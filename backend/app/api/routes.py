"""FastAPI route handlers for authentication, EHR operations, AI predictions,
and audit verification.

These routes intentionally keep all sensitive payload handling on the trusted
backend. Database columns remain encrypted at rest, and cloud inference stays
behind the trusted prediction service boundary.
"""
from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user, require_roles
from app.core.security import create_token_pair, decode_token, hash_password, verify_password
from app.crypto.abe import (
    ABEError,
    ATTRIBUTE_UNIVERSE,
    PolicyNotSatisfied,
    get_abe_authority,
)
from app.db.models import Consent, MedicalRecord, Patient, User
from app.db.session import get_db
from app.ml.registry import DISEASES
from app.schemas import (
    AuditBlockView,
    AuditVerifyView,
    ChatMessageView,
    ChatRequest,
    ChatTurnResponse,
    ConsentGrantRequest,
    ConsentView,
    DiseaseFeatureView,
    DiseaseSpecView,
    FhirExportView,
    LoginRequest,
    PatientCreate,
    PatientSummary,
    PatientUpdate,
    PatientView,
    PredictionCreateResponse,
    PredictionRequest,
    PredictionStoredView,
    RecordCreate,
    RecordIntegrityView,
    RecordShareRequest,
    RecordSummary,
    RecordView,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
    UserView,
)
from app.services import (
    audit_service,
    chat_service,
    consent_service,
    fhir_service,
    prediction_service,
    record_service,
)

router = APIRouter(prefix="/api")
_ATTRIBUTE_UNIVERSE = set(ATTRIBUTE_UNIVERSE)


def _actor(user: User) -> str:
    return f"{user.role}:{user.username}:{user.id}"


def _get_patient(db: Session, patient_id: str) -> Patient:
    patient = db.get(Patient, patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="patient not found")
    return patient


def _get_record(db: Session, record_id: str) -> MedicalRecord:
    record = db.get(MedicalRecord, record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="record not found")
    return record


def _patient_summary(patient: Patient) -> PatientSummary:
    return PatientSummary(
        id=patient.id,
        user_id=patient.user_id,
        mrn=patient.mrn,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
    )


def _patient_view(patient: Patient, demographics: dict) -> PatientView:
    return PatientView(
        id=patient.id,
        user_id=patient.user_id,
        mrn=patient.mrn,
        demographics=demographics,
        created_by=patient.created_by,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
    )


def _record_summary(record: MedicalRecord) -> RecordSummary:
    return RecordSummary(
        id=record.id,
        patient_id=record.patient_id,
        record_type=record.record_type,
        category=record.category,
        abe_policy=record.abe_policy,
        created_by=record.created_by,
        created_at=record.created_at,
    )


def _record_view(record: MedicalRecord, decrypted: dict) -> RecordView:
    return RecordView(
        id=record.id,
        patient_id=record.patient_id,
        record_type=record.record_type,
        category=record.category,
        title=decrypted["title"],
        payload=decrypted["payload"],
        abe_policy=record.abe_policy,
        created_by=record.created_by,
        created_at=record.created_at,
    )


def _can_manage_patient(user: User, patient: Patient) -> bool:
    return user.role == "admin" or patient.user_id == user.id


def _validate_abe_attributes(attrs: list[str]) -> None:
    unsupported = [attr for attr in attrs if attr not in _ATTRIBUTE_UNIVERSE]
    if unsupported:
        raise HTTPException(
            status_code=400,
            detail=f"unsupported ABE attributes requested: {unsupported}",
        )


def _require_patient_access(
    db: Session,
    *,
    user: User,
    patient: Patient,
    category: str | None = None,
    purpose: str = "treatment",
) -> str:
    allowed, reason = consent_service.check_access(
        db,
        user=user,
        patient=patient,
        category=category,
        purpose=purpose,
    )
    if not allowed:
        raise HTTPException(status_code=403, detail=reason)
    return reason


@router.post("/auth/register", response_model=UserView, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> UserView:
    """Self-service patient registration."""
    existing = db.execute(
        select(User).where(or_(User.username == payload.username, User.email == payload.email))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="username or email already exists")
    attrs = [
        "role:patient",
        "relation:self",
        f"org:{payload.organization}",
        f"dept:{payload.department}",
    ]
    _validate_abe_attributes(attrs)
    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role="patient",
        organization=payload.organization,
        department=payload.department,
        attributes=attrs,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    get_abe_authority().issue_user_key(user.id, user.attributes)
    audit_service.append_event(
        db,
        actor=f"patient:{user.username}:{user.id}",
        action="user.register",
        resource=f"user:{user.id}",
        details={"role": user.role},
    )
    return UserView.model_validate(user)


@router.post("/auth/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    """Authenticate and mint access/refresh tokens."""
    user = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid username or password")
    tokens = create_token_pair(user.id, user.role, list(user.attributes or []))
    audit_service.append_event(
        db,
        actor=_actor(user),
        action="auth.login",
        resource=f"user:{user.id}",
        details={"role": user.role},
    )
    return TokenPair(**tokens)


@router.post("/auth/refresh", response_model=TokenPair)
def refresh_tokens(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    """Exchange a valid refresh token for a fresh access/refresh token pair."""
    try:
        claims = decode_token(payload.refresh_token, expected_type="refresh")
    except pyjwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"invalid refresh token: {exc.__class__.__name__}",
        ) from exc
    user = db.get(User, claims["sub"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="user inactive or unknown")
    tokens = create_token_pair(user.id, user.role, list(user.attributes or []))
    return TokenPair(**tokens)


@router.get("/auth/me", response_model=UserView)
def me(current_user: User = Depends(get_current_user)) -> UserView:
    """Return the authenticated user's profile."""
    return UserView.model_validate(current_user)


@router.get("/patients", response_model=list[PatientSummary])
def list_patients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PatientSummary]:
    """List visible patients. Patients only see themselves."""
    if current_user.role == "patient":
        rows = db.execute(select(Patient).where(Patient.user_id == current_user.id)).scalars().all()
    else:
        rows = db.execute(select(Patient).order_by(Patient.created_at.desc())).scalars().all()
    return [_patient_summary(row) for row in rows]


@router.post("/patients", response_model=PatientView, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "admin")),
) -> PatientView:
    """Create a patient profile with encrypted demographics."""
    existing = db.execute(select(Patient).where(Patient.mrn == payload.mrn)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="MRN already exists")
    if payload.user_id is not None and db.get(User, payload.user_id) is None:
        raise HTTPException(status_code=404, detail="linked user not found")
    patient = record_service.create_patient(
        db,
        mrn=payload.mrn,
        demographics=payload.demographics,
        created_by=current_user,
    )
    if payload.user_id is not None:
        patient.user_id = payload.user_id
        db.commit()
        db.refresh(patient)
    audit_service.append_event(
        db,
        actor=_actor(current_user),
        action="patient.create",
        resource=f"patient:{patient.id}",
        details={"mrn": patient.mrn},
    )
    return _patient_view(patient, record_service.read_demographics(db, patient))


@router.get("/patients/{patient_id}", response_model=PatientView)
def get_patient(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PatientView:
    """Fetch decrypted demographics for one patient."""
    patient = _get_patient(db, patient_id)
    _require_patient_access(db, user=current_user, patient=patient)
    return _patient_view(patient, record_service.read_demographics(db, patient))


@router.put("/patients/{patient_id}", response_model=PatientView)
def update_patient(
    patient_id: str,
    payload: PatientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PatientView:
    """Replace a patient's encrypted demographics blob."""
    patient = _get_patient(db, patient_id)
    if not _can_manage_patient(current_user, patient) and current_user.role != "doctor":
        raise HTTPException(status_code=403, detail="not allowed to update this patient")
    updated = record_service.update_demographics(db, patient, payload.demographics)
    audit_service.append_event(
        db,
        actor=_actor(current_user),
        action="patient.update",
        resource=f"patient:{patient.id}",
        details={},
    )
    return _patient_view(updated, record_service.read_demographics(db, updated))


@router.get("/patients/{patient_id}/records", response_model=list[RecordSummary])
def list_patient_records(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[RecordSummary]:
    """List record metadata visible to the caller."""
    patient = _get_patient(db, patient_id)
    records = record_service.list_records(db, patient_id)
    if current_user.role == "auditor":
        return [_record_summary(record) for record in records]
    if current_user.role in {"admin", "patient"} and (
        current_user.role == "admin" or patient.user_id == current_user.id
    ):
        return [_record_summary(record) for record in records]
    visible: list[RecordSummary] = []
    for record in records:
        allowed, _ = consent_service.check_access(
            db,
            user=current_user,
            patient=patient,
            category=record.category,
            purpose="treatment",
        )
        if allowed:
            visible.append(_record_summary(record))
    return visible


@router.post(
    "/patients/{patient_id}/records",
    response_model=RecordView,
    status_code=status.HTTP_201_CREATED,
)
def create_record(
    patient_id: str,
    payload: RecordCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "admin")),
) -> RecordView:
    """Create one encrypted medical record."""
    patient = _get_patient(db, patient_id)
    if current_user.role != "admin":
        _require_patient_access(
            db,
            user=current_user,
            patient=patient,
            category=payload.category,
            purpose="treatment",
        )
    record = record_service.create_record(
        db,
        patient=patient,
        record_type=payload.record_type,
        category=payload.category,
        title=payload.title,
        payload=payload.payload,
        created_by=current_user,
    )
    audit_service.append_event(
        db,
        actor=_actor(current_user),
        action="record.create",
        resource=f"record:{record.id}",
        details={"patient_id": patient.id, "category": record.category},
    )
    return _record_view(record, record_service.read_record(db, record))


@router.get("/patients/{patient_id}/records/{record_id}", response_model=RecordView)
def get_record(
    patient_id: str,
    record_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecordView:
    """Decrypt one record after consent enforcement."""
    patient = _get_patient(db, patient_id)
    record = _get_record(db, record_id)
    if record.patient_id != patient.id:
        raise HTTPException(status_code=404, detail="record does not belong to patient")
    _require_patient_access(
        db,
        user=current_user,
        patient=patient,
        category=record.category,
        purpose="treatment",
    )
    decrypted = record_service.read_record(db, record)
    audit_service.append_event(
        db,
        actor=_actor(current_user),
        action="record.read",
        resource=f"record:{record.id}",
        details={"patient_id": patient.id, "category": record.category},
    )
    return _record_view(record, decrypted)


@router.get("/patients/{patient_id}/records/{record_id}/verify", response_model=RecordIntegrityView)
def verify_record_integrity(
    patient_id: str,
    record_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "admin", "auditor")),
) -> RecordIntegrityView:
    """Verify record ciphertext authenticity and stored digest."""
    _get_patient(db, patient_id)
    record = _get_record(db, record_id)
    if record.patient_id != patient_id:
        raise HTTPException(status_code=404, detail="record does not belong to patient")
    status_view = record_service.verify_record(db, record)
    audit_service.append_event(
        db,
        actor=_actor(current_user),
        action="record.verify",
        resource=f"record:{record.id}",
        details={"patient_id": patient_id},
    )
    return RecordIntegrityView(**status_view)


@router.post("/records/{record_id}/share", response_model=RecordSummary)
def share_record(
    record_id: str,
    payload: RecordShareRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("doctor", "admin")),
) -> RecordSummary:
    """Wrap a record under a CP-ABE policy for cross-organization sharing."""
    record = _get_record(db, record_id)
    patient = _get_patient(db, record.patient_id)
    if current_user.role != "admin":
        _require_patient_access(
            db,
            user=current_user,
            patient=patient,
            category=record.category,
            purpose="export",
        )
    updated = record_service.share_with_policy(db, record, payload.policy)
    audit_service.append_event(
        db,
        actor=_actor(current_user),
        action="record.share",
        resource=f"record:{record.id}",
        details={"policy": payload.policy},
    )
    return _record_summary(updated)


@router.post("/records/{record_id}/open-abe", response_model=RecordView)
def open_shared_record(
    record_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RecordView:
    """Attempt to decrypt a CP-ABE shared record with the caller's ABE key."""
    record = _get_record(db, record_id)
    try:
        opened = record_service.open_abe_record(record, current_user)
    except PolicyNotSatisfied as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ABEError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit_service.append_event(
        db,
        actor=_actor(current_user),
        action="record.open_abe",
        resource=f"record:{record.id}",
        details={"policy": record.abe_policy},
    )
    return RecordView(
        id=record.id,
        patient_id=record.patient_id,
        record_type=record.record_type,
        category=record.category,
        title=opened["title"],
        payload=opened["payload"],
        abe_policy=record.abe_policy,
        created_by=record.created_by,
        created_at=record.created_at,
    )


@router.get("/patients/{patient_id}/consents", response_model=list[ConsentView])
def list_consents(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ConsentView]:
    """List active consents for a patient."""
    patient = _get_patient(db, patient_id)
    if not _can_manage_patient(current_user, patient):
        raise HTTPException(status_code=403, detail="only the patient or admin can view consents")
    return [
        ConsentView.model_validate(row)
        for row in consent_service.active_consents_for_patient(db, patient_id)
    ]


@router.post(
    "/patients/{patient_id}/consents",
    response_model=ConsentView,
    status_code=status.HTTP_201_CREATED,
)
def grant_consent(
    patient_id: str,
    payload: ConsentGrantRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConsentView:
    """Grant a scoped consent to a doctor/user."""
    patient = _get_patient(db, patient_id)
    if not _can_manage_patient(current_user, patient):
        raise HTTPException(status_code=403, detail="only the patient or admin can grant consent")
    grantee = db.get(User, payload.grantee_user_id)
    if grantee is None:
        raise HTTPException(status_code=404, detail="grantee user not found")
    consent = consent_service.grant(
        db,
        patient=patient,
        grantee_user_id=payload.grantee_user_id,
        categories=payload.categories,
        purposes=payload.purposes,
        expires_at=payload.expires_at,
    )
    audit_service.append_event(
        db,
        actor=_actor(current_user),
        action="consent.grant",
        resource=f"consent:{consent.id}",
        details={"patient_id": patient.id, "grantee_user_id": grantee.id},
    )
    return ConsentView.model_validate(consent)


@router.post("/consents/{consent_id}/revoke", response_model=ConsentView)
def revoke_consent(
    consent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConsentView:
    """Revoke a consent grant."""
    consent = db.get(Consent, consent_id)
    if consent is None:
        raise HTTPException(status_code=404, detail="consent not found")
    patient = _get_patient(db, consent.patient_id)
    if not _can_manage_patient(current_user, patient):
        raise HTTPException(status_code=403, detail="only the patient or admin can revoke consent")
    revoked = consent_service.revoke(db, consent)
    audit_service.append_event(
        db,
        actor=_actor(current_user),
        action="consent.revoke",
        resource=f"consent:{consent.id}",
        details={"patient_id": patient.id, "grantee_user_id": revoked.grantee_user_id},
    )
    return ConsentView.model_validate(revoked)


@router.get("/diseases", response_model=list[DiseaseSpecView])
def list_diseases(
    _: User = Depends(get_current_user),
) -> list[DiseaseSpecView]:
    """Return the canonical disease model catalog and feature definitions."""
    return [
        DiseaseSpecView(
            key=spec.key,
            label=spec.label,
            features=[
                DiseaseFeatureView(
                    name=f.name,
                    label=f.label,
                    min=f.min,
                    max=f.max,
                    mean=f.mean,
                    std=f.std,
                )
                for f in spec.features
            ],
        )
        for spec in DISEASES.values()
    ]


@router.post(
    "/patients/{patient_id}/predictions",
    response_model=PredictionCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_prediction(
    patient_id: str,
    payload: PredictionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PredictionCreateResponse:
    """Run encrypted inference and persist the result encrypted at rest."""
    patient = _get_patient(db, patient_id)
    if current_user.role != "admin":
        _require_patient_access(
            db,
            user=current_user,
            patient=patient,
            purpose="ai_prediction",
        )
    try:
        _, result = prediction_service.create_prediction(
            db,
            patient=patient,
            disease=payload.disease,
            features=payload.features,
            created_by=current_user,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    audit_service.append_event(
        db,
        actor=_actor(current_user),
        action="prediction.create",
        resource=f"patient:{patient.id}",
        details={"disease": payload.disease},
    )
    return PredictionCreateResponse(**result)


@router.get("/patients/{patient_id}/predictions", response_model=list[PredictionStoredView])
def list_patient_predictions(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[PredictionStoredView]:
    """List decrypted stored predictions for one patient."""
    patient = _get_patient(db, patient_id)
    if current_user.role != "admin":
        _require_patient_access(
            db,
            user=current_user,
            patient=patient,
            purpose="ai_prediction",
        )
    rows = prediction_service.list_predictions(db, patient_id)
    return [PredictionStoredView(**prediction_service.read_prediction(row)) for row in rows]


@router.post(
    "/patients/{patient_id}/fhir",
    response_model=FhirExportView,
    status_code=status.HTTP_201_CREATED,
)
def export_patient_fhir(
    patient_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FhirExportView:
    """Export consented patient data as a signed HL7 FHIR R4 Bundle."""
    patient = _get_patient(db, patient_id)
    if current_user.role != "admin":
        _require_patient_access(
            db,
            user=current_user,
            patient=patient,
            purpose="export",
        )
    exported = fhir_service.export_patient_bundle(db, patient=patient, actor=current_user)
    audit_service.append_event(
        db,
        actor=_actor(current_user),
        action="fhir.export",
        resource=f"patient:{patient.id}",
        details={
            "export_id": exported["export_id"],
            "resource_count": exported["resource_count"],
            "bundle_sha256": exported["bundle_sha256"],
        },
    )
    return FhirExportView(**exported)


@router.post("/chat", response_model=ChatTurnResponse, status_code=status.HTTP_201_CREATED)
def clinical_chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatTurnResponse:
    """Run the PII-scrubbed LangGraph clinical assistant and persist encrypted messages."""
    patient: Patient | None = None
    if payload.patient_id is not None:
        patient = _get_patient(db, payload.patient_id)
        if current_user.role != "admin":
            _require_patient_access(db, user=current_user, patient=patient)
    user_msg, assistant_msg = chat_service.send_chat(
        db,
        user=current_user,
        prompt=payload.prompt,
        patient=patient,
    )
    audit_service.append_event(
        db,
        actor=_actor(current_user),
        action="chat.turn",
        resource=f"patient:{patient.id}" if patient else f"user:{current_user.id}",
        details={"has_patient_context": patient is not None},
    )
    return ChatTurnResponse(
        user_message=ChatMessageView(**user_msg),
        assistant_message=ChatMessageView(**assistant_msg),
    )


@router.get("/chat/history", response_model=list[ChatMessageView])
def clinical_chat_history(
    patient_id: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ChatMessageView]:
    """List decrypted chat messages belonging to the authenticated user."""
    rows = chat_service.list_history(db, user=current_user, patient_id=patient_id, limit=limit)
    return [ChatMessageView(**row) for row in rows]


@router.get("/audit/chain", response_model=list[AuditBlockView])
def audit_chain(
    limit: int = 200,
    offset: int = 0,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles("admin", "auditor")),
) -> list[AuditBlockView]:
    """Return a slice of the append-only audit chain."""
    return [AuditBlockView(**row) for row in audit_service.get_chain(db, limit=limit, offset=offset)]


@router.get("/audit/verify", response_model=AuditVerifyView)
def audit_verify(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "auditor")),
) -> AuditVerifyView:
    """Verify the full audit blockchain and HMAC signatures."""
    result = audit_service.verify(db)
    audit_service.append_event(
        db,
        actor=_actor(current_user),
        action="audit.verify",
        resource="audit-chain",
        details=result,
    )
    return AuditVerifyView(**result)

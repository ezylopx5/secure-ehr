"""FastAPI application entrypoint for the Secure AI-Powered EHR backend.

This module wires together:
- startup bootstrap (DB schema, audit-chain genesis, dev demo users),
- the 7-layer middleware stack,
- authenticated clinical, consent, prediction, and audit routes.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import uuid

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import and_, select

from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.routes import router as api_router
from app.core.config import IS_VERCEL, get_settings
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.crypto.abe import get_abe_authority
from app.db.models import Consent, MedicalRecord, Patient, User
from app.db.session import SessionLocal, init_db
from app.middleware.stack import (
    ExceptionScrubMiddleware,
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
)
from app.schemas import HealthView
from app.services import audit_service, consent_service, record_service

settings = get_settings()
configure_logging()
log = get_logger(__name__)
allowed_hosts = list(dict.fromkeys(settings.trusted_host_list + (["testserver"] if settings.is_dev else [])))


def _det_id(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"aegis-ehr.demo.{label}"))


def _ensure_user(
    *,
    db,
    username: str,
    email: str,
    password: str,
    full_name: str,
    role: str,
    organization: str,
    department: str,
    attributes: list[str],
) -> User:
    user = db.execute(select(User).where(User.username == username)).scalar_one_or_none()
    if user is not None:
        return user
    user = User(
        id=_det_id(f"user.{username}"),
        username=username,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role=role,
        organization=organization,
        department=department,
        attributes=attributes,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    if not IS_VERCEL:
        get_abe_authority().issue_user_key(user.id, user.attributes)
    return user


def _seed_dev_demo() -> None:
    """Create idempotent demo actors and one consented patient in dev mode."""
    if not settings.is_dev:
        return
    with SessionLocal() as db:
        admin = _ensure_user(
            db=db,
            username="admin",
            email="admin@secure-ehr.local",
            password="Admin12345",
            full_name="System Administrator",
            role="admin",
            organization="nitsurat-hospital",
            department="general",
            attributes=["role:admin", "org:nitsurat-hospital", "dept:general"],
        )
        doctor = _ensure_user(
            db=db,
            username="doctor1",
            email="doctor1@secure-ehr.local",
            password="Doctor12345",
            full_name="Dr. Priya Shah",
            role="doctor",
            organization="nitsurat-hospital",
            department="cardiology",
            attributes=[
                "role:doctor",
                "org:nitsurat-hospital",
                "dept:cardiology",
                "relation:primary-physician",
                "cat:cardiac",
                "cat:labs",
                "cat:general",
            ],
        )
        _ensure_user(
            db=db,
            username="auditor1",
            email="auditor1@secure-ehr.local",
            password="Auditor12345",
            full_name="Security Auditor",
            role="auditor",
            organization="nitsurat-hospital",
            department="general",
            attributes=["role:auditor", "org:nitsurat-hospital", "dept:general"],
        )
        patient_user = _ensure_user(
            db=db,
            username="patient1",
            email="patient1@secure-ehr.local",
            password="Patient12345",
            full_name="Aarav Patel",
            role="patient",
            organization="nitsurat-hospital",
            department="general",
            attributes=[
                "role:patient",
                "relation:self",
                "org:nitsurat-hospital",
                "dept:general",
            ],
        )
        patient = db.execute(select(Patient).where(Patient.user_id == patient_user.id)).scalar_one_or_none()
        if patient is None:
            patient = record_service.create_patient(
                db,
                mrn="MRN-DEMO-0001",
                demographics={
                    "name": "Aarav Patel",
                    "gender": "male",
                    "dob": "1999-08-14",
                    "phone": "9999999999",
                    "blood_group": "B+",
                },
                created_by=admin,
                patient_id=_det_id("patient.MRN-DEMO-0001"),
            )
            patient.user_id = patient_user.id
            db.commit()
            db.refresh(patient)
        consent = db.execute(
            select(Consent).where(
                and_(
                    Consent.patient_id == patient.id,
                    Consent.grantee_user_id == doctor.id,
                    Consent.status == "active",
                )
            )
        ).scalar_one_or_none()
        if consent is None:
            consent_service.grant(
                db,
                patient=patient,
                grantee_user_id=doctor.id,
                categories=["cardiac", "labs", "general"],
                purposes=["treatment", "ai_prediction", "export"],
            )
        existing_records = db.execute(
            select(MedicalRecord).where(MedicalRecord.patient_id == patient.id)
        ).scalars().all()
        if not existing_records:
            record_service.create_record(
                db,
                patient=patient,
                record_type="lab",
                category="cardiac",
                title="High-Sensitivity Troponin & Lipid Panel",
                payload={
                    "ldl_mg_dl": 138,
                    "hdl_mg_dl": 46,
                    "triglycerides_mg_dl": 162,
                    "troponin_ng_ml": 0.012,
                    "notes": "Sinus rhythm, mildly elevated LDL cholesterol; advise statin evaluation.",
                },
                created_by=doctor,
                record_id=_det_id("record.cardiac-lipid-panel"),
            )
            record_service.create_record(
                db,
                patient=patient,
                record_type="vitals",
                category="general",
                title="Baseline Cardiology Outpatient Vitals",
                payload={
                    "bp_systolic_mmhg": 134,
                    "bp_diastolic_mmhg": 84,
                    "heart_rate_bpm": 76,
                    "spo2_pct": 98,
                    "bmi": 26.4,
                },
                created_by=doctor,
                record_id=_det_id("record.baseline-vitals"),
            )
        log.info(
            "Dev demo data ready: admin, doctor1, auditor1, patient1 seeded"
        )


_BOOTSTRAPPED = False


def ensure_bootstrapped() -> None:
    """Idempotently initialize DB schema, audit genesis, and demo seed data."""
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED:
        return
    init_db()
    with SessionLocal() as db:
        audit_service.ensure_genesis(db)
    _seed_dev_demo()
    _BOOTSTRAPPED = True


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize persistent state before the API starts serving."""
    global _BOOTSTRAPPED
    _BOOTSTRAPPED = False
    ensure_bootstrapped()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)

# Inside-out order in Starlette means we register the innermost first and the
# outermost last so requests traverse the intended 7-layer stack.
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ExceptionScrubMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=512)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["*"], allow_headers=["*"])
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts or ["*"])
app.add_middleware(
    RateLimitMiddleware,
    rate_per_second=settings.RATE_LIMIT_RPS,
    burst=settings.RATE_LIMIT_BURST,
)

app.include_router(api_router)


@app.get("/healthz", response_model=HealthView, tags=["system"])
def healthz() -> HealthView:
    """Liveness check with basic environment metadata."""
    return HealthView(status="ok", app=settings.APP_NAME, env=settings.ENV)


_FRONTEND_DIST = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"
if (_FRONTEND_DIST / "assets").is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=str(_FRONTEND_DIST / "assets")),
        name="frontend-assets",
    )


@app.get("/", include_in_schema=False)
def serve_spa_root():
    """Serve the built React clinical portal index.html."""
    index_file = _FRONTEND_DIST / "index.html"
    if index_file.is_file():
        return FileResponse(str(index_file))
    return {"status": "ok", "app": settings.APP_NAME}

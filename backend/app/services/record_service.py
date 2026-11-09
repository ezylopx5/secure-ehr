"""Medical record lifecycle: encrypt-at-rest writes, decrypt+verify reads,
integrity verification and ABE-based sharing.

Cryptographic envelope per record:
    key  = HKDF(master, salt=record_uuid, info="ehr:record-dek")
    blob = AES-256-GCM(key, canonical_json(payload), aad=record_uuid)
    plaintext_sha256 = SHA-256(canonical_json(payload))  # stored for drift checks
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.crypto.abe import ABEError, PolicyNotSatisfied, get_abe_authority
from app.crypto.aes_gcm import decrypt_bytes, decrypt_json, encrypt_bytes, encrypt_json
from app.crypto.integrity import sha256_json
from app.crypto.key_manager import get_key_manager
from app.db.models import MedicalRecord, Patient, User

log = get_logger(__name__)

RECORD_TYPES = {"note", "lab", "vitals", "prescription", "imaging_meta"}
CATEGORIES = {"cardiac", "general", "mental", "labs", "imaging"}


def _aad(record_id: str) -> bytes:
    return f"ehr:record:{record_id}".encode()


# ---- patients --------------------------------------------------------------
def create_patient(
    db: Session,
    *,
    mrn: str,
    demographics: dict,
    created_by: User | None,
    patient_id: str | None = None,
) -> Patient:
    patient = Patient(
        id=patient_id or str(uuid.uuid4()),
        mrn=mrn,
        created_by=created_by.id if created_by else None,
    )
    db.add(patient)
    km = get_key_manager()
    key = km.record_dek(patient.id)
    patient.demographics_enc = encrypt_json(key, demographics, aad=_aad(patient.id))
    patient.demographics_sha256 = sha256_json(demographics)
    patient.key_version = km.key_version
    db.commit()
    db.refresh(patient)
    return patient


def read_demographics(db: Session, patient: Patient) -> dict:
    km = get_key_manager()
    data = decrypt_json(km.record_dek(patient.id), patient.demographics_enc, _aad(patient.id))
    if sha256_json(data) != patient.demographics_sha256:
        raise ValueError(f"integrity failure: demographics of patient {patient.id} altered")
    return data


def update_demographics(db: Session, patient: Patient, demographics: dict) -> Patient:
    km = get_key_manager()
    key = km.record_dek(patient.id)
    patient.demographics_enc = encrypt_json(key, demographics, aad=_aad(patient.id))
    patient.demographics_sha256 = sha256_json(demographics)
    db.commit()
    return patient


# ---- records ----------------------------------------------------------------
def create_record(
    db: Session,
    *,
    patient: Patient,
    record_type: str,
    category: str,
    title: str,
    payload: dict,
    created_by: User,
    record_id: str | None = None,
) -> MedicalRecord:
    if record_type not in RECORD_TYPES:
        raise ValueError(f"record_type must be one of {sorted(RECORD_TYPES)}")
    if category not in CATEGORIES:
        raise ValueError(f"category must be one of {sorted(CATEGORIES)}")
    record = MedicalRecord(
        id=record_id or str(uuid.uuid4()),
        patient_id=patient.id,
        record_type=record_type,
        category=category,
        created_by=created_by.id,
    )
    db.add(record)
    km = get_key_manager()
    key = km.record_dek(record.id)
    record.title_enc = encrypt_json(key, {"title": title}, aad=_aad(record.id))
    record.payload_enc = encrypt_json(key, payload, aad=_aad(record.id))
    record.plaintext_sha256 = sha256_json(payload)
    record.key_version = km.key_version
    db.commit()
    db.refresh(record)
    return record


def read_record(db: Session, record: MedicalRecord) -> dict:
    """Decrypt and verify one record (caller MUST have passed consent checks)."""
    km = get_key_manager()
    key = km.record_dek(record.id)
    payload = decrypt_json(key, record.payload_enc, aad=_aad(record.id))
    title = decrypt_json(key, record.title_enc, aad=_aad(record.id))["title"]
    if sha256_json(payload) != record.plaintext_sha256:
        raise ValueError(f"integrity failure: record {record.id} altered at rest")
    return {"title": title, "payload": payload}


def verify_record(db: Session, record: MedicalRecord) -> dict:
    try:
        payload = decrypt_json(
            get_key_manager().record_dek(record.id), record.payload_enc,
            aad=_aad(record.id),
        )
        ok = sha256_json(payload) == record.plaintext_sha256
        return {"record_id": record.id, "integrity": "ok" if ok else "HASH-MISMATCH"}
    except Exception as exc:  # noqa: BLE001
        return {"record_id": record.id, "integrity": f"DECRYPT-FAILED ({exc.__class__.__name__})"}


def list_records(db: Session, patient_id: str) -> list[MedicalRecord]:
    return list(
        db.execute(
            select(MedicalRecord)
            .where(MedicalRecord.patient_id == patient_id)
            .order_by(MedicalRecord.created_at.desc())
        ).scalars()
    )


# ---- ABE sharing -------------------------------------------------------------
def share_with_policy(db: Session, record: MedicalRecord, policy: str) -> MedicalRecord:
    """Re-wrap the record payload under a CP-ABE policy. Anyone whose ABE
    key satisfies the policy can recover the payload WITHOUT the hospital's
    master key - this is the cross-organization sharing path."""
    plaintext = read_record(db, record)
    import json

    authority = get_abe_authority()
    ct = authority.encrypt(
        json.dumps(plaintext, sort_keys=True).encode(), policy
    )
    record.abe_policy = policy
    record.abe_ct = ct
    db.commit()
    db.refresh(record)
    return record


def open_abe_record(record: MedicalRecord, user: User) -> dict:
    """Attempt to open a shared record with the caller's ABE private key."""
    if not record.abe_ct:
        raise ABEError("record has not been shared under an ABE policy")
    authority = get_abe_authority()
    try:
        key = authority.load_user_key(user.id)
    except ABEError:
        key = authority.issue_user_key(user.id, list(user.attributes or []))
    import json

    plaintext = json.loads(authority.decrypt(record.abe_ct, key))
    return {
        "policy": record.abe_policy,
        "satisfied_attributes": sorted(set(key.attributes)),
        **plaintext,
    }

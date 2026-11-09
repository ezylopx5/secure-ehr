"""ORM models. Design rule: NOTHING sensitive is stored in the clear.

Encrypted columns (AES-256-GCM, per-row HKDF-derived keys) hold the actual
content; adjacent ``*_sha256`` columns store the plaintext digest captured at
write time so any silent drift is detectable on read (see record_service).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Users & patients
# --------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(128))  # bcrypt
    full_name: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16))  # admin|doctor|patient|auditor
    organization: Mapped[str] = mapped_column(String(128), default="")
    department: Mapped[str] = mapped_column(String(64), default="")
    # ABE attributes, e.g. ["role:doctor", "dept:cardiology", "org:nitsurat-hospital"]
    attributes: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    patient_profile: Mapped["Patient"] = relationship(
        back_populates="user", uselist=False, foreign_keys="Patient.user_id"
    )


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    mrn: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # record number
    demographics_enc: Mapped[bytes] = mapped_column(LargeBinary)  # AES-GCM blob
    demographics_sha256: Mapped[str] = mapped_column(String(64))
    key_version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    user: Mapped[User | None] = relationship(
        back_populates="patient_profile", foreign_keys=[user_id]
    )
    records: Mapped[list["MedicalRecord"]] = relationship(back_populates="patient")


# --------------------------------------------------------------------------
# Medical records
# --------------------------------------------------------------------------
class MedicalRecord(Base):
    __tablename__ = "medical_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    record_type: Mapped[str] = mapped_column(String(32))  # note|lab|vitals|prescription|imaging_meta
    category: Mapped[str] = mapped_column(String(32), index=True)  # cardiac|general|mental|labs|imaging
    title_enc: Mapped[bytes] = mapped_column(LargeBinary)
    payload_enc: Mapped[bytes] = mapped_column(LargeBinary)  # nonce||ct||tag
    plaintext_sha256: Mapped[str] = mapped_column(String(64))
    key_version: Mapped[int] = mapped_column(Integer, default=1)
    # ABE-protected sharing (policy + wrapped copy for cross-org sharing)
    abe_policy: Mapped[str | None] = mapped_column(Text, nullable=True)
    abe_ct: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    patient: Mapped[Patient] = relationship(back_populates="records")


# --------------------------------------------------------------------------
# Consent management
# --------------------------------------------------------------------------
class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(
        ForeignKey("patients.id", ondelete="CASCADE"), index=True
    )
    grantee_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    # e.g. {"categories": ["cardiac", "labs"], "purposes": ["treatment", "ai_prediction"]}
    scope: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active|revoked
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --------------------------------------------------------------------------
# Audit blockchain
# --------------------------------------------------------------------------
class AuditBlockRow(Base):
    __tablename__ = "audit_blocks"

    seq: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    index: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    timestamp: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource: Mapped[str] = mapped_column(String(128), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64))
    block_hash: Mapped[str] = mapped_column(String(64))
    hmac_sig: Mapped[str] = mapped_column(String(64))


# --------------------------------------------------------------------------
# AI predictions (encrypted at rest; encrypted-in-transit-to-cloud)
# --------------------------------------------------------------------------
class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    disease: Mapped[str] = mapped_column(String(32), index=True)
    model_version: Mapped[str] = mapped_column(String(64), default="stub-synthetic")
    features_enc: Mapped[bytes] = mapped_column(LargeBinary)
    result_enc: Mapped[bytes] = mapped_column(LargeBinary)  # prob + shap + interval
    risk_band: Mapped[str] = mapped_column(String(16))  # low|moderate|high
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# --------------------------------------------------------------------------
# Clinical chat (content encrypted - conversations may contain PHI)
# --------------------------------------------------------------------------
class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    patient_id: Mapped[str | None] = mapped_column(
        ForeignKey("patients.id", ondelete="SET NULL"), nullable=True
    )
    role: Mapped[str] = mapped_column(String(16))  # user|assistant
    content_enc: Mapped[bytes] = mapped_column(LargeBinary)
    agent_trace: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# --------------------------------------------------------------------------
# FHIR exports
# --------------------------------------------------------------------------
class FhirExport(Base):
    __tablename__ = "fhir_exports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    bundle_sha256: Mapped[str] = mapped_column(String(64))
    checksum_hmac: Mapped[str] = mapped_column(String(64))
    resource_count: Mapped[int] = mapped_column(Integer)
    exported_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

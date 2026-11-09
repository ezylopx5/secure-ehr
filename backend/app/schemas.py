"""Typed API schemas for the Secure EHR backend.

These models define the request/response contracts for authentication,
patients, encrypted records, consents, predictions, and audit views.
They intentionally avoid exposing raw encrypted database blobs directly.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ApiMessage(BaseModel):
    """Simple success/info payload."""

    message: str


class TokenPair(BaseModel):
    """JWT access/refresh pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """Username/password login request."""

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=72)


class RegisterRequest(BaseModel):
    """Self-service patient registration payload."""

    username: str = Field(min_length=3, max_length=64)
    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(min_length=1, max_length=128)
    role: Literal["patient"] = "patient"
    organization: str = Field(default="nitsurat-hospital", max_length=128)
    department: str = Field(default="general", max_length=64)


class UserView(BaseModel):
    """Safe user profile returned to clients."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: str
    full_name: str
    role: str
    organization: str
    department: str
    attributes: list[str]
    is_active: bool
    created_at: datetime


class PatientCreate(BaseModel):
    """Create a new patient shell with encrypted demographics."""

    mrn: str = Field(min_length=3, max_length=32)
    demographics: dict[str, Any]
    user_id: str | None = None


class PatientUpdate(BaseModel):
    """Replace encrypted demographics."""

    demographics: dict[str, Any]


class PatientView(BaseModel):
    """Patient view with decrypted demographics."""

    id: str
    user_id: str | None
    mrn: str
    demographics: dict[str, Any]
    created_by: str | None
    created_at: datetime
    updated_at: datetime


class PatientSummary(BaseModel):
    """Patient metadata for list screens."""

    id: str
    user_id: str | None
    mrn: str
    created_at: datetime
    updated_at: datetime


class RecordCreate(BaseModel):
    """Create an encrypted medical record."""

    record_type: Literal["note", "lab", "vitals", "prescription", "imaging_meta"]
    category: Literal["cardiac", "general", "mental", "labs", "imaging"]
    title: str = Field(min_length=1, max_length=256)
    payload: dict[str, Any]


class RecordShareRequest(BaseModel):
    """Share a record with a CP-ABE policy."""

    policy: str = Field(min_length=3)


class RecordView(BaseModel):
    """Decrypted record payload."""

    id: str
    patient_id: str
    record_type: str
    category: str
    title: str
    payload: dict[str, Any]
    abe_policy: str | None
    created_by: str | None
    created_at: datetime


class RecordSummary(BaseModel):
    """Record metadata for tables and auditor views."""

    id: str
    patient_id: str
    record_type: str
    category: str
    abe_policy: str | None
    created_by: str | None
    created_at: datetime


class RecordIntegrityView(BaseModel):
    """Integrity verification status."""

    record_id: str
    integrity: str


class ConsentGrantRequest(BaseModel):
    """Grant access to a user for selected record categories/purposes."""

    grantee_user_id: str
    categories: list[str] = Field(min_length=1)
    purposes: list[str] = Field(default_factory=lambda: ["treatment"])
    expires_at: datetime | None = None


class ConsentView(BaseModel):
    """Consent state returned to UI."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    patient_id: str
    grantee_user_id: str
    scope: dict[str, Any]
    status: str
    granted_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None


class PredictionRequest(BaseModel):
    """Disease prediction request over a patient's feature vector."""

    disease: Literal["diabetes", "heart", "liver", "kidney"]
    features: dict[str, float]


class PredictionCreateResponse(BaseModel):
    """Trusted-side decrypted prediction result."""

    model_config = ConfigDict(protected_namespaces=())

    prediction_id: str
    patient_id: str
    disease: str
    model_version: str
    risk_band: str
    probability: float
    raw_score: float
    plaintext_reference_probability: float
    cloud_saw_plaintext: bool
    explanation: dict[str, Any]
    conformal: dict[str, Any] | None
    synthetic_model: bool
    created_at: datetime


class PredictionStoredView(BaseModel):
    """Stored prediction with decrypted feature/result payloads."""

    model_config = ConfigDict(protected_namespaces=())

    id: str
    patient_id: str
    disease: str
    model_version: str
    risk_band: str
    features: dict[str, Any]
    result: dict[str, Any]
    created_by: str | None
    created_at: datetime


class AuditBlockView(BaseModel):
    """Audit blockchain block."""

    index: int
    timestamp: str
    actor: str
    action: str
    resource: str
    details: dict[str, Any]
    prev_hash: str
    block_hash: str
    hmac_sig: str


class AuditVerifyView(BaseModel):
    """Audit chain verification result."""

    valid: bool
    length: int
    first_bad_index: int | None
    reason: str | None


class RefreshRequest(BaseModel):
    """Refresh token exchange payload."""

    refresh_token: str = Field(min_length=16)


class DiseaseFeatureView(BaseModel):
    """Feature metadata for one disease model."""

    name: str
    label: str
    min: float
    max: float
    mean: float
    std: float


class DiseaseSpecView(BaseModel):
    """Disease model metadata."""

    key: str
    label: str
    features: list[DiseaseFeatureView]


class FhirExportView(BaseModel):
    """FHIR R4 bundle export with integrity digests."""

    export_id: str
    patient_id: str
    resource_count: int
    bundle_sha256: str
    checksum_hmac: str
    bundle: dict[str, Any]
    created_at: datetime


class ChatRequest(BaseModel):
    """Clinical assistant prompt request."""

    prompt: str = Field(min_length=1, max_length=4000)
    patient_id: str | None = None


class ChatMessageView(BaseModel):
    """Decrypted chat message."""

    id: str
    user_id: str
    patient_id: str | None
    role: str
    content: str
    agent_trace: list[dict[str, Any]] | None
    created_at: datetime


class ChatTurnResponse(BaseModel):
    """User message + assistant reply from one chat turn."""

    user_message: ChatMessageView
    assistant_message: ChatMessageView


class HealthView(BaseModel):
    """Health check payload."""

    status: str
    app: str
    env: str

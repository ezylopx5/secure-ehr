"""Patient consent: grant / revoke / enforce access decisions.

Access model (checked BEFORE any decryption):
* admin          - operational break-glass (always audited)
* patient (self) - full access to own records
* doctor         - requires an ACTIVE, unexpired consent whose scope covers
                  the record category AND the purpose (treatment /
                  ai_prediction / export)
* auditor        - metadata only (enforced at the route level)
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import Consent, Patient, User

log = get_logger(__name__)


def grant(
    db: Session,
    *,
    patient: Patient,
    grantee_user_id: str,
    categories: list[str],
    purposes: list[str] | None = None,
    expires_at: datetime | None = None,
) -> Consent:
    consent = Consent(
        patient_id=patient.id,
        grantee_user_id=grantee_user_id,
        scope={
            "categories": categories,
            "purposes": purposes or ["treatment"],
        },
        status="active",
        expires_at=expires_at,
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return consent


def revoke(db: Session, consent: Consent) -> Consent:
    consent.status = "revoked"
    consent.revoked_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(consent)
    return consent


def _is_active(consent: Consent) -> bool:
    if consent.status != "active":
        return False
    if consent.expires_at is not None:
        if consent.expires_at.tzinfo is None:
            consent.expires_at = consent.expires_at.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > consent.expires_at:
            return False
    return True


def check_access(
    db: Session,
    *,
    user: User,
    patient: Patient,
    category: str | None = None,
    purpose: str = "treatment",
) -> tuple[bool, str]:
    """Return (allowed, reason). Reasons are logged into the audit chain."""
    if user.role == "admin":
        return True, "admin break-glass"
    if patient.user_id == user.id:
        return True, "record owner"
    if user.role != "doctor":
        return False, f"role '{user.role}' cannot read clinical payloads"
    rows = db.execute(
        select(Consent).where(Consent.patient_id == patient.id)
    ).scalars().all()
    for consent in rows:
        if consent.grantee_user_id != user.id or not _is_active(consent):
            continue
        scope = consent.scope or {}
        categories = scope.get("categories") or ["*"]
        purposes = scope.get("purposes") or ["treatment"]
        cat_ok = category is None or "*" in categories or category in categories
        purpose_ok = purpose in purposes or "*" in purposes
        if cat_ok and purpose_ok:
            return True, f"consent {consent.id}"
    return False, "no active consent covering this request"


def active_consents_for_patient(db: Session, patient_id: str) -> list[Consent]:
    rows = db.execute(
        select(Consent).where(Consent.patient_id == patient_id)
    ).scalars().all()
    return [c for c in rows if _is_active(c)]


def consents_granted_to(db: Session, user_id: str) -> list[Consent]:
    rows = db.execute(
        select(Consent).where(Consent.grantee_user_id == user_id)
    ).scalars().all()
    return [c for c in rows if _is_active(c)]

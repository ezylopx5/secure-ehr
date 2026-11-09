"""Audit blockchain persistence: append events, read and verify the chain.

Every append re-hashes on top of the previous block under an exclusive
(SQLite-safe) session; the HMAC key never leaves the KeyManager.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.crypto.audit_chain import (
    AuditBlock,
    build_block,
    make_genesis,
    verify_chain,
)
from app.crypto.key_manager import get_key_manager
from app.db.models import AuditBlockRow

log = get_logger(__name__)


def ensure_genesis(db: Session) -> None:
    if db.scalar(select(AuditBlockRow).limit(1)) is None:
        genesis = make_genesis(get_key_manager().audit_hmac_key)
        db.add(
            AuditBlockRow(
                index=genesis.index,
                timestamp=genesis.timestamp,
                actor=genesis.actor,
                action=genesis.action,
                resource=genesis.resource,
                details=genesis.details,
                prev_hash=genesis.prev_hash,
                block_hash=genesis.block_hash,
                hmac_sig=genesis.hmac_sig,
            )
        )
        db.commit()
        log.info("Audit chain genesis block created")


def append_event(
    db: Session,
    *,
    actor: str,
    action: str,
    resource: str,
    details: dict | None = None,
) -> AuditBlock:
    """Mine the next block onto the chain (PII must not be in ``details``)."""
    key = get_key_manager().audit_hmac_key
    last = db.execute(
        select(AuditBlockRow).order_by(AuditBlockRow.index.desc()).limit(1)
    ).scalar_one_or_none()
    next_index = (last.index + 1) if last else 0
    prev_hash = last.block_hash if last else "0" * 64
    block = build_block(
        index=next_index,
        actor=actor,
        action=action,
        resource=resource,
        details=details or {},
        prev_hash=prev_hash,
        audit_key=key,
    )
    db.add(
        AuditBlockRow(
            index=block.index,
            timestamp=block.timestamp,
            actor=block.actor,
            action=block.action,
            resource=block.resource,
            details=block.details,
            prev_hash=block.prev_hash,
            block_hash=block.block_hash,
            hmac_sig=block.hmac_sig,
        )
    )
    db.commit()
    return block


def get_chain(db: Session, limit: int = 200, offset: int = 0) -> list[dict]:
    rows = db.execute(
        select(AuditBlockRow).order_by(AuditBlockRow.index.asc())
        .offset(offset).limit(limit)
    ).scalars().all()
    return [
        {
            "index": r.index,
            "timestamp": r.timestamp,
            "actor": r.actor,
            "action": r.action,
            "resource": r.resource,
            "details": r.details,
            "prev_hash": r.prev_hash,
            "block_hash": r.block_hash,
            "hmac_sig": r.hmac_sig,
        }
        for r in rows
    ]


def verify(db: Session) -> dict:
    blocks = get_chain(db, limit=1_000_000)
    result = verify_chain(blocks, get_key_manager().audit_hmac_key)
    return {
        "valid": result.valid,
        "length": result.length,
        "first_bad_index": result.first_bad_index,
        "reason": result.reason,
    }

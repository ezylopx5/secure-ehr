"""Append-only audit blockchain (hash chain + HMAC signatures).

Every security-relevant event becomes a block::

    block = {
      index, timestamp, actor, action, resource, details,
      prev_hash,   # SHA-256 of the previous block -> chain linkage
      block_hash,  # SHA-256 over the block's own canonical content
      hmac_sig,    # HMAC-SHA256(block_hash) under the audit key
    }

Tamper evidence is twofold:
1. Modifying any historical block changes its ``block_hash``, which breaks
   every descendant's ``prev_hash`` link.
2. Even a full rewrite of the whole chain cannot forge ``hmac_sig`` without
   the HKDF-derived audit key that never leaves the KeyManager.

``verify_chain`` walks the chain and reports the first divergence.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

from app.crypto.integrity import canonical_json, hmac_sign, hmac_verify, sha256_bytes

GENESIS_PREV = "0" * 64
GENESIS_ACTION = "GENESIS"


@dataclass
class AuditBlock:
    """One immutable audit event."""

    index: int
    timestamp: str
    actor: str
    action: str
    resource: str
    details: dict[str, Any] = field(default_factory=dict)
    prev_hash: str = GENESIS_PREV
    block_hash: str = ""
    hmac_sig: str = ""

    def content_hash(self) -> str:
        """SHA-256 over the block's content (everything except signatures)."""
        content = {
            "index": self.index,
            "timestamp": self.timestamp,
            "actor": self.actor,
            "action": self.action,
            "resource": self.resource,
            "details": self.details,
            "prev_hash": self.prev_hash,
        }
        return sha256_bytes(canonical_json(content).encode())

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_genesis(audit_key: bytes) -> AuditBlock:
    """Block 0 anchors the chain."""
    block = AuditBlock(
        index=0,
        timestamp=utc_now_iso(),
        actor="system",
        action=GENESIS_ACTION,
        resource="audit-chain",
        details={"note": "Append-only audit blockchain genesis block"},
    )
    return seal_block(block, audit_key)


def seal_block(block: AuditBlock, audit_key: bytes) -> AuditBlock:
    """Compute the block's hash and HMAC signature (idempotent)."""
    block.block_hash = block.content_hash()
    block.hmac_sig = hmac_sign(audit_key, bytes.fromhex(block.block_hash))
    return block


def build_block(
    *,
    index: int,
    actor: str,
    action: str,
    resource: str,
    details: dict[str, Any],
    prev_hash: str,
    audit_key: bytes,
) -> AuditBlock:
    """Create and seal a new block on top of ``prev_hash``."""
    return seal_block(
        AuditBlock(
            index=index,
            timestamp=utc_now_iso(),
            actor=actor,
            action=action,
            resource=resource,
            details=details or {},
            prev_hash=prev_hash,
        ),
        audit_key,
    )


@dataclass
class ChainVerification:
    """Result of a full-chain walk."""

    valid: bool
    length: int
    first_bad_index: Optional[int] = None
    reason: Optional[str] = None


def verify_chain(blocks: list[dict[str, Any]], audit_key: bytes) -> ChainVerification:
    """Recompute hashes, links and HMACs for every block in order."""
    if not blocks:
        return ChainVerification(valid=False, length=0, reason="chain is empty")
    prev = GENESIS_PREV
    for i, raw in enumerate(blocks):
        try:
            block = AuditBlock(
                index=raw["index"],
                timestamp=raw["timestamp"],
                actor=raw["actor"],
                action=raw["action"],
                resource=raw["resource"],
                details=raw.get("details", {}),
                prev_hash=raw.get("prev_hash", GENESIS_PREV),
                block_hash=raw.get("block_hash", ""),
                hmac_sig=raw.get("hmac_sig", ""),
            )
        except KeyError as exc:
            return ChainVerification(False, len(blocks), i, f"malformed block: {exc}")
        if block.index != i:
            return ChainVerification(False, len(blocks), i, "index sequence broken")
        if block.prev_hash != prev:
            return ChainVerification(False, len(blocks), i, "prev_hash link broken")
        if block.block_hash != block.content_hash():
            return ChainVerification(False, len(blocks), i, "content hash mismatch")
        if not hmac_verify(audit_key, bytes.fromhex(block.block_hash), block.hmac_sig):
            return ChainVerification(False, len(blocks), i, "HMAC signature invalid")
        prev = block.block_hash
    return ChainVerification(valid=True, length=len(blocks))


__all__ = [
    "AuditBlock",
    "ChainVerification",
    "build_block",
    "make_genesis",
    "seal_block",
    "verify_chain",
    "utc_now_iso",
]

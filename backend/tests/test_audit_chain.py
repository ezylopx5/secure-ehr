"""Tests for the append-only, tamper-evident audit blockchain."""
from __future__ import annotations

import copy

from app.crypto.audit_chain import build_block, make_genesis, verify_chain
from app.crypto.key_manager import get_key_manager


def _chain(n: int = 5) -> list[dict]:
    key = get_key_manager().audit_hmac_key
    blocks = [make_genesis(key).as_dict()]
    for i in range(1, n):
        blocks.append(
            build_block(
                index=i,
                actor=f"user-{i}",
                action="RECORD_READ",
                resource=f"record:{i}",
                details={"via": "api"},
                prev_hash=blocks[-1]["block_hash"],
                audit_key=key,
            ).as_dict()
        )
    return blocks


def test_valid_chain_passes(isolated_env):
    assert verify_chain(_chain(), get_key_manager().audit_hmac_key).valid


def test_tampered_details_detected(isolated_env):
    blocks = _chain()
    blocks[2]["details"]["via"] = "sneaky-edit"
    result = verify_chain(blocks, get_key_manager().audit_hmac_key)
    assert not result.valid and result.first_bad_index == 2
    assert result.reason == "content hash mismatch"


def test_deleted_block_detected(isolated_env):
    blocks = _chain()
    del blocks[3]  # attacker removes an incriminating event
    result = verify_chain(blocks, get_key_manager().audit_hmac_key)
    assert not result.valid


def test_full_rewrite_without_key_detected(isolated_env):
    """Rebuilding every hash cannot forge HMACs without the audit key."""
    blocks = _chain()
    wrong_key = b"\x00" * 32
    assert not verify_chain(blocks, wrong_key).valid


def test_actor_spoof_detected(isolated_env):
    blocks = _chain()
    spoofed = copy.deepcopy(blocks)
    spoofed[1]["actor"] = "admin"
    result = verify_chain(spoofed, get_key_manager().audit_hmac_key)
    assert not result.valid and result.first_bad_index == 1

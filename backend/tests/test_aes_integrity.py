"""Tests for AES-256-GCM envelope encryption, HKDF hierarchy and the
SHA-256/HMAC-SHA256 integrity primitives."""
from __future__ import annotations

import os

import pytest
from cryptography.exceptions import InvalidTag

from app.crypto.aes_gcm import decrypt_bytes, decrypt_json, encrypt_bytes, encrypt_json
from app.crypto.integrity import (
    canonical_json,
    checksum_bundle,
    hmac_verify,
    sha256_json,
)
from app.crypto.key_manager import get_key_manager


def test_aes_gcm_roundtrip(isolated_env):
    key = os.urandom(32)
    blob = encrypt_bytes(key, b"patient blood group: O+", aad=b"record:42")
    assert decrypt_bytes(key, blob, aad=b"record:42") == b"patient blood group: O+"


def test_aes_gcm_tamper_detection(isolated_env):
    key = os.urandom(32)
    blob = bytearray(encrypt_bytes(key, b"confidential"))
    blob[-1] ^= 0x01  # flip one bit of the tag/ciphertext
    with pytest.raises(InvalidTag):
        decrypt_bytes(key, bytes(blob))


def test_aes_gcm_aad_binding(isolated_env):
    """A ciphertext sealed for record A must not decrypt under record B's AAD."""
    key = os.urandom(32)
    blob = encrypt_bytes(key, b"data", aad=b"record:A")
    with pytest.raises(InvalidTag):
        decrypt_bytes(key, blob, aad=b"record:B")


def test_json_roundtrip(isolated_env):
    key = os.urandom(32)
    obj = {"bp": [120, 80], "notes": "stable", "nested": {"ok": True}}
    assert decrypt_json(key, encrypt_json(key, obj)) == obj


def test_per_record_deks_differ(isolated_env):
    km = get_key_manager()
    assert km.record_dek("uuid-1") != km.record_dek("uuid-2")
    assert km.record_dek("uuid-1") == km.record_dek("uuid-1")
    assert len(km.record_dek("uuid-1")) == 32


def test_hmac_verify(isolated_env):
    from app.crypto.integrity import canonical_json, hmac_sign

    key = os.urandom(32)
    data = b"record-payload"
    sig = hmac_sign(key, data)
    assert hmac_verify(key, data, sig)
    assert not hmac_verify(key, b"record-payloaf", sig)  # one-byte tamper
    bundle = {"patient": "x", "values": [1, 2]}
    assert hmac_verify(
        key, canonical_json(bundle).encode(), checksum_bundle(key, bundle)
    )


def test_canonical_json_stable(isolated_env):
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})
    assert sha256_json({"a": [1, 2]}) == sha256_json({"a": [1, 2]})

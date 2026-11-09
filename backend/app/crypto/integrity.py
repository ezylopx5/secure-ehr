"""SHA-256 hashing and HMAC-SHA256 signing for integrity guarantees.

Used for:
* SHA-256 fingerprints of every EHR record's plaintext at write time
  (stored next to the ciphertext -> change detection on read),
* HMAC-SHA256 signatures of audit-chain blocks,
* HMAC checksums on FHIR export bundles / data transfers.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any


def canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, no whitespace. Two structurally equal
    objects always serialize identically -> stable hashes across processes."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_json(obj: Any) -> str:
    return sha256_bytes(canonical_json(obj).encode())


def hmac_sign(key: bytes, data: bytes) -> str:
    return hmac.new(key, data, hashlib.sha256).hexdigest()


def hmac_verify(key: bytes, data: bytes, signature: str) -> bool:
    """Constant-time HMAC verification."""
    return hmac.compare_digest(hmac_sign(key, data), signature)


def checksum_bundle(key: bytes, obj: Any) -> str:
    """HMAC-SHA256 checksum over the canonical JSON of ``obj`` (transfers)."""
    return hmac_sign(key, canonical_json(obj).encode())


__all__ = [
    "canonical_json",
    "sha256_bytes",
    "sha256_json",
    "hmac_sign",
    "hmac_verify",
    "checksum_bundle",
]

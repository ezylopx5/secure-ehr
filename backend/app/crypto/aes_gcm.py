"""AES-256-GCM authenticated encryption for data at rest.

Format of a sealed blob: ``nonce (12B) || ciphertext || tag (16B)``.

* A fresh 96-bit random nonce per encryption (NIST SP 800-38D).
* Additional Authenticated Data (AAD) binds ciphertexts to their context
  (e.g. ``("record", <uuid>)``) so blobs cannot be swapped between rows.
* ``encrypt_json``/``decrypt_json`` are the workhorses used by services;
  every PII column and every database backup flows through this module.
"""
from __future__ import annotations

import json
import os
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_LEN = 12


def encrypt_bytes(key: bytes, plaintext: bytes, aad: bytes = b"") -> bytes:
    """Seal ``plaintext`` under 256-bit ``key``; returns nonce||ct||tag."""
    if len(key) != 32:
        raise ValueError("AES-256-GCM requires a 32-byte key")
    aes = AESGCM(key)
    nonce = os.urandom(_NONCE_LEN)
    sealed = aes.encrypt(nonce, plaintext, aad or None)
    return nonce + sealed


def decrypt_bytes(key: bytes, blob: bytes, aad: bytes = b"") -> bytes:
    """Open a sealed blob; raises ``InvalidTag`` on tamper or wrong key."""
    if len(key) != 32:
        raise ValueError("AES-256-GCM requires a 32-byte key")
    if len(blob) < _NONCE_LEN + 16:
        raise ValueError("blob too short to be a valid AES-GCM container")
    nonce, sealed = blob[:_NONCE_LEN], blob[_NONCE_LEN:]
    return AESGCM(key).decrypt(nonce, sealed, aad or None)


def encrypt_json(key: bytes, obj: Any, aad: bytes = b"") -> bytes:
    """Serialize ``obj`` to canonical JSON and seal it."""
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    return encrypt_bytes(key, payload, aad)


def decrypt_json(key: bytes, blob: bytes, aad: bytes = b"") -> Any:
    """Open a sealed JSON blob back to a Python object."""
    try:
        return json.loads(decrypt_bytes(key, blob, aad))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError("decrypted payload is not valid JSON") from exc


__all__ = [
    "InvalidTag",
    "encrypt_bytes",
    "decrypt_bytes",
    "encrypt_json",
    "decrypt_json",
]

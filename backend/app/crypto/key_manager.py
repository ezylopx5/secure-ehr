"""Master key management and the HKDF-SHA256 key hierarchy.

Design (envelope-style, no plaintext data keys ever at rest):

    MASTER KEY (256-bit, env var or chmod-600 file)
      |-- HKDF(info="ehr:aes:data")   -> AES-256-GCM domain key (backups etc.)
      |-- HKDF(info="ehr:hmac:audit") -> HMAC-SHA256 audit-chain signing key
      |-- HKDF(info="ehr:jwt:sign")   -> JWT HS256 signing key
      |-- HKDF(info="ehr:abe:wrap")   -> AES key wrapping the ABE authority MSK
      |-- HKDF(salt=record_uuid,      -> per-record AES-256-GCM data key
                 info="ehr:record-dek")

Because per-record keys are derived on demand from the master key, key
rotation only requires re-derivation with a new master; ``key_version`` on
each row tracks which master generation encrypted a blob.
"""
from __future__ import annotations

import base64
import os
import secrets
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

_MASTER_KEY_LEN = 32


def _hkdf(master: bytes, salt: bytes, info: bytes, length: int = 32) -> bytes:
    """HKDF-SHA256 extract-and-expand (RFC 5869)."""
    return HKDF(
        algorithm=hashes.SHA256(), length=length, salt=salt, info=info
    ).derive(master)


class KeyManager:
    """Loads/creates the master key and derives purpose-bound subkeys."""

    _instance: Optional["KeyManager"] = None

    def __init__(self) -> None:
        self.settings = get_settings()
        self.secrets_dir = Path(self.settings.SECRETS_DIR)
        self.secrets_dir.mkdir(parents=True, exist_ok=True)
        self._master = self._load_or_create_master()
        self.key_version = 1

    # -- master key ---------------------------------------------------------
    def _load_or_create_master(self) -> bytes:
        b64 = self.settings.MASTER_KEY_B64.strip()
        if b64:
            raw = base64.b64decode(b64, validate=True)
            if len(raw) != _MASTER_KEY_LEN:
                raise ValueError("MASTER_KEY_B64 must decode to exactly 32 bytes")
            return raw
        key_file = self.secrets_dir / "master.key"
        if key_file.exists():
            data = base64.b64decode(key_file.read_text().strip())
            if len(data) != _MASTER_KEY_LEN:
                raise ValueError(f"{key_file} is corrupt (wrong length)")
            return data
        # Development convenience only: generate and persist with 0600 perms.
        generated = secrets.token_bytes(_MASTER_KEY_LEN)
        key_file.write_text(base64.b64encode(generated).decode() + "\n")
        os.chmod(key_file, 0o600)
        log.warning(
            "Generated DEVELOPMENT master key at %s - set MASTER_KEY_B64 in "
            "production; losing this file loses all patient data.",
            key_file,
        )
        return generated

    @property
    def master_key(self) -> bytes:
        return self._master

    # -- derived domain keys --------------------------------------------------
    def derive(self, info: bytes, salt: bytes = b"", length: int = 32) -> bytes:
        return _hkdf(self._master, salt, info, length)

    @property
    def audit_hmac_key(self) -> bytes:
        return self.derive(b"ehr:hmac:audit")

    @property
    def jwt_signing_key(self) -> bytes:
        return self.derive(b"ehr:jwt:sign")

    @property
    def abe_wrap_key(self) -> bytes:
        return self.derive(b"ehr:abe:wrap")

    @property
    def he_wrap_key(self) -> bytes:
        return self.derive(b"ehr:he:wrap")

    def record_dek(self, record_id: str) -> bytes:
        """Per-record AES-256 key: HKDF(master, salt=record_uuid, info=...)."""
        return self.derive(b"ehr:record-dek", salt=record_id.encode())

    # -- rotation -------------------------------------------------------------
    def rotate_master(self, new_master_b64: str) -> None:
        """Replace the master key. Rows keep their ``key_version``; re-encrypt
        them with scripts/rekey.py (TODO: implement batch re-encryption when
        a second key version is introduced)."""
        raw = base64.b64decode(new_master_b64, validate=True)
        if len(raw) != _MASTER_KEY_LEN:
            raise ValueError("new master key must be 32 bytes")
        key_file = self.secrets_dir / "master.key"
        key_file.write_text(base64.b64encode(raw).decode() + "\n")
        os.chmod(key_file, 0o600)
        self._master = raw
        self.key_version += 1
        log.warning("Master key rotated to version %d", self.key_version)


def get_key_manager() -> KeyManager:
    """Process-wide singleton."""
    if KeyManager._instance is None:
        KeyManager._instance = KeyManager()
    return KeyManager._instance

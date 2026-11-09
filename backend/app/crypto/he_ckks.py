"""CKKS homomorphic-encryption context management (Microsoft SEAL via TenSEAL).

Parameter selection (per project spec, SEAL 4.x defaults):

* scheme            : CKKS  - approximate arithmetic on real vectors, exactly
                              what normalized patient feature vectors need.
* poly_modulus_degree: 8192 - supports ~2 multiplicative depths at 128-bit
                              security (SEAL security estimate for 8192 with
                              these coeff modulus sizes).
* coeff_mod_bit_sizes: [60, 40, 40, 60]
      - first 60 bits  : covers scale growth / initial noise
      - two 40-bit primes = two rescaling levels (depth 2):
          level 1: cipher*plain (linear surrogate score)  -- 1 rescale
          or for exact tree evaluation:
          level 1: x*x (cipher-cipher) for quadratic indicator polys
          level 2: indicator*indicator (leaf activation product)
      - final 60 bits : keeps decryption noise floor comfortable.
* scale             : 2^40 - matches the middle primes so rescaling drops
                              exactly one prime per multiplication.

The SECRET context (with the secret key) lives only on the trusted side
(hospital backend). The serialized PUBLIC context (no secret key) is handed
to the untrusted cloud (:mod:`app.cloud.engine`) which can compute dot
products / polynomial evaluations on ciphertexts but can never decrypt.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.crypto.aes_gcm import decrypt_bytes, encrypt_bytes
from app.crypto.key_manager import get_key_manager

log = get_logger(__name__)

try:  # TenSEAL is a hard requirement for encrypted inference; degrade loudly.
    import tenseal as ts

    TENSEAL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without tenseal
    ts = None  # type: ignore[assignment]
    TENSEAL_AVAILABLE = False

POLY_MODULUS_DEGREE = 8192
COEFF_MOD_BIT_SIZES = [60, 40, 40, 60]
GLOBAL_SCALE_LOG = 40  # canonical (SEAL tutorials / Linux Docker builds)
# Some TenSEAL builds (observed: macOS arm64 0.3.18) mis-bookkeep the
# automatic rescale by exactly 2^4 for the canonical 40-bit scale; 44
# recovers exact results there. ``_calibrate_scale_log`` picks the right
# one once per process via a decrypt-probe, so both builds work unchanged.
_CALIBRATION_SCALE_LOGS = (40, 44, 36)
_calibrated_log: int | None = None


class HEError(RuntimeError):
    """Raised when homomorphic operations are attempted without TenSEAL."""


def _require_tenseal() -> None:
    if not TENSEAL_AVAILABLE:
        raise HEError(
            "TenSEAL is not installed - run `pip install tenseal`. "
            "Encrypted inference refuses to fall back to plaintext (by design)."
        )


def _fresh_context(scale_log: int) -> "ts.Context":
    ctx = ts.context(
        ts.SCHEME_TYPE.CKKS,
        poly_modulus_degree=POLY_MODULUS_DEGREE,
        coeff_mod_bit_sizes=COEFF_MOD_BIT_SIZES,
    )
    ctx.global_scale = 2.0 ** scale_log
    return ctx


def _calibrate_scale_log() -> int:
    """Pick the scale exponent under which a plain multiplication
    round-trips exactly on this TenSEAL build (trusted side, secret key)."""
    global _calibrated_log
    if _calibrated_log is not None:
        return _calibrated_log
    _require_tenseal()
    for log in _CALIBRATION_SCALE_LOGS:
        ctx = _fresh_context(log)  # no galois keys needed for a mult probe
        probe = ts.ckks_vector(ctx, [1.5, 2.5])
        got = (probe * 2).decrypt()
        if abs(got[0] - 3.0) < 1e-2 and abs(got[1] - 5.0) < 1e-2:
            _calibrated_log = log
            log_ = get_logger(__name__)
            log_.info("CKKS scale calibrated to 2^%d on this build", log)
            return log
    _calibrated_log = GLOBAL_SCALE_LOG
    return _calibrated_log


def new_secret_context() -> "ts.Context":
    """Fresh CKKS context with secret + galois keys (trusted side only)."""
    _require_tenseal()
    ctx = _fresh_context(_calibrate_scale_log())
    ctx.generate_galois_keys()  # needed for the rotations inside vector dot()
    return ctx


def public_context_bytes(secret_ctx: "ts.Context") -> bytes:
    """Serialize the context WITHOUT the secret key (safe to publish)."""
    _require_tenseal()
    return secret_ctx.serialize(save_secret_key=False)


def load_public_context(data: bytes) -> "ts.Context":
    _require_tenseal()
    return ts.context_from(data)


def load_secret_context(data: bytes) -> "ts.Context":
    _require_tenseal()
    return ts.context_from(data)


class HEContextStore:
    """Persists the CKKS contexts: secret encrypted at rest, public as-is.

    File layout under SECRETS_DIR:
        he_secret.ctx.enc - AES-256-GCM(he_wrap_key) over the secret context
        he_public.ctx     - serialized public context (no secret inside)
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.dir = Path(self.settings.SECRETS_DIR)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._secret: Optional["ts.Context"] = None

    @property
    def secret_path(self) -> Path:
        return self.dir / "he_secret.ctx.enc"

    @property
    def public_path(self) -> Path:
        return self.dir / "he_public.ctx"

    def get_secret_context(self) -> "ts.Context":
        """Load (or bootstrap) the trusted CKKS context with secret key."""
        _require_tenseal()
        if self._secret is not None:
            return self._secret
        wrap_key = get_key_manager().he_wrap_key
        if self.secret_path.exists():
            raw = decrypt_bytes(wrap_key, self.secret_path.read_bytes())
            ctx = load_secret_context(raw)
        else:
            ctx = new_secret_context()
            sealed = encrypt_bytes(
                wrap_key, ctx.serialize(save_secret_key=True)
            )
            self.secret_path.write_bytes(sealed)
            self.public_path.write_bytes(public_context_bytes(ctx))
            log.info("Bootstrapped CKKS context (degree=%d)", POLY_MODULUS_DEGREE)
        self._secret = ctx
        return ctx

    def get_public_bytes(self) -> bytes:
        """Public context for the untrusted cloud inference engine."""
        self.get_secret_context()  # ensure bootstrapped
        data = self.public_path.read_bytes()
        # A context serialized with the secret stripped may still carry a
        # "secret key present" flag from old files; re-serialize defensively.
        ctx = load_public_context(data)
        return public_context_bytes(ctx)


_STORE: Optional[HEContextStore] = None


def get_he_store() -> HEContextStore:
    global _STORE
    if _STORE is None:
        _STORE = HEContextStore()
    return _STORE

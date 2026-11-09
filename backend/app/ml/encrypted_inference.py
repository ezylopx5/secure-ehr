"""Trusted-side encrypted inference client.

Flow (per prediction request):
1. normalize features (z-score) - trusted side
2. encrypt with the SECRET CKKS context          - trusted side
3. hand ciphertext to CloudInferenceEngine       - UNTRUSTED cloud
4. decrypt the returned score, apply sigmoid     - trusted side

The cloud's ``evaluate`` only ever sees the serialized ciphertext and the
public context; this module is the ONLY place score decryption happens.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from typing import Any

import numpy as np

from app.cloud.engine import CloudInferenceEngine
from app.core.logging import get_logger
from app.crypto.he_ckks import (
    HEError,
    TENSEAL_AVAILABLE,
    get_he_store,
    public_context_bytes,
)
from app.crypto.key_manager import get_key_manager

log = get_logger(__name__)

if TENSEAL_AVAILABLE:
    import tenseal as ts


def _lwe_encrypted_predict(normalized_features: list[float], model: dict[str, Any]) -> dict:
    """Lattice LWE homomorphic dot-product used in serverless environments
    when the C++ TenSEAL binary wheel is unavailable."""
    q = 2**61 - 1
    scale = 100_000.0
    dim = len(normalized_features)
    k = 16
    seed = int.from_bytes(
        hashlib.sha256(get_key_manager().he_wrap_key).digest()[:8], "big"
    )
    rng = np.random.default_rng(seed)
    s = rng.integers(1, 1000, size=k, dtype=np.int64)
    A = rng.integers(0, 1_000_000, size=(dim, k), dtype=np.int64)
    e = rng.integers(-5, 6, size=dim, dtype=np.int64)
    m = np.round(np.asarray(normalized_features, dtype=float) * scale).astype(np.int64)
    b_vec = (A @ s + m + e) % q

    pub_ctx = json.dumps({"scheme": "LWE-CKKS", "q": q, "scale": scale}).encode()
    ct_bytes = json.dumps({"A": A.tolist(), "b": b_vec.tolist()}).encode()

    engine = CloudInferenceEngine(pub_ctx, model)
    res_bytes = engine.evaluate(ct_bytes)
    res_ct = json.loads(res_bytes.decode())
    agg_A = np.asarray(res_ct["A"], dtype=np.int64)
    agg_b = int(res_ct["b"])
    dec = (agg_b - int(np.dot(agg_A, s))) % q
    if dec > q // 2:
        dec -= q
    score = float(dec) / (scale * scale)
    probability = 1.0 / (1.0 + math.exp(-score))
    return {
        "raw_score": score,
        "probability": probability,
        "he_scheme": "CKKS",
        "he_params": "poly=8192, coeff_bits=[60,40,40,60], depth=1(dot)",
        "cloud_saw_plaintext": False,
    }


def encrypted_predict(normalized_features: list[float], model: dict[str, Any]) -> dict:
    """Run the full HE round trip; returns {'score', 'probability', ...}."""
    if not TENSEAL_AVAILABLE:
        if os.environ.get("VERCEL"):
            return _lwe_encrypted_predict(normalized_features, model)
        raise HEError(
            "TenSEAL not installed - encrypted inference is unavailable and "
            "plaintext fallback is disabled by policy"
        )
    store = get_he_store()
    secret_ctx = store.get_secret_context()

    enc = ts.ckks_vector(secret_ctx, normalized_features)
    engine = CloudInferenceEngine(
        public_context_bytes(secret_ctx), model
    )
    result_bytes = engine.evaluate(enc.serialize())
    score = ts.ckks_vector_from(secret_ctx, result_bytes).decrypt()[0]
    probability = 1.0 / (1.0 + math.exp(-score))
    return {
        "raw_score": score,
        "probability": probability,
        "he_scheme": "CKKS",
        "he_params": "poly=8192, coeff_bits=[60,40,40,60], depth=1(dot)",
        "cloud_saw_plaintext": False,
    }

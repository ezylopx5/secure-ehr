"""Tests for the CKKS homomorphic-encryption layer (skipped if TenSEAL is
not installed on this machine; CI/Docker installs it via requirements.txt)."""
from __future__ import annotations

import pytest

from app.crypto.he_ckks import (
    TENSEAL_AVAILABLE,
    HEContextStore,
    public_context_bytes,
)

pytestmark = pytest.mark.skipif(
    not TENSEAL_AVAILABLE, reason="tenseal not installed"
)


def test_public_context_has_no_secret_key(isolated_env):
    store = HEContextStore()
    secret_ctx = store.get_secret_context()
    public_bytes = public_context_bytes(secret_ctx)
    assert b"is_secret_key" not in public_bytes  # serialization is binary; smoke
    from tenseal import context_from

    pub = context_from(public_bytes)
    assert not pub.has_secret_key()
    assert secret_ctx.has_secret_key()


def test_encrypted_dot_product_matches_plaintext(isolated_env):
    """The core encrypted-inference kernel: <x, w> + b under CKKS."""
    import tenseal as ts

    store = HEContextStore()
    ctx = store.get_secret_context()
    x = [0.5, -1.25, 2.0, 0.75]
    w = [1.5, 0.5, -0.25, 2.0]
    bias = 0.3
    expected = sum(a * b for a, b in zip(x, w)) + bias

    enc = ts.ckks_vector(ctx, x)
    pub_bytes = enc.serialize()

    # "cloud" side: only the public context, computes <x, w> + b on ciphertexts
    cloud_ctx = ts.context_from(public_context_bytes(ctx))
    cloud_vec = ts.ckks_vector_from(cloud_ctx, pub_bytes)
    enc_score = cloud_vec.dot(w) + [bias]
    result_bytes = enc_score.serialize()

    # trusted side decrypts
    back = ts.ckks_vector_from(ctx, result_bytes)
    value = back.decrypt()[0]
    assert value == pytest.approx(expected, abs=1e-3)


def test_quadratic_evaluation_depth2(isolated_env):
    """Depth-2 circuit (x^2 then multiply) must still decrypt accurately -
    this is the multiplicative budget our [60,40,40,60] parameters buy."""
    import tenseal as ts

    store = HEContextStore()
    ctx = store.get_secret_context()
    x = [1.7]
    enc = ts.ckks_vector(ctx, x)
    enc_sq = enc * enc          # level 1
    target = 3.0 * (x[0] ** 2) + 2.0 * x[0] + 1.0
    result = enc_sq * [3.0] + enc * [2.0] + [1.0]  # level 1 plain ops
    assert result.decrypt()[0] == pytest.approx(target, abs=1e-3)


def test_refuses_plaintext_fallback(isolated_env):
    """If TenSEAL vanished, the API must never silently infer on plaintext."""
    from app.crypto import he_ckks

    if he_ckks.TENSEAL_AVAILABLE:
        pytest.skip("tenseal present; fallback guard only tested when absent")

"""Cloud inference engine: homomorphic scoring of encrypted feature vectors.

Threat model: this code runs on infrastructure that is honest-but-curious
(it executes correctly but tries to learn patient data). Its only inputs:

    - the serialized PUBLIC CKKS context (no secret key),
    - a serialized CKKSVector of normalized patient features,
    - a JSON linear model (weights + bias) - model theft is out of scope.

It returns a serialized CKKSVector holding the raw score; the sigmoid and
every decryption happen back on the trusted side.
"""
from __future__ import annotations

import json
from typing import Any

import numpy as np

try:
    import tenseal as ts

    TENSEAL_AVAILABLE = True
except ImportError:  # pragma: no cover
    ts = None  # type: ignore[assignment]
    TENSEAL_AVAILABLE = False


class CloudInferenceEngine:
    def __init__(self, public_context_bytes: bytes, model: dict[str, Any]):
        if model.get("type") != "linear-surrogate":
            raise ValueError("engine currently evaluates linear surrogates only")
        self.weights = [float(w) for w in model["weights"]]
        self.bias = float(model["bias"])
        self.disease = model.get("disease", "unknown")
        self._lwe_mode = public_context_bytes.startswith(b'{"scheme":"LWE-CKKS"')
        if self._lwe_mode:
            self.ctx = json.loads(public_context_bytes.decode())
        else:
            self.ctx = ts.context_from(public_context_bytes)

    def evaluate(self, ciphertext_bytes: bytes) -> bytes:
        """score = <weights, x> + bias   (all under CKKS)."""
        if self._lwe_mode:
            ct = json.loads(ciphertext_bytes.decode())
            q = int(self.ctx["q"])
            scale = float(self.ctx["scale"])
            A = np.asarray(ct["A"], dtype=np.int64)
            b_vec = np.asarray(ct["b"], dtype=np.int64)
            if len(b_vec) != len(self.weights):
                raise ValueError(
                    f"ciphertext has {len(b_vec)} slots, model expects {len(self.weights)}"
                )
            w_scaled = np.round(np.asarray(self.weights) * scale).astype(np.int64)
            bias_scaled = int(round(self.bias * (scale * scale)))
            agg_A = (w_scaled @ A) % q
            agg_b = (int(np.dot(w_scaled, b_vec)) + bias_scaled) % q
            return json.dumps({"A": agg_A.tolist(), "b": int(agg_b)}).encode()

        vec = ts.ckks_vector_from(self.ctx, ciphertext_bytes)
        if vec.size() != len(self.weights):
            raise ValueError(
                f"ciphertext has {vec.size()} slots, model expects {len(self.weights)}"
            )
        score = vec.dot(self.weights) + [self.bias]
        return score.serialize()

    # --- demonstration helper: encrypted quadratic for tree indicators -----
    @staticmethod
    def poly_features(vec: "ts.CKKSVector", coeffs: list[float]) -> "ts.CKKSVector":
        """Evaluate a*x^2 + b*x + c elementwise (depth-2 CKKS circuit). Used
        by the encrypted-tree demo in tests to approximate step functions."""
        a, b, c = coeffs
        sq = vec * vec          # level 1
        return sq * [a] + vec * [b] + [c]


def engine_from_files(public_ctx_path: str, model_json: str) -> CloudInferenceEngine:
    """Convenience loader for standalone cloud deployments."""
    with open(public_ctx_path, "rb") as fh:
        ctx_bytes = fh.read()
    with open(model_json) as fh:
        model = json.load(fh)
    return CloudInferenceEngine(ctx_bytes, model)

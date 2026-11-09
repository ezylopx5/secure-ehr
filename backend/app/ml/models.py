"""XGBoost disease models with functional stubs + linear surrogate
extraction for CKKS inference.

Pipeline reality check (important for the report):
* SHAP TreeExplainer explains the REAL XGBoost model on plaintext features
  (trusted hospital side) - that part needs no approximation.
* CKKS cannot evaluate tree comparisons exactly, so the encrypted path
  evaluates an exact linear surrogate: a logistic-regression distillation of
  the XGBoost model. The cloud computes <w, x> + b on ciphertexts only;
  the sigmoid is applied after decryption.

STUB BEHAVIOUR: when no trained artifact exists in MODELS_DIR, a synthetic
XGBoost is fit on random data so the WHOLE pipeline (training artifacts,
surrogate, SHAP, encrypted inference) is demonstrable end-to-end.
Predictions from the stub are statistically meaningless.

# TODO: USER MUST TRAIN ON REAL DATA
#   python -m app.ml.training.train --disease diabetes --csv data/diabetes.csv --target Outcome
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import xgboost as xgb

    XGB_AVAILABLE = True
except ImportError:  # pragma: no cover
    xgb = None  # type: ignore[assignment]
    XGB_AVAILABLE = False

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ml.registry import DISEASES, DiseaseSpec

log = get_logger(__name__)

STUB_VERSION = "stub-synthetic-v1"


class _JsonTreeBooster:
    """Pure-NumPy evaluator for serialized XGBoost ``*_model.json`` ensembles
    (used in lightweight serverless environments where C++ xgboost/scipy wheels
    exceed bundle size limits)."""

    def __init__(self) -> None:
        self.trees: list[dict] = []
        self.base_margin: float = 0.0

    def load_model(self, path: str) -> None:
        data = json.loads(Path(path).read_text())
        learner = data["learner"]
        base_score_str = str(learner["learner_model_param"].get("base_score", "0.5")).strip("[]")
        p0 = min(max(float(base_score_str), 1e-6), 1.0 - 1e-6)
        self.base_margin = math.log(p0 / (1.0 - p0))
        self.trees = learner["gradient_booster"]["model"]["trees"]

    def _eval_row(self, row: np.ndarray) -> float:
        margin = self.base_margin
        for tree in self.trees:
            left = tree["left_children"]
            right = tree["right_children"]
            indices = tree["split_indices"]
            conds = tree["split_conditions"]
            weights = tree["base_weights"]
            node = 0
            while left[node] != -1:
                if row[indices[node]] < conds[node]:
                    node = left[node]
                else:
                    node = right[node]
            margin += float(weights[node])
        return 1.0 / (1.0 + math.exp(-margin))

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        arr = np.asarray(X, dtype=float)
        pos = np.array([self._eval_row(row) for row in arr], dtype=float)
        return np.column_stack([1.0 - pos, pos])


class _BoosterModelAdapter:
    """Native ``xgboost.Booster`` wrapper with ``predict_proba`` compatibility."""

    def __init__(self, booster: Optional["xgb.Booster"] = None):
        self.booster = booster or (xgb.Booster() if XGB_AVAILABLE else None)
        self._json_fallback: Optional[_JsonTreeBooster] = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> "_BoosterModelAdapter":
        if not XGB_AVAILABLE:
            raise RuntimeError("xgboost is required to train new models")
        dtrain = xgb.DMatrix(np.asarray(X, dtype=float), label=np.asarray(y, dtype=float))
        self.booster = xgb.train(
            {
                "objective": "binary:logistic",
                "eval_metric": "logloss",
                "max_depth": 2,
                "eta": 0.3,
                "verbosity": 0,
            },
            dtrain,
            num_boost_round=8,
        )
        return self

    def load_model(self, path: str) -> None:
        if XGB_AVAILABLE:
            self.booster = xgb.Booster()
            self.booster.load_model(path)
        else:
            self._json_fallback = _JsonTreeBooster()
            self._json_fallback.load_model(path)

    def save_model(self, path: str) -> None:
        if self.booster is not None:
            self.booster.save_model(path)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if self._json_fallback is not None:
            return self._json_fallback.predict_proba(X)
        dmat = xgb.DMatrix(np.asarray(X, dtype=float))
        pos = np.asarray(self.booster.predict(dmat), dtype=float).reshape(-1)
        return np.column_stack([1.0 - pos, pos])

    def predict_contribs(self, X: np.ndarray) -> np.ndarray:
        """Exact TreeSHAP feature attributions via native XGBoost C++ engine."""
        if not XGB_AVAILABLE or self.booster is None:
            raise RuntimeError("native xgboost booster not loaded")
        dmat = xgb.DMatrix(np.asarray(X, dtype=float))
        contribs = np.asarray(self.booster.predict(dmat, pred_contribs=True), dtype=float)
        return contribs[..., :-1]


class DiseaseModel:
    """Lazy-loading wrapper around one XGBoost classifier."""

    def __init__(self, spec: DiseaseSpec):
        self.spec = spec
        self.artifact = Path(get_settings().MODELS_DIR) / f"{spec.key}_model.json"
        self.artifact.parent.mkdir(parents=True, exist_ok=True)
        self.model: Optional[_BoosterModelAdapter] = None
        self.version = ""
        self.synthetic = False

    # ---- loading -----------------------------------------------------------
    def ensure_loaded(self) -> "DiseaseModel":
        if self.model is not None:
            return self
        if self.artifact.exists():
            self.model = _BoosterModelAdapter()
            self.model.load_model(str(self.artifact))
            meta = self._meta_path
            if meta.exists():
                meta_json = json.loads(meta.read_text())
                self.version = meta_json.get("version", "trained")
                self.synthetic = meta_json.get("synthetic", False)
            else:
                self.version = "trained"
        else:
            self._fit_stub()
        return self

    @property
    def _meta_path(self) -> Path:
        return self.artifact.with_suffix(".meta.json")

    def _fit_stub(self) -> None:
        """Train on random data so every downstream component works.
        # TODO: USER MUST TRAIN ON REAL DATA (see module docstring)."""
        rng = np.random.default_rng(42)
        n = 300
        dim = len(self.spec.features)
        means = np.array([f.mean for f in self.spec.features])
        stds = np.array([f.std for f in self.spec.features])
        X = np.clip(rng.normal(means, stds, size=(n, dim)),
                    [f.min for f in self.spec.features],
                    [f.max for f in self.spec.features])
        # meaningless-but-deterministic labels for the stub
        w = rng.normal(0, 1.0 / np.sqrt(dim), size=dim)
        logits = (X - means) @ w * 0.02
        y = (logits + rng.normal(0, 0.5, size=n) > 0).astype(int)
        self.model = _BoosterModelAdapter().fit(X, y)
        self.model.save_model(str(self.artifact))
        self.version = STUB_VERSION
        self.synthetic = True
        self._meta_path.write_text(
            json.dumps({"version": STUB_VERSION, "synthetic": True})
        )
        log.warning(
            "Loaded STUB model for '%s' (synthetic random data). "
            "Train on real data with app.ml.training.train.",
            self.spec.key,
        )

    # ---- inference (trusted, plaintext) ------------------------------------
    def predict_proba(self, raw_features: dict[str, float]) -> float:
        self.ensure_loaded()
        x = self._matrix(raw_features)
        return float(self.model.predict_proba(x)[0][1])

    def _matrix(self, raw_features: dict[str, float]) -> np.ndarray:
        row = [float(raw_features[f.name]) for f in self.spec.features]
        return np.asarray([row], dtype=float)

    # ---- surrogate for CKKS ---------------------------------------------------
    def linear_surrogate(self, samples: int = 400, seed: int = 7) -> dict:
        """Distill the XGBoost into an exact-evaluable linear model
        (logistic regression fitted to the model's own probabilities).
        Returned as plain floats the cloud can encode; the cloud sees model
        coefficients, never patient data."""
        self.ensure_loaded()
        rng = np.random.default_rng(seed)
        dim = len(self.spec.features)
        lo = np.array([f.min for f in self.spec.features])
        hi = np.array([f.max for f in self.spec.features])
        mean = np.array([f.mean for f in self.spec.features])
        std = np.array([f.std for f in self.spec.features])
        X = rng.uniform(lo, hi, size=(samples, dim))
        y = self.model.predict_proba(X)[:, 1]
        Xz = (X - mean) / std  # same normalization the CKKS path applies

        w = np.zeros(dim)
        b = 0.0
        lr, iters = 0.5, 600
        for _ in range(iters):
            p = 1.0 / (1.0 + np.exp(-(Xz @ w + b)))
            grad_w = Xz.T @ (p - y) / samples
            grad_b = float(np.mean(p - y))
            w -= lr * grad_w
            b -= lr * grad_b
        return {
            "type": "linear-surrogate",
            "disease": self.spec.key,
            "feature_names": [f.name for f in self.spec.features],
            "weights": [float(v) for v in w],
            "bias": float(b),
            "distilled_from": self.version,
        }


_CACHE: dict[str, DiseaseModel] = {}


def get_model(disease: str) -> DiseaseModel:
    if disease not in DISEASES:
        raise KeyError(f"unknown disease '{disease}' (known: {list(DISEASES)})")
    if disease not in _CACHE:
        _CACHE[disease] = DiseaseModel(DISEASES[disease]).ensure_loaded()
    return _CACHE[disease]

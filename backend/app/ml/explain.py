"""Explainability: SHAP values for every prediction + split-conformal
prediction intervals.

SHAP TreeExplainer runs on the trusted side over the plaintext feature
vector - the encrypted cloud only ever produces the risk score. If the
`shap` package is unavailable at runtime we fall back to the exact linear
surrogate's per-feature contributions (w_j * x_j), clearly labelled.
"""
from __future__ import annotations

from typing import Optional

import numpy as np

try:
    import shap

    SHAP_AVAILABLE = True
except ImportError:  # pragma: no cover
    shap = None  # type: ignore[assignment]
    SHAP_AVAILABLE = False

from app.core.logging import get_logger
from app.ml.models import DiseaseModel

log = get_logger(__name__)


def explain_prediction(
    model: DiseaseModel, raw_features: dict[str, float], surrogate: dict
) -> dict:
    """Top contributing features for one prediction."""
    names = [f.name for f in model.spec.features]
    x = np.array([float(raw_features[n]) for n in names])
    contributions = None
    method = "linear-surrogate"
    if SHAP_AVAILABLE:
        try:
            target = getattr(model.model, "booster", model.model)
            explainer = shap.TreeExplainer(target)
            values = explainer.shap_values(x.reshape(1, -1))
            arr = np.asarray(values)
            if arr.ndim == 3:  # (classes, rows, features) in some versions
                arr = arr[1]
            elif arr.ndim == 2 and arr.shape[0] != 1 and arr.shape[1] == 1:
                arr = arr.reshape(-1)
            contributions = arr.reshape(-1)[: len(names)]
            method = "shap-tree"
        except Exception as exc:  # noqa: BLE001 - fall back transparently
            log.warning("SHAP failed (%s); trying native XGBoost TreeSHAP", exc)
    if contributions is None and hasattr(model.model, "predict_contribs"):
        try:
            contributions = model.model.predict_contribs(x.reshape(1, -1)).reshape(-1)[: len(names)]
            method = "shap-tree"
        except Exception as exc:  # noqa: BLE001
            log.warning("Native TreeSHAP failed (%s); using surrogate contributions", exc)
            contributions = None
    if contributions is None:
        mean = np.array([f.mean for f in model.spec.features])
        std = np.array([f.std for f in model.spec.features])
        xz = (x - mean) / std
        contributions = np.asarray(surrogate["weights"]) * xz
        method = "linear-surrogate"
    order = np.argsort(-np.abs(contributions))
    top = [
        {
            "feature": names[i],
            "label": model.spec.features[i].label,
            "value": float(x[i]),
            "contribution": float(contributions[i]),
        }
        for i in order[: min(6, len(names))]
    ]
    return {"method": method, "top_features": top}


def conformal_interval(
    model: DiseaseModel, surrogate: dict, alpha: float = 0.1
) -> Optional[dict]:
    """Split-conformal interval for the predicted probability:
    [p - q, p + q] covers the true label with probability ~1-alpha, where q
    is the (1-alpha) quantile of calibration residuals.

    NOTE: with stub models the calibration set is synthetic, so intervals
    are structurally correct but uninformative. Retraining (train.py)
    recomputes q on real calibration data.
    # TODO: USER MUST CALIBRATE ON REAL DATA
    """
    try:
        import json

        from app.core.config import get_settings
        from pathlib import Path

        cal_path = Path(get_settings().MODELS_DIR) / f"{model.spec.key}.conformal.json"
        if cal_path.exists():
            data = json.loads(cal_path.read_text())
            return {
                "alpha": data["alpha"],
                "half_width": data["q"],
                "note": "calibrated on held-out data",
            }
        rng = np.random.default_rng(11)
        dim = len(model.spec.features)
        lo = np.array([f.min for f in model.spec.features])
        hi = np.array([f.max for f in model.spec.features])
        X = rng.uniform(lo, hi, size=(200, dim))
        mean = np.array([f.mean for f in model.spec.features])
        std = np.array([f.std for f in model.spec.features])
        Xz = (X - mean) / std
        w = np.asarray(surrogate["weights"])
        p_hat = 1.0 / (1.0 + np.exp(-(Xz @ w + surrogate["bias"])))
        y = (model.model.predict_proba(X)[:, 1] >= 0.5).astype(float)
        residuals = np.abs(p_hat - y)
        q = float(np.quantile(residuals, 1 - alpha))
        return {
            "alpha": alpha,
            "half_width": q,
            "note": "uncalibrated stub (synthetic residuals) - retrain for real coverage",
        }
    except Exception as exc:  # noqa: BLE001
        log.warning("conformal interval unavailable: %s", exc)
        return None

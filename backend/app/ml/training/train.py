"""CLI trainer for XGBoost disease models and split-conformal calibration.

Usage:
    python -m app.ml.training.train --disease diabetes --csv data/diabetes.csv --target Outcome
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.core.config import get_settings
from app.ml.models import DiseaseModel, _BoosterModelAdapter
from app.ml.registry import DISEASES, DiseaseSpec


def _load_csv_dataset(spec: DiseaseSpec, csv_path: Path, target_col: str) -> tuple[np.ndarray, np.ndarray]:
    feature_names = [f.name for f in spec.features]
    rows: list[list[float]] = []
    labels: list[float] = []
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise ValueError(f"CSV '{csv_path}' has no header row")
        missing = [name for name in [*feature_names, target_col] if name not in reader.fieldnames]
        if missing:
            raise ValueError(f"CSV missing required columns for {spec.key}: {missing}")
        for row in reader:
            try:
                x_row = [float(row[name]) for name in feature_names]
                y_val = float(row[target_col])
            except (TypeError, ValueError):
                continue
            rows.append(x_row)
            labels.append(1.0 if y_val > 0 else 0.0)
    if len(rows) < 20:
        raise ValueError(f"not enough valid rows ({len(rows)}) in {csv_path}")
    return np.asarray(rows, dtype=float), np.asarray(labels, dtype=float)


def train_disease_model(
    disease: str,
    csv_path: Path,
    target_col: str,
    *,
    alpha: float = 0.1,
    seed: int = 42,
) -> dict:
    """Fit an XGBoost model on CSV data and persist conformal calibration."""
    if disease not in DISEASES:
        raise KeyError(f"unknown disease '{disease}' (expected one of {sorted(DISEASES)})")
    spec = DISEASES[disease]
    X, y = _load_csv_dataset(spec, csv_path, target_col)

    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(X))
    X = X[perm]
    y = y[perm]

    split = max(int(len(X) * 0.8), len(X) - max(10, len(X) // 5))
    X_train, X_cal = X[:split], X[split:]
    y_train, y_cal = y[:split], y[split:]

    adapter = _BoosterModelAdapter().fit(X_train, y_train)
    models_dir = Path(get_settings().MODELS_DIR)
    models_dir.mkdir(parents=True, exist_ok=True)
    artifact = models_dir / f"{spec.key}_model.json"
    adapter.save_model(str(artifact))

    version = f"trained-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    meta_path = artifact.with_suffix(".meta.json")
    meta_path.write_text(
        json.dumps(
            {
                "version": version,
                "synthetic": False,
                "rows_total": int(len(X)),
                "rows_train": int(len(X_train)),
                "rows_calibration": int(len(X_cal)),
            },
            indent=2,
        )
    )

    wrapper = DiseaseModel(spec)
    wrapper.model = adapter
    wrapper.version = version
    wrapper.synthetic = False
    surrogate = wrapper.linear_surrogate()

    mean = np.array([f.mean for f in spec.features])
    std = np.array([f.std for f in spec.features])
    Xz_cal = (X_cal - mean) / std
    w = np.asarray(surrogate["weights"], dtype=float)
    p_hat = 1.0 / (1.0 + np.exp(-(Xz_cal @ w + float(surrogate["bias"]))))
    residuals = np.abs(p_hat - y_cal)
    q = float(np.quantile(residuals, 1.0 - alpha))

    cal_path = models_dir / f"{spec.key}.conformal.json"
    cal_path.write_text(
        json.dumps(
            {
                "alpha": alpha,
                "q": q,
                "calibration_size": int(len(X_cal)),
                "version": version,
            },
            indent=2,
        )
    )
    return {
        "disease": disease,
        "version": version,
        "artifact": str(artifact),
        "conformal_artifact": str(cal_path),
        "half_width": q,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a Secure EHR disease model.")
    parser.add_argument("--disease", required=True, choices=sorted(DISEASES))
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--target", required=True)
    parser.add_argument("--alpha", type=float, default=0.1)
    args = parser.parse_args()
    summary = train_disease_model(args.disease, args.csv, args.target, alpha=args.alpha)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

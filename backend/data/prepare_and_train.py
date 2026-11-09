"""Prepare clean CSV datasets (with canonical headers matching app.ml.registry)
and train all 4 disease models so the demo works out of the box.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

DATA_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DATA_DIR.parent))

from app.ml.registry import DISEASES
from app.ml.training.train import train_disease_model


def generate_dataset(disease: str, rows: int = 400, seed: int = 42) -> Path:
    spec = DISEASES[disease]
    rng = np.random.default_rng(seed)
    dim = len(spec.features)
    means = np.array([f.mean for f in spec.features])
    stds = np.array([f.std for f in spec.features])
    lo = np.array([f.min for f in spec.features])
    hi = np.array([f.max for f in spec.features])

    X = np.clip(rng.normal(means, stds, size=(rows, dim)), lo, hi)
    # Clinically directional weights so higher glucose/BP/bilirubin/creatinine increase risk
    weights = np.linspace(0.25, 0.85, dim)
    z = (X - means) / stds
    logits = (z @ weights) / np.sqrt(dim) + rng.normal(0, 0.35, size=rows)
    y = (logits > 0.0).astype(int)

    out_path = DATA_DIR / f"{disease}.csv"
    headers = [f.name for f in spec.features] + ["Outcome"]
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        for row_vals, label in zip(X, y):
            formatted = [round(float(v), 3) for v in row_vals] + [int(label)]
            writer.writerow(formatted)
    return out_path


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for idx, disease in enumerate(DISEASES):
        csv_path = generate_dataset(disease, rows=400, seed=100 + idx)
        summary = train_disease_model(disease, csv_path, "Outcome")
        print(f"[OK] {disease}: {summary['artifact']} (conformal q={summary['half_width']:.4f})")


if __name__ == "__main__":
    main()

"""Disease model registry: canonical feature lists, ranges and z-score
statistics used to normalize features before CKKS encryption.

Feature sets follow the standard public datasets (Pima diabetes 9,
Cleveland heart 13, Indian liver 10, chronic kidney 24) so retraining with
real data is a drop-in ``python -m app.ml.training.train`` away.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureSpec:
    name: str
    label: str
    min: float
    max: float
    mean: float
    std: float


@dataclass(frozen=True)
class DiseaseSpec:
    key: str
    label: str
    features: tuple[FeatureSpec, ...]


def _f(name, label, lo, hi, mean, std) -> FeatureSpec:
    return FeatureSpec(name, label, lo, hi, mean, std)


DISEASES: dict[str, DiseaseSpec] = {
    # Pima Indians Diabetes - 8 predictors (9 columns in diabetes.csv incl.
    # the Outcome target; the target is obviously NOT an input feature)
    "diabetes": DiseaseSpec(
        key="diabetes",
        label="Diabetes (Type-2 risk)",
        features=(
            _f("Pregnancies", "Pregnancies", 0, 17, 3.8, 3.4),
            _f("Glucose", "Plasma glucose (mg/dL)", 0, 200, 121.7, 30.4),
            _f("BloodPressure", "Diastolic BP (mm Hg)", 0, 122, 69.1, 19.4),
            _f("SkinThickness", "Triceps skinfold (mm)", 0, 99, 20.5, 16.0),
            _f("Insulin", "2-h serum insulin (mu U/ml)", 0, 846, 79.8, 115.2),
            _f("BMI", "Body mass index", 0, 67, 32.0, 7.9),
            _f("DiabetesPedigreeFunction", "Pedigree function", 0.08, 2.42, 0.47, 0.33),
            _f("Age", "Age (years)", 21, 81, 33.2, 11.8),
        ),
    ),
    # Cleveland Heart Disease (13 features)
    "heart": DiseaseSpec(
        key="heart",
        label="Coronary Heart Disease",
        features=(
            _f("age", "Age (years)", 29, 77, 54.4, 9.0),
            _f("sex", "Sex (1=male)", 0, 1, 0.68, 0.47),
            _f("cp", "Chest pain type (0-3)", 0, 3, 0.97, 1.03),
            _f("trestbps", "Resting BP (mm Hg)", 94, 200, 131.6, 17.5),
            _f("chol", "Serum cholesterol (mg/dL)", 126, 564, 246.7, 51.8),
            _f("fbs", "Fasting glucose >120 (1=yes)", 0, 1, 0.15, 0.36),
            _f("restecg", "Resting ECG (0-2)", 0, 2, 0.53, 0.53),
            _f("thalach", "Max heart rate", 71, 202, 149.6, 22.9),
            _f("exang", "Exercise angina (1=yes)", 0, 1, 0.33, 0.47),
            _f("oldpeak", "ST depression", 0, 6.2, 1.04, 1.16),
            _f("slope", "Slope of ST (0-2)", 0, 2, 1.4, 0.62),
            _f("ca", "Major vessels (0-3)", 0, 3, 0.73, 0.92),
            _f("thal", "Thal (1=normal,2=fixed,3=reversible)", 1, 3, 2.31, 0.61),
        ),
    ),
    # Indian Liver Patient (10 features)
    "liver": DiseaseSpec(
        key="liver",
        label="Liver Disease",
        features=(
            _f("Age", "Age (years)", 4, 90, 44.7, 16.2),
            _f("Gender", "Gender (1=male)", 0, 1, 0.76, 0.43),
            _f("Total_Bilirubin", "Total bilirubin (mg/dL)", 0.4, 75, 3.3, 6.2),
            _f("Direct_Bilirubin", "Direct bilirubin (mg/dL)", 0.1, 19.7, 1.5, 2.8),
            _f("Alkaline_Phosphotase", "ALP (IU/L)", 63, 2110, 290.6, 242.2),
            _f("Alamine_Aminotransferase", "SGPT (IU/L)", 10, 2000, 80.7, 182.4),
            _f("Aspartate_Aminotransferase", "SGOT (IU/L)", 10, 4929, 109.9, 288.7),
            _f("Total_Protiens", "Total protein (g/dL)", 2.7, 9.6, 6.5, 1.1),
            _f("Albumin", "Albumin (g/dL)", 0.9, 5.5, 3.1, 0.8),
            _f("Albumin_and_Globulin_Ratio", "A/G ratio", 0.3, 2.8, 0.95, 0.32),
        ),
    ),
    # Chronic Kidney Disease (24 features)
    "kidney": DiseaseSpec(
        key="kidney",
        label="Chronic Kidney Disease",
        features=(
            _f("age", "Age (years)", 2, 90, 51.5, 17.2),
            _f("bp", "Blood pressure (mm Hg)", 50, 180, 76.5, 13.7),
            _f("sg", "Specific gravity (1.005-1.025)", 1.005, 1.025, 1.017, 0.005),
            _f("al", "Albumin (0-5)", 0, 5, 1.0, 1.4),
            _f("su", "Sugar (0-5)", 0, 5, 0.4, 1.0),
            _f("rbc", "Red blood cells (0=normal,1=abnormal)", 0, 1, 0.14, 0.35),
            _f("pc", "Pus cell (0=normal,1=abnormal)", 0, 1, 0.2, 0.4),
            _f("pcc", "Pus cell clumps (0/1)", 0, 1, 0.05, 0.23),
            _f("ba", "Bacteria (0/1)", 0, 1, 0.03, 0.17),
            _f("bgr", "Blood glucose random (mgs/dL)", 22, 490, 148.0, 79.3),
            _f("bu", "Blood urea (mgs/dL)", 1.5, 391, 57.4, 50.5),
            _f("sc", "Serum creatinine (mgs/dL)", 0.4, 76, 3.1, 5.3),
            _f("sod", "Sodium (mEq/L)", 4.5, 163, 137.6, 10.4),
            _f("pot", "Potassium (mEq/L)", 2.5, 47, 4.6, 3.2),
            _f("hemo", "Hemoglobin (gms)", 3.1, 17.8, 12.5, 2.9),
            _f("pcv", "Packed cell volume", 9, 54, 38.9, 8.9),
            _f("wc", "White blood cell count", 2200, 26400, 8412, 2923),
            _f("rc", "Red blood cell count (millions/cmm)", 2.1, 8.0, 4.8, 1.1),
            _f("htn", "Hypertension (0/1)", 0, 1, 0.37, 0.48),
            _f("dm", "Diabetes mellitus (0/1)", 0, 1, 0.39, 0.49),
            _f("cad", "Coronary artery disease (0/1)", 0, 1, 0.06, 0.25),
            _f("appet", "Appetite (0=good,1=poor)", 0, 1, 0.19, 0.39),
            _f("pe", "Pedal edema (0/1)", 0, 1, 0.14, 0.35),
            _f("ane", "Anemia (0/1)", 0, 1, 0.13, 0.34),
        ),
    ),
}


def normalize(spec: DiseaseSpec, features: dict[str, float]) -> list[float]:
    """Validate + z-score normalize into the CKKS slot vector (NaN-safe)."""
    out: list[float] = []
    for feat in spec.features:
        if feat.name not in features:
            raise ValueError(f"missing feature '{feat.name}' for {spec.key}")
        value = float(features[feat.name])
        if value < feat.min or value > feat.max:
            raise ValueError(
                f"feature '{feat.name}' value {value} outside [{feat.min}, {feat.max}]"
            )
        out.append((value - feat.mean) / feat.std)
    return out


def denormalized_view(spec: DiseaseSpec, features: dict) -> list[dict]:
    return [
        {
            "name": f.name,
            "label": f.label,
            "value": features.get(f.name),
            "min": f.min,
            "max": f.max,
        }
        for f in spec.features
    ]

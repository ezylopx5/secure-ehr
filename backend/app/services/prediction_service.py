"""Trusted-side disease prediction orchestration and encrypted persistence.

This service owns the end-to-end prediction flow:
1. validate/normalize the patient's feature vector,
2. run CKKS encrypted inference against the untrusted cloud engine,
3. compute trusted-side explainability and reference plaintext probability,
4. encrypt both features and results at rest in the database.

The cloud only ever sees serialized CKKS ciphertexts plus the public context.
"""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto.aes_gcm import decrypt_json, encrypt_json
from app.crypto.key_manager import get_key_manager
from app.db.models import Patient, Prediction, User
from app.ml.encrypted_inference import encrypted_predict
from app.ml.explain import conformal_interval, explain_prediction
from app.ml.models import get_model
from app.ml.registry import normalize


def _aad(prediction_id: str) -> bytes:
    return f"ehr:prediction:{prediction_id}".encode()


def _risk_band(probability: float) -> str:
    if probability < 0.35:
        return "low"
    if probability < 0.70:
        return "moderate"
    return "high"


def create_prediction(
    db: Session,
    *,
    patient: Patient,
    disease: str,
    features: dict[str, float],
    created_by: User,
) -> tuple[Prediction, dict]:
    """Create and persist one encrypted disease prediction."""
    model = get_model(disease)
    normalized = normalize(model.spec, features)
    surrogate = model.linear_surrogate()
    he_result = encrypted_predict(normalized, surrogate)
    explanation = explain_prediction(model, features, surrogate)
    interval = conformal_interval(model, surrogate)
    plaintext_probability = model.predict_proba(features)
    risk_band = _risk_band(he_result["probability"])

    prediction = Prediction(
        id=str(uuid.uuid4()),
        patient_id=patient.id,
        disease=disease,
        model_version=model.version,
        risk_band=risk_band,
        created_by=created_by.id,
    )
    db.add(prediction)

    key = get_key_manager().record_dek(prediction.id)
    prediction.features_enc = encrypt_json(
        key,
        {
            "raw": features,
            "normalized": normalized,
            "feature_names": surrogate["feature_names"],
        },
        aad=_aad(prediction.id),
    )
    result_payload = {
        "disease": disease,
        "encrypted_inference": he_result,
        "plaintext_reference_probability": plaintext_probability,
        "explanation": explanation,
        "conformal": interval,
        "synthetic_model": model.synthetic,
        "distilled_from": surrogate["distilled_from"],
        "he_params": he_result["he_params"],
    }
    prediction.result_enc = encrypt_json(key, result_payload, aad=_aad(prediction.id))
    db.commit()
    db.refresh(prediction)

    response = {
        "prediction_id": prediction.id,
        "patient_id": prediction.patient_id,
        "disease": prediction.disease,
        "model_version": prediction.model_version,
        "risk_band": prediction.risk_band,
        "probability": float(he_result["probability"]),
        "raw_score": float(he_result["raw_score"]),
        "plaintext_reference_probability": float(plaintext_probability),
        "cloud_saw_plaintext": False,
        "explanation": explanation,
        "conformal": interval,
        "synthetic_model": model.synthetic,
        "created_at": prediction.created_at,
    }
    return prediction, response


def read_prediction(prediction: Prediction) -> dict:
    """Decrypt one stored prediction."""
    key = get_key_manager().record_dek(prediction.id)
    features = decrypt_json(key, prediction.features_enc, aad=_aad(prediction.id))
    result = decrypt_json(key, prediction.result_enc, aad=_aad(prediction.id))
    return {
        "id": prediction.id,
        "patient_id": prediction.patient_id,
        "disease": prediction.disease,
        "model_version": prediction.model_version,
        "risk_band": prediction.risk_band,
        "features": features,
        "result": result,
        "created_by": prediction.created_by,
        "created_at": prediction.created_at,
    }


def list_predictions(db: Session, patient_id: str) -> list[Prediction]:
    """List stored predictions for one patient."""
    return list(
        db.execute(
            select(Prediction)
            .where(Prediction.patient_id == patient_id)
            .order_by(Prediction.created_at.desc())
        ).scalars()
    )

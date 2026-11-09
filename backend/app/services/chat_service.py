"""Encrypted clinical chat service backed by LangGraph."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.assistant import run_clinical_assistant
from app.crypto.aes_gcm import decrypt_json, encrypt_json
from app.crypto.key_manager import get_key_manager
from app.db.models import ChatMessage, Patient, User
from app.services import consent_service, prediction_service, record_service


def _aad(message_id: str) -> bytes:
    return f"ehr:chat:{message_id}".encode()


def _store_message(
    db: Session,
    *,
    user_id: str,
    patient_id: str | None,
    role: str,
    content: str,
    agent_trace: list[dict] | None = None,
) -> ChatMessage:
    msg_id = str(uuid.uuid4())
    key = get_key_manager().record_dek(msg_id)
    msg = ChatMessage(
        id=msg_id,
        user_id=user_id,
        patient_id=patient_id,
        role=role,
        content_enc=encrypt_json(key, {"content": content}, aad=_aad(msg_id)),
        agent_trace=agent_trace,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def read_message(msg: ChatMessage) -> dict:
    key = get_key_manager().record_dek(msg.id)
    body = decrypt_json(key, msg.content_enc, aad=_aad(msg.id))
    return {
        "id": msg.id,
        "user_id": msg.user_id,
        "patient_id": msg.patient_id,
        "role": msg.role,
        "content": body["content"],
        "agent_trace": msg.agent_trace,
        "created_at": msg.created_at,
    }


def _build_deidentified_context(db: Session, user: User, patient: Patient | None) -> dict:
    if patient is None:
        return {"records": [], "predictions": []}
    records_ctx: list[dict] = []
    for record in record_service.list_records(db, patient.id)[:5]:
        allowed, _ = consent_service.check_access(
            db, user=user, patient=patient, category=record.category, purpose="treatment"
        )
        if allowed:
            decrypted = record_service.read_record(db, record)
            records_ctx.append(
                {
                    "record_type": record.record_type,
                    "category": record.category,
                    "title": decrypted["title"],
                    "payload": decrypted.get("payload") or {},
                }
            )
    preds_ctx: list[dict] = []
    allowed_pred, _ = consent_service.check_access(
        db, user=user, patient=patient, purpose="ai_prediction"
    )
    if allowed_pred:
        for pred in prediction_service.list_predictions(db, patient.id)[:3]:
            dec_pred = prediction_service.read_prediction(pred)
            res = dec_pred["result"]
            preds_ctx.append(
                {
                    "disease": pred.disease,
                    "risk_band": pred.risk_band,
                    "probability": float(res["encrypted_inference"]["probability"]),
                    "top_features": (res.get("explanation") or {}).get("top_features", []),
                }
            )
    return {"records": records_ctx, "predictions": preds_ctx}


def send_chat(
    db: Session,
    *,
    user: User,
    prompt: str,
    patient: Patient | None = None,
) -> tuple[dict, dict]:
    """Persist encrypted user prompt and assistant response."""
    context = _build_deidentified_context(db, user, patient)
    result = run_clinical_assistant(prompt, context)
    user_msg = _store_message(
        db,
        user_id=user.id,
        patient_id=patient.id if patient else None,
        role="user",
        content=result["scrubbed_prompt"],
    )
    assistant_msg = _store_message(
        db,
        user_id=user.id,
        patient_id=patient.id if patient else None,
        role="assistant",
        content=result["reply"],
        agent_trace=result["trace"],
    )
    return read_message(user_msg), read_message(assistant_msg)


def list_history(
    db: Session, *, user: User, patient_id: str | None = None, limit: int = 50
) -> list[dict]:
    stmt = select(ChatMessage).where(ChatMessage.user_id == user.id)
    if patient_id is not None:
        stmt = stmt.where(ChatMessage.patient_id == patient_id)
    rows = db.execute(stmt.order_by(ChatMessage.created_at.asc()).limit(limit)).scalars().all()
    return [read_message(row) for row in rows]

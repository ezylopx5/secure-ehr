"""End-to-end tests for the FastAPI application, encrypted inference boundary,
CP-ABE record sharing, consent enforcement, FHIR R4 export, clinical chat, and
audit blockchain verification.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def _login(client: TestClient, username: str, password: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    tokens = resp.json()
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def test_full_clinical_and_encrypted_ai_workflow(isolated_env):
    with TestClient(app) as client:
        # 1. Health check + security headers
        health = client.get("/healthz")
        assert health.status_code == 200
        assert health.headers["X-Content-Type-Options"] == "nosniff"
        assert health.headers["X-Frame-Options"] == "DENY"

        # 2. Authenticate seeded demo actors + test refresh token exchange
        login_res = client.post(
            "/api/auth/login", json={"username": "doctor1", "password": "Doctor12345"}
        )
        assert login_res.status_code == 200
        refreshed = client.post(
            "/api/auth/refresh",
            json={"refresh_token": login_res.json()["refresh_token"]},
        )
        assert refreshed.status_code == 200
        doc_headers = {"Authorization": f"Bearer {refreshed.json()['access_token']}"}
        patient_headers = _login(client, "patient1", "Patient12345")
        auditor_headers = _login(client, "auditor1", "Auditor12345")

        # 3. Patient listing and decrypted demographics
        patients = client.get("/api/patients", headers=doc_headers).json()
        assert len(patients) == 1
        patient_id = patients[0]["id"]

        p_view = client.get(f"/api/patients/{patient_id}", headers=doc_headers)
        assert p_view.status_code == 200
        assert p_view.json()["demographics"]["name"] == "Aarav Patel"

        # 4. Create encrypted record + verify SHA-256 integrity + CP-ABE share
        rec_res = client.post(
            f"/api/patients/{patient_id}/records",
            headers=doc_headers,
            json={
                "record_type": "lab",
                "category": "cardiac",
                "title": "Lipid Panel & Troponin",
                "payload": {"ldl": 142, "hdl": 44, "troponin_ng_ml": 0.01},
            },
        )
        assert rec_res.status_code == 201, rec_res.text
        record_id = rec_res.json()["id"]

        ver = client.get(
            f"/api/patients/{patient_id}/records/{record_id}/verify",
            headers=auditor_headers,
        )
        assert ver.status_code == 200
        assert ver.json()["integrity"] == "ok"

        share = client.post(
            f"/api/records/{record_id}/share",
            headers=doc_headers,
            json={"policy": "(role:doctor AND dept:cardiology) OR role:admin"},
        )
        assert share.status_code == 200

        opened = client.post(f"/api/records/{record_id}/open-abe", headers=doc_headers)
        assert opened.status_code == 200
        assert opened.json()["payload"]["ldl"] == 142

        # Auditor does not satisfy the cardiology doctor/admin policy
        denied_abe = client.post(
            f"/api/records/{record_id}/open-abe", headers=auditor_headers
        )
        assert denied_abe.status_code == 403

        # 5. Disease catalog + CKKS homomorphic encrypted prediction
        diseases = client.get("/api/diseases", headers=doc_headers)
        assert diseases.status_code == 200
        assert {d["key"] for d in diseases.json()} == {"diabetes", "heart", "liver", "kidney"}

        pred_res = client.post(
            f"/api/patients/{patient_id}/predictions",
            headers=doc_headers,
            json={
                "disease": "diabetes",
                "features": {
                    "Pregnancies": 2,
                    "Glucose": 148,
                    "BloodPressure": 72,
                    "SkinThickness": 35,
                    "Insulin": 120,
                    "BMI": 33.6,
                    "DiabetesPedigreeFunction": 0.627,
                    "Age": 50,
                },
            },
        )
        assert pred_res.status_code == 201, pred_res.text
        pred_body = pred_res.json()
        assert pred_body["cloud_saw_plaintext"] is False
        assert 0.0 <= pred_body["probability"] <= 1.0
        assert pred_body["risk_band"] in {"low", "moderate", "high"}
        assert len(pred_body["explanation"]["top_features"]) > 0

        stored_preds = client.get(
            f"/api/patients/{patient_id}/predictions", headers=doc_headers
        )
        assert stored_preds.status_code == 200
        assert len(stored_preds.json()) == 1

        # 6. FHIR R4 Bundle export with SHA-256 and HMAC signatures
        fhir_res = client.post(
            f"/api/patients/{patient_id}/fhir", headers=doc_headers
        )
        assert fhir_res.status_code == 201, fhir_res.text
        fhir_body = fhir_res.json()
        assert fhir_body["bundle"]["resourceType"] == "Bundle"
        assert fhir_body["resource_count"] >= 3

        # 7. Encrypted clinical chat with PII scrubbing
        chat_res = client.post(
            "/api/chat",
            headers=doc_headers,
            json={
                "patient_id": patient_id,
                "prompt": "Summarize risk for patient phone 9876543210 and email test@example.com",
            },
        )
        assert chat_res.status_code == 201, chat_res.text
        chat_body = chat_res.json()
        assert "[PHONE]" in chat_body["user_message"]["content"]
        assert "[EMAIL]" in chat_body["user_message"]["content"]
        assert "diabetes" in chat_body["assistant_message"]["content"]

        # 8. Consent revocation blocks doctor access immediately
        consents = client.get(
            f"/api/patients/{patient_id}/consents", headers=patient_headers
        ).json()
        assert len(consents) == 1
        revoke = client.post(
            f"/api/consents/{consents[0]['id']}/revoke", headers=patient_headers
        )
        assert revoke.status_code == 200
        blocked = client.get(
            f"/api/patients/{patient_id}/records/{record_id}", headers=doc_headers
        )
        assert blocked.status_code == 403

        # 9. Audit blockchain verification
        audit_ver = client.get("/api/audit/verify", headers=auditor_headers)
        assert audit_ver.status_code == 200
        assert audit_ver.json()["valid"] is True
        assert audit_ver.json()["length"] >= 8

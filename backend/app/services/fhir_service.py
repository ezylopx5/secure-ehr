"""HL7 FHIR R4 bundle export with SHA-256 and HMAC-SHA256 integrity proofs."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.crypto.integrity import checksum_bundle, sha256_json
from app.crypto.key_manager import get_key_manager
from app.db.models import FhirExport, Patient, User
from app.services import consent_service, prediction_service, record_service


def export_patient_bundle(
    db: Session, *, patient: Patient, actor: User
) -> dict:
    """Assemble an HL7 FHIR R4 Bundle for consented patient resources and
    persist cryptographic integrity metadata."""
    demographics = record_service.read_demographics(db, patient)
    entries: list[dict] = [
        {
            "fullUrl": f"urn:uuid:{patient.id}",
            "resource": {
                "resourceType": "Patient",
                "id": patient.id,
                "identifier": [{"system": "urn:secure-ehr:mrn", "value": patient.mrn}],
                "name": [{"text": demographics.get("name", "Unknown")}],
                "gender": demographics.get("gender", "unknown"),
                "birthDate": demographics.get("dob"),
            },
        }
    ]

    for record in record_service.list_records(db, patient.id):
        if actor.role != "admin":
            allowed, _ = consent_service.check_access(
                db,
                user=actor,
                patient=patient,
                category=record.category,
                purpose="export",
            )
            if not allowed:
                continue
        decrypted = record_service.read_record(db, record)
        entries.append(
            {
                "fullUrl": f"urn:uuid:{record.id}",
                "resource": {
                    "resourceType": "Observation",
                    "id": record.id,
                    "status": "final",
                    "category": [{"text": record.category}],
                    "code": {"text": decrypted["title"]},
                    "subject": {"reference": f"Patient/{patient.id}"},
                    "effectiveDateTime": record.created_at.isoformat(),
                    "valueString": str(decrypted["payload"]),
                },
            }
        )

    for pred in prediction_service.list_predictions(db, patient.id):
        dec = prediction_service.read_prediction(pred)
        prob = float(dec["result"]["encrypted_inference"]["probability"])
        entries.append(
            {
                "fullUrl": f"urn:uuid:{pred.id}",
                "resource": {
                    "resourceType": "RiskAssessment",
                    "id": pred.id,
                    "status": "final",
                    "subject": {"reference": f"Patient/{patient.id}"},
                    "occurrenceDateTime": pred.created_at.isoformat(),
                    "prediction": [
                        {
                            "outcome": {"text": pred.disease},
                            "probabilityDecimal": round(prob, 6),
                            "qualitativeRisk": {"text": pred.risk_band},
                        }
                    ],
                },
            }
        )

    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total": len(entries),
        "entry": entries,
    }
    digest = sha256_json(bundle)
    sig = checksum_bundle(get_key_manager().audit_hmac_key, bundle)

    export_row = FhirExport(
        id=str(uuid.uuid4()),
        patient_id=patient.id,
        bundle_sha256=digest,
        checksum_hmac=sig,
        resource_count=len(entries),
        exported_by=actor.id,
    )
    db.add(export_row)
    db.commit()
    db.refresh(export_row)

    return {
        "export_id": export_row.id,
        "patient_id": patient.id,
        "resource_count": export_row.resource_count,
        "bundle_sha256": export_row.bundle_sha256,
        "checksum_hmac": export_row.checksum_hmac,
        "bundle": bundle,
        "created_at": export_row.created_at,
    }

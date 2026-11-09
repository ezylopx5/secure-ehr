# AegisEHR — Privacy-Preserving AI-Powered Electronic Health Record Platform

AegisEHR is an end-to-end cryptographically hardened Electronic Health Record (EHR) and Clinical Decision-Support Platform. It combines **zero-plaintext database storage (`AES-256-GCM`)**, **bilinear-pairing Ciphertext-Policy Attribute-Based Encryption (`CP-ABE` on BN254)**, **homomorphic encrypted cloud disease prediction (`CKKS` via Microsoft SEAL / TenSEAL)**, **TreeSHAP explainability**, **HL7 FHIR R4 interoperability**, and an **append-only `HMAC-SHA256` audit blockchain**.

Production link: https://secure-ehr.vercel.app/
---

## Key Capabilities

1. **Zero-Plaintext Storage (`AES-256-GCM` + `HKDF-SHA256` + `SHA-256` Drift Detection)**
   - Every sensitive column (`Patient.demographics_enc`, `MedicalRecord.title_enc`, `MedicalRecord.payload_enc`, `Prediction.features_enc`, `Prediction.result_enc`, `ChatMessage.content_enc`) is encrypted with a unique per-row Data Encryption Key derived via `HKDF-SHA256` from a single 256-bit root master key and bound to the row UUID via Additional Authenticated Data (`AAD`).
   - Canonical JSON `SHA-256` digests are stored alongside ciphertexts to detect any silent bit-rot or out-of-band database tampering on read.

2. **Cross-Organization Sharing via Bilinear Pairing `CP-ABE` (`BN254`)**
   - Records shared across departments or institutions are encrypted under monotone access policies (e.g. `(role:doctor AND dept:cardiology) OR role:admin`) using linear secret sharing (Shamir threshold gates) over the Barreto-Naehrig `bn128` pairing curve (`py_ecc`).
   - Users can only open shared ciphertexts if their issued attribute key satisfies the policy tree mathematically.

3. **Homomorphic Encrypted Cloud Inference (`CKKS`) + Local `TreeSHAP`**
   - Patient clinical features are z-score normalized and encrypted on the **trusted hospital side** using a secret `CKKS` context (`poly_modulus_degree = 8192`, `coeff_mod_bit_sizes = [60, 40, 40, 60]`, scale $2^{40}$).
   - The **untrusted cloud engine** (`CloudInferenceEngine`) receives **only** the serialized public context (secret key stripped) and the ciphertext vector, evaluating $\langle w, x \rangle + b$ homomorphically on ciphertexts (`cloud_saw_plaintext = false`).
   - Only the trusted hospital backend decrypts the scalar logit, applies the logistic sigmoid, computes exact **TreeSHAP** feature attributions (`pred_contribs=True`) and **90% split-conformal intervals**, and seals the result at rest.

4. **Patient-Sovereign Consent Governance & 7-Layer Defense-in-Depth Middleware**
   - Doctors can only read clinical records, run AI risk assessments, or export FHIR bundles when an active, unexpired patient consent covers both the **record category** (`cardiac`, `labs`, `general`, `mental`, `imaging`) and **purpose** (`treatment`, `ai_prediction`, `export`).
   - Requests pass through a 7-layer ASGI middleware stack: token-bucket rate limiting, trusted host validation, explicit CORS allow-listing, OWASP security headers (`CSP`, `HSTS`, `X-Frame-Options: DENY`), GZip, regex PII exception scrubbing, and structured JSON request logging.

5. **PII-Scrubbed LangGraph Clinical Assistant & Signed HL7 FHIR R4 Export**
   - A 3-stage `LangGraph` workflow (`scrub_input → build_context → generate_reply`) redacts phone numbers, emails, PAN/Aadhaar-like identifiers, and ciphertext blobs before assembling de-identified clinical context.
   - Exports consented patient records and risk assessments as standard **HL7 FHIR R4 Bundles** signed with `SHA-256` and `HMAC-SHA256`.

6. **Tamper-Evident Audit Blockchain**
   - Every authentication, consent change, record access, CP-ABE share, FHIR export, and AI prediction mines a hash-linked block (`prev_hash → block_hash`) signed with the KeyManager's `HMAC-SHA256` audit key.

---

## Architecture & Trust Boundary

```text
+-----------------------------------------------------------------------------------+
|                            TRUSTED HOSPITAL BOUNDARY                              |
|                                                                                   |
|  [React Clinical Portal]  <-- JWT + RBAC + Consent -->  [FastAPI Backend]         |
|         (:5173)                                              (:8000)              |
|                                                                 |                 |
|     +---------------------------+-------------------------------+-------------+   |
|     |                           |                               |             |   |
|     v                           v                               v             v   |
| [HKDF + AES-256-GCM]    [BN254 CP-ABE Authority]     [Secret CKKS Context] [Audit]|
| Per-Row DEKs & SHA256   Policy Trees & User Keys     Encrypts z-score vec  HMAC   |
|     |                                                           |          Chain  |
+-----|-----------------------------------------------------------|-----------------+
      |                                                           |
      v                                                           | Public Context +
[SQLite / PostgreSQL]                                             | Ciphertext Only
(Zero Plaintext PHI)                                              v
                                            +---------------------------------------+
                                            |     UNTRUSTED CLOUD INFERENCE         |
                                            |        CloudInferenceEngine           |
                                            |  Evaluates Enc(score) = <w, Enc(z)>+b |
                                            |     (No Secret Key, No Plaintext)     |
                                            +---------------------------------------+
```

---

## Repository Structure

```text
secure-ehr/
├── run_demo.sh                         # One-command launcher (FastAPI + Vite UI)
├── .env.example                        # Environment configuration template
├── docs/
│   └── CRYPTOGRAPHY.md                 # Detailed cryptographic specifications
├── backend/
│   ├── alembic/                        # Database schema migration environment
│   ├── data/
│   │   ├── prepare_and_train.py        # Dataset generator & batch model trainer
│   │   ├── diabetes.csv                # Diabetes dataset (8 features + Outcome)
│   │   ├── heart.csv                   # Heart disease dataset (13 features + Outcome)
│   │   ├── liver.csv                   # Liver disease dataset (10 features + Outcome)
│   │   └── kidney.csv                  # Kidney disease dataset (24 features + Outcome)
│   ├── models/                         # Trained XGBoost .json + .conformal.json artifacts
│   ├── app/
│   │   ├── main.py                     # FastAPI entrypoint, middleware & demo seed
│   │   ├── schemas.py                  # Pydantic v2 request/response contracts
│   │   ├── api/                        # Route handlers (routes.py) & JWT guards (deps.py)
│   │   ├── core/                       # Settings (config.py), JWT/bcrypt (security.py)
│   │   ├── crypto/                     # AES-GCM, HKDF KeyManager, CP-ABE, CKKS, AuditChain
│   │   ├── ml/                         # XGBoost models, CKKS client, TreeSHAP, CLI trainer
│   │   ├── cloud/                      # Untrusted CKKS homomorphic evaluator (engine.py)
│   │   ├── ai/                         # LangGraph clinical assistant (assistant.py)
│   │   ├── services/                   # Record, Consent, Prediction, Chat, FHIR & Audit
│   │   └── db/                         # SQLAlchemy 2.0 ORM models & session management
│   └── tests/                          # 25-test suite (AES, CP-ABE, CKKS, Audit, E2E API)
└── frontend/
    ├── index.html
    ├── vite.config.ts
    └── src/
        ├── api/client.ts               # Typed API client with automatic JWT refresh
        ├── context/AuthContext.tsx     # Session & role-switching provider
        ├── components/Layout.tsx       # Clinical portal shell & navigation
        └── pages/
            ├── LoginPage.tsx           # Split-panel sign-in, registration & demo presets
            ├── PatientWorkspacePage.tsx# Records, CP-ABE, CKKS AI, Chat, Consent & FHIR
            └── AuditChainPage.tsx      # Blockchain ledger & HMAC signature verifier
```

---

## Quick Start

### Option A: One-Command Launch
From the repository root:
```bash
./run_demo.sh
```
- **Frontend UI**: [http://127.0.0.1:5173](http://127.0.0.1:5173)
- **Backend API & Swagger Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

### Option B: Run Backend & Frontend Separately

#### 1. Start the Backend (`FastAPI`)
```bash
cd backend
./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### 2. Start the Frontend (`React + TypeScript + Vite`)
```bash
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

---

## Seeded Demo Accounts

In development mode (`ENV=dev`), the backend automatically seeds four actors, issues their `BN254 CP-ABE` attribute keys, creates an encrypted patient profile (`MRN-DEMO-0001`), and grants initial consent to `doctor1`. You can switch between them with a single click on the login page or top navigation bar:

| Role | Username | Password | Issued CP-ABE Attributes | What to Test |
| :--- | :--- | :--- | :--- | :--- |
| **Doctor** | `doctor1` | `Doctor12345` | `role:doctor`, `dept:cardiology`, `org:nitsurat-hospital`, `relation:primary-physician`, `cat:cardiac`, `cat:labs`, `cat:general` | Create/decrypt records, apply CP-ABE policies, run CKKS encrypted disease risk assessments, chat with the clinical assistant, export FHIR bundles |
| **Patient** | `patient1` | `Patient12345` | `role:patient`, `relation:self`, `org:nitsurat-hospital`, `dept:general` | View own decrypted records & risk assessments, grant or **revoke** doctor consent in real time |
| **Auditor** | `auditor1` | `Auditor12345` | `role:auditor`, `org:nitsurat-hospital`, `dept:general` | Inspect record metadata without plaintext PHI access, verify `SHA-256` digests, and run full `HMAC-SHA256` audit blockchain verification |
| **Admin** | `admin` | `Admin12345` | `role:admin`, `org:nitsurat-hospital`, `dept:general` | Onboard new patients, audited break-glass clinical access, and audit ledger inspection |

---

## Model Training & Verification Suite

### Re-train All 4 Disease Models (`diabetes`, `heart`, `liver`, `kidney`)
```bash
cd backend
./.venv/bin/python data/prepare_and_train.py
```
Or train an individual model via the CLI trainer:
```bash
cd backend
./.venv/bin/python -m app.ml.training.train --disease diabetes --csv data/diabetes.csv --target Outcome
```

### Run the Automated Pytest Suite
```bash
cd backend
./.venv/bin/python -m pytest -q
```
The test suite verifies:
- `tests/test_aes_integrity.py` — `AES-256-GCM` round-trip, bit-flip tamper rejection, AAD binding, HKDF key isolation, and `HMAC-SHA256` bundle verification.
- `tests/test_abe.py` — `BN254` `CP-ABE` policy parser, authorized attribute decryption, unauthorized attribute rejection, and user key persistence.
- `tests/test_he.py` — `CKKS` secret key stripping from public contexts, homomorphic dot-product accuracy (`< 1e-3` error), and depth-2 quadratic circuits.
- `tests/test_audit_chain.py` — Genesis creation, hash chaining, payload tamper detection, and `HMAC` key verification.
- `tests/test_api_e2e.py` — Full FastAPI lifecycle across login, token refresh, encrypted records, `CP-ABE` sharing, `CKKS` predictions, `FHIR R4` export, `PII`-scrubbed clinical chat, consent revocation, and audit chain verification.

---

## REST API Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/healthz` | Service health check |
| `POST` | `/api/auth/register` | Self-service patient registration & CP-ABE key issuance |
| `POST` | `/api/auth/login` | Authenticate and mint JWT access/refresh token pair |
| `POST` | `/api/auth/refresh` | Exchange refresh token for a new token pair |
| `GET` | `/api/auth/me` | Current user profile & issued CP-ABE attributes |
| `GET` | `/api/patients` | List patients visible to the caller |
| `POST` | `/api/patients` | Create patient with `AES-256-GCM` encrypted demographics |
| `GET` | `/api/patients/{id}` | Read decrypted patient demographics (consent-checked) |
| `GET` | `/api/patients/{id}/records` | List record metadata visible to the caller |
| `POST` | `/api/patients/{id}/records` | Seal & store a new clinical record (`AES-256-GCM` + `SHA-256`) |
| `GET` | `/api/patients/{id}/records/{rid}` | Decrypt & verify a single record after consent check |
| `GET` | `/api/patients/{id}/records/{rid}/verify` | Verify ciphertext authenticity & `SHA-256` digest without exposing PHI |
| `POST` | `/api/records/{rid}/share` | Wrap a record under a `BN254 CP-ABE` policy expression |
| `POST` | `/api/records/{rid}/open-abe` | Decrypt a shared record using the caller's `CP-ABE` key |
| `GET` | `/api/diseases` | List disease models (`diabetes`, `heart`, `liver`, `kidney`) & feature specs |
| `POST` | `/api/patients/{id}/predictions` | Run `CKKS` homomorphic cloud inference + `TreeSHAP` + conformal intervals |
| `GET` | `/api/patients/{id}/predictions` | List decrypted historical predictions for a patient |
| `GET` | `/api/patients/{id}/consents` | List active patient consents |
| `POST` | `/api/patients/{id}/consents` | Grant scoped category/purpose consent to a clinician |
| `POST` | `/api/consents/{cid}/revoke` | Revoke consent (immediately blocks clinical/AI access) |
| `POST` | `/api/patients/{id}/fhir` | Export signed `HL7 FHIR R4` bundle (`SHA-256` + `HMAC-SHA256`) |
| `POST` | `/api/chat` | Run `PII`-scrubbed `LangGraph` clinical assistant & store encrypted chat |
| `GET` | `/api/chat/history` | Retrieve decrypted chat history |
| `GET` | `/api/audit/chain` | Inspect append-only audit blockchain blocks |
| `GET` | `/api/audit/verify` | Verify full blockchain hash links and `HMAC-SHA256` signatures |

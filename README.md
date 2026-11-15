# AegisEHR — Secure AI-Powered Electronic Health Record Platform

AegisEHR is an end-to-end cryptographically secured Electronic Health Record (EHR) and Clinical Decision-Support Platform. It integrates **classical and foundational cryptographic algorithms** (**MD5 & SHA-256 Message Digests**, **Diffie–Hellman Key Exchange**, **RSA Cryptosystem**, **Data Encryption Standard (DES)**, **One-Time Pad (OTP)**, and **Hill Cipher**) with **Multi-Disease Machine Learning (`XGBoost` + `TreeSHAP`)**, **LangGraph Clinical AI**, **HL7 FHIR R4 interoperability**, and a **tamper-evident hash-chained Audit Ledger**.

---
**Live Production Portal:** https://secure-ehr.vercel.app/

## Core Cryptographic & AI Capabilities

1. **MD5 & SHA-256 Message Digests for Record Integrity Verification**
   - Every clinical record (`MedicalRecord`), patient demographic profile (`Patient`), and audit block generates 128-bit **MD5** and 256-bit **SHA-256** message digests ([`classical_crypto.py`](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/crypto/classical_crypto.py), [`integrity.py`](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/crypto/integrity.py)).
   - Clicking **Verify MD5 & SHA-256** in the portal recomputes both digests over the canonical JSON payload to detect any unauthorized modification or database tampering.

2. **Symmetric & Classical Record Encryption (`DES`, `One-Time Pad`, `Hill Cipher`, `AES-256-GCM`)**
   - **Data Encryption Standard (DES):** Full 16-round Feistel network (`IP`, Expansion `E`, 8 S-boxes, P-box, 56-bit key schedule) operating on 64-bit blocks.
   - **One-Time Pad (OTP):** Bitwise XOR stream cipher ($C_i = P_i \oplus K_i$) with equal-length random pad keys.
   - **Hill Cipher:** Polygraphic $2 \times 2$ matrix substitution modulo 26 ($C = K \cdot P \bmod 26$, $P = K^{-1} \cdot C \bmod 26$).
   - **Envelope Storage:** Database columns are sealed at rest with per-row keys.

3. **Asymmetric Key Exchange & Record Sharing (`Diffie–Hellman` & `RSA Cryptosystem`)**
   - **Diffie–Hellman Key Exchange (DHKE):** Establishes shared session keys ($A = g^a \bmod p$, $B = g^b \bmod p$, $S = g^{ab} \bmod p$) between the Hospital Portal and Specialist / Cloud AI nodes.
   - **RSA Cryptosystem:** Asymmetric public/private key generation ($n = p \times q$, $\phi(n) = (p-1)(q-1)$, $e, d$) and modular exponentiation ($C = M^e \bmod n$, $M = C^d \bmod n$) for secure cross-departmental sharing.

4. **Interactive Cryptography Workbench (`POST /api/crypto/lab`)**
   - Built-in **Crypto Algorithms Lab** tab in the React clinical portal allowing users and examiners to enter any patient record or clinical text and inspect live outputs of **MD5/SHA-256**, **Diffie–Hellman**, **RSA**, **DES**, **One-Time Pad**, and **Hill Cipher**.

5. **Multi-Disease AI Risk Prediction (`XGBoost` + `TreeSHAP` + Conformal Intervals)**
   - Trained clinical risk models for **Type-2 Diabetes**, **Coronary Heart Disease**, **Liver Disease**, and **Chronic Kidney Disease** with exact **TreeSHAP** biomarker attributions and **90% Split Conformal Prediction** intervals.

6. **PII-Scrubbed LangGraph Clinical Assistant & Signed HL7 FHIR R4 Export**
   - 3-node `LangGraph` pipeline (`scrub_input → build_context → generate_reply`) that redacts phone numbers, emails, and IDs before summarizing consented clinical records.
   - Exports consented patient records as **HL7 FHIR R4 Bundles** signed with `SHA-256` and `HMAC-SHA256`.

---

## Demo Accounts (One-Click Persona Launch Available on Login Page)

| Persona | Username | Password | Capabilities |
| :--- | :--- | :--- | :--- |
| **Cardiology Doctor** | `doctor1` | `Doctor12345` | Decrypt consented records, run Crypto Lab, execute AI disease models & share records |
| **Patient** | `patient1` | `Patient12345` | View personal lab panels, inspect AI risk drivers & grant/revoke doctor consent |
| **Security Auditor** | `auditor1` | `Auditor12345` | Verify MD5 & SHA-256 record digests & validate the append-only audit hash chain |
| **System Admin** | `admin` | `Admin12345` | Enroll patients, break-glass access, run Crypto Lab & verify audit ledger |

---

## Quick Start (Local Development)

```bash
# Launch both FastAPI backend (:8000) and React Vite frontend (:5173)
./run_demo.sh
```

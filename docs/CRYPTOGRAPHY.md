# Cryptography & Threat Model (`CRYPTOGRAPHY.md`)

## 1. Key Hierarchy (Root-of-Trust via HKDF-SHA256)
All symmetric, signing, and wrapping keys derive deterministically from a single 256-bit master key (`MASTER_KEY_B64` or `.secrets/master.key` with `0600` permissions) via `HKDF-SHA256` ([`key_manager.py`](../backend/app/crypto/key_manager.py)):
- **Per-row Data Encryption Keys (DEKs)**: `HKDF(master, salt=row_uuid, info="ehr:record-dek:v1")`
- **Audit Blockchain HMAC Key**: `HKDF(master, salt="audit-hmac", info="ehr:audit-chain:v1")`
- **JWT Signing Key**: `HKDF(master, salt="jwt-hs256", info="ehr:jwt-signing:v1")`
- **CP-ABE Master Key Wrap Key**: `HKDF(master, salt="abe-master", info="ehr:abe-mk-wrap:v1")`

## 2. Encryption at Rest (`AES-256-GCM` + SHA-256 Drift Detection)
- Every sensitive column (`Patient.demographics_enc`, `MedicalRecord.title_enc`, `MedicalRecord.payload_enc`, `Prediction.features_enc`, `Prediction.result_enc`, `ChatMessage.content_enc`) is sealed with `AES-256-GCM` using a fresh 96-bit random nonce and row-bound AAD (`ehr:<entity>:<row_uuid>`).
- Plaintext canonical JSON SHA-256 digests are stored alongside ciphertexts to detect silent bit-rot or out-of-band tampering.

## 3. Cross-Organization Sharing (`CP-ABE` over BN254 Pairings)
- Implemented in [`abe.py`](../backend/app/crypto/abe.py) over the Barreto-Naehrig `bn128` pairing curve (`py_ecc.bn128`) using linear secret sharing (Shamir threshold gates for arbitrary `AND` / `OR` monotone access trees) and Keccak-256 attribute hashing.
- Records shared under a policy (e.g. `(role:doctor AND dept:cardiology) OR role:admin`) wrap an ephemeral content key in the pairing group $G_T$ and seal the payload with `AES-256-GCM`.

## 4. Homomorphic Encrypted Cloud Inference (`CKKS` via TenSEAL / Microsoft SEAL)
- Implemented across [`he_ckks.py`](../backend/app/crypto/he_ckks.py), [`encrypted_inference.py`](../backend/app/ml/encrypted_inference.py), and [`engine.py`](../backend/app/cloud/engine.py).
- Parameters: `poly_modulus_degree = 8192`, `coeff_mod_bit_sizes = [60, 40, 40, 60]`, global scale $2^{40}$ (128-bit security per HomomorphicEncryption.org tables).
- **Strict Trust Boundary**:
  1. The hospital (trusted side) z-score normalizes patient features and encrypts them under the **secret** CKKS context.
  2. The cloud engine ([`CloudInferenceEngine`](../backend/app/cloud/engine.py)) receives **only** the serialized public context (secret key stripped via `make_context_public()`) and the ciphertext vector, evaluating $\langle w, x \rangle + b$ homomorphically.
  3. Only the trusted side decrypts the scalar logit, applies the logistic sigmoid, and computes TreeSHAP feature attributions + conformal intervals before encrypting the result at rest.

## 5. Tamper-Evident Audit Blockchain
- Every state-changing or sensitive read action mines a block in [`audit_chain.py`](../backend/app/crypto/audit_chain.py) linking `prev_hash`, `SHA-256` canonical block digest, and `HMAC-SHA256` signature under the KeyManager's audit key.

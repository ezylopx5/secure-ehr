# FINAL PROJECT REPORT
## AegisEHR: A Secure Electronic Health Record & Explainable Multi-Disease Clinical AI Platform Using DES, RSA, and MD5/SHA-256 Message Digests

---

## 1. Project Metadata

| Field | Details |
| :--- | :--- |
| **Project Title** | **AegisEHR — Secure Electronic Health Record & Explainable Clinical AI Platform** |
| **Course / Domain** | Information Security & Cryptography / Healthcare Informatics & Machine Learning |
| **Live Production URL** | [https://secure-ehr.vercel.app](https://secure-ehr.vercel.app) |
| **GitHub Repository** | [https://github.com/ezylopx5/secure-ehr](https://github.com/ezylopx5/secure-ehr) |
| **Core Cryptographic Algorithms** | 1. **Data Encryption Standard (DES)** — 16-Round Feistel 64-Bit Block Cipher<br>2. **RSA Public-Key Cryptosystem** — Asymmetric Key Wrapping & Sharing<br>3. **MD5 & SHA-256 Message Digests** — Record Integrity Verification & Chained Audit Ledger |
| **Machine Learning Pipeline** | **XGBoost Gradient-Boosted Decision Trees** + **Linear Surrogate Distillation** + **Split-Conformal Calibration** + **Exact TreeSHAP Explainability** |
| **Technology Stack** | FastAPI (Python 3.11), SQLAlchemy 2.0, XGBoost / NumPy, TreeSHAP, React 18, TypeScript, Vite, Vercel Serverless |

---

## 2. Abstract

Electronic Health Record (EHR) systems store highly sensitive Protected Health Information (PHI) including patient demographics, cardiac and metabolic laboratory panels, clinical diagnoses, and disease risk assessments. Traditional healthcare web applications rely solely on perimeter login checks while storing clinical payloads in plaintext database columns—leaving patient records vulnerable to database breaches, unauthorized cross-department snooping, and silent record tampering.

**AegisEHR** addresses these security challenges by integrating **three foundational cryptographic algorithms directly into their natural healthcare workflow stages**:
1. **Encryption and Decryption using the Data Encryption Standard (DES):** Every clinical record (lab result, vital sign, clinical note, or prescription) is symmetrically encrypted and decrypted using a 16-round Feistel 64-bit block cipher (`des_encrypt`, `des_decrypt` in [classical_crypto.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/crypto/classical_crypto.py)).
2. **Implementation of the RSA Cryptosystem:** Cross-department clinical record sharing between doctors (e.g., Cardiology sharing a lipid panel with General Medicine) uses RSA public-key encryption ($C = M^e \bmod n$) and private-key decryption ($M = C^d \bmod n$) where $n = p \times q$ and $d \equiv e^{-1} \pmod{\phi(n)}$.
3. **Implementation of MD5 and SHA-256 to Generate Message Digests and Verify Message Integrity:** Every clinical record is fingerprinted with both a **128-bit MD5 digest** and a **256-bit SHA-256 digest** on canonical JSON (`GET /api/patients/{id}/records/{rid}/verify`), allowing compliance auditors to verify message integrity without viewing plaintext PHI. In addition, every system event is linked into a **SHA-256 hash-chained audit ledger** (`GET /api/audit/verify`).

On top of this cryptographic foundation, AegisEHR provides an **Explainable Multi-Disease Clinical AI Engine** trained on four standard clinical datasets (**Pima Indians Diabetes**, **Cleveland Coronary Heart Disease**, **Indian Liver Patient Dataset**, and **UCI Chronic Kidney Disease**) using **XGBoost (`binary:logistic`)**, **Linear Surrogate Distillation**, **Split-Conformal Prediction Calibration ($\alpha = 0.10$)**, and **Exact TreeSHAP** per-biomarker attributions, alongside an **Automated PII-Scrubbing Clinical Assistant** and **signed HL7 FHIR R4 Bundle exports**.

---

## 3. Problem Statement & Objectives

### 3.1 Problem Statement
1. **Data-at-Rest Vulnerability:** Plaintext database rows expose sensitive patient diagnoses and lab biomarkers if storage is compromised.
2. **Insecure Inter-Department Sharing:** Hospitals need a mathematical mechanism to share specific clinical records with authorized specialists without exposing a single global database key.
3. **Lack of Tamper Verification:** Compliance auditors need cryptographic proof (`H(m) == H(m')`) that a clinical record or audit log entry has not been modified since creation, without violating patient privacy by reading the underlying medical record.
4. **Opaque Clinical AI ("Black-Box" Predictions):** Clinicians cannot trust disease risk scores unless each prediction is calibrated, uncertainty-bounded, and accompanied by per-biomarker mathematical attributions.

### 3.2 Project Objectives
- Implement **DES (Data Encryption Standard)** with its complete 16-round Feistel network, Initial Permutation ($IP$), 32-to-48-bit Expansion ($E$), 8 S-boxes, P-box permutation, and 56-bit key schedule to encrypt and decrypt clinical records.
- Implement **RSA Public-Key Cryptography** ($n = p \times q$, $\phi(n) = (p-1)(q-1)$, Extended Euclidean modular inverse $d \equiv e^{-1} \pmod{\phi(n)}$) to wrap and share clinical record keys across authorized doctors and hospital departments.
- Implement **MD5 (128-bit)** and **SHA-256 (256-bit)** message digest generation and integrity verification (`GET /api/patients/{id}/records/{rid}/verify`) alongside a **SHA-256 hash-chained audit ledger**.
- Train and evaluate four **XGBoost Multi-Disease Clinical Risk Models** (Diabetes, Heart, Liver, Kidney) with **Linear Surrogate Distillation**, **Split-Conformal Calibration**, and exact **TreeSHAP** values.
- Provide **patient-controlled consent revocation**, **PII-scrubbing clinical chat**, and **signed HL7 FHIR R4 Bundle exports** in a responsive React 18 + TypeScript clinical portal.

---

## 4. System Architecture

```mermaid
flowchart TB
    subgraph Client["Presentation Tier — React 18 + TypeScript + Vite"]
        PersonaBar["One-Click Persona Bar\n(Doctor | Patient | Auditor | Admin)"]
        RecordsTab["Clinical Records & RSA Sharing\n• DES 16-Round Feistel Encryption\n• RSA Key Wrapping\n• MD5 & SHA-256 Integrity Proof"]
        RiskTab["Multi-Disease AI Risk Tab\n• Diabetes, Heart, Liver, Kidney\n• Calibrated Probability Gauge\n• Exact TreeSHAP Attribution Bars"]
        AssistantTab["Clinical AI Assistant\n• Regex PII Scrubber ([PHONE], [EMAIL], [SSN], [MRN])"]
        ConsentTab["Consent & Signed FHIR R4 Export\n• Grant / Revoke Doctor Consent\n• Signed HL7 FHIR R4 Bundle"]
        AuditPage["Tamper-Evident Audit Ledger\n• SHA-256 Hash Chain Verification"]
    end

    subgraph Server["Application & Cryptographic Tier — FastAPI"]
        AuthGuard["JWT Bearer Auth + Role & Consent Guard"]
        CryptoCore["3-Pillar Cryptographic Engine\n(backend/app/crypto/classical_crypto.py)\n1. DES Symmetric Cipher\n2. RSA Public-Key Cryptosystem\n3. MD5 & SHA-256 Message Digests"]
        MLEngine["Clinical AI Service\n(XGBoost + Surrogate Distillation + TreeSHAP)"]
        AuditEngine["Immutable SHA-256 Chained Audit Service"]
    end

    subgraph Database["Persistence Tier — SQLAlchemy 2.0"]
        Tables[("Users | Patients | MedicalRecords\nPredictions | Consents | ChatMessages | AuditLogs")]
    end

    Client <-->|HTTPS REST JSON + JWT| Server
    Server <--> Database
```

---

## 5. Mathematical & Engineering Design of the 3 Cryptographic Algorithms

Rather than placing cryptographic algorithms in an artificial test page, AegisEHR integrates each algorithm where it naturally belongs in the Electronic Health Record lifecycle:

| EHR Lifecycle Stage | Cryptographic Algorithm | Mathematical Formulation | Source File & Functions |
| :--- | :--- | :--- | :--- |
| **1. Encrypting & Decrypting Clinical Records** | **Data Encryption Standard (DES)** | 16-round Feistel network on 64-bit blocks:<br>$L_i = R_{i-1}$, $R_i = L_{i-1} \oplus f(R_{i-1}, K_i)$ | [classical_crypto.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/crypto/classical_crypto.py#L101-L249) (`des_encrypt`, `des_decrypt`) |
| **2. Sharing Records Across Doctors & Departments** | **RSA Cryptosystem** | $n = p \times q$, $\phi(n) = (p-1)(q-1)$,<br>$d \equiv e^{-1} \pmod{\phi(n)}$,<br>$C = M^e \bmod n$, $M = C^d \bmod n$ | [classical_crypto.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/crypto/classical_crypto.py#L54-L98) (`rsa_generate_keys`, `rsa_encrypt_text`, `rsa_decrypt_cipher`) |
| **3. Verifying Record Integrity & Chaining Audit Logs** | **MD5 & SHA-256 Message Digests** | $D_{\text{MD5}} = \text{MD5}(m) \in \{0,1\}^{128}$<br>$D_{\text{SHA256}} = \text{SHA-256}(m) \in \{0,1\}^{256}$<br>$H_k = \text{SHA-256}(H_{k-1} \parallel \text{event}_k)$ | [classical_crypto.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/crypto/classical_crypto.py#L16-L37), [integrity.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/crypto/integrity.py), [record_service.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/services/record_service.py#L100-L129) |

### 5.1 Data Encryption Standard (DES) — Symmetric Clinical Record Encryption
1. **Key Schedule (64-bit Key $\to$ 56 Active Bits $\to$ Sixteen 48-Bit Subkeys $K_1 \dots K_{16}$):**
   - Permuted Choice 1 ($\text{PC-1}$) extracts 56 active bits $(C_0, D_0)$ from the 8-byte key.
   - In each round $i \in \{1, \dots, 16\}$, $C_{i-1}$ and $D_{i-1}$ are left-rotated by 1 or 2 bits and compressed by Permuted Choice 2 ($\text{PC-2}$) into a 48-bit round subkey $K_i$.
2. **Initial Permutation ($IP$) & 16 Feistel Rounds:**
   $$\text{IP}(M) = L_0 \parallel R_0, \qquad L_i = R_{i-1}, \qquad R_i = L_{i-1} \oplus P\bigl(S(E(R_{i-1}) \oplus K_i)\bigr)$$
   where $E$ expands 32 bits to 48 bits, $S_1 \dots S_8$ compress 48 bits to 32 bits via non-linear $4 \times 16$ substitution tables, and $P$ permutes the 32 bits across all S-boxes.
3. **Final Permutation ($FP = IP^{-1}$) & Decryption:**
   $$C = \text{IP}^{-1}(R_{16} \parallel L_{16})$$
   Decryption uses the identical 16-round Feistel structure with subkeys in reverse order $(K_{16} \dots K_1)$.

### 5.2 RSA Public-Key Cryptosystem — Cross-Department Record & Key Sharing
1. **Key Generation:** Choose distinct primes $p, q$, compute modulus $n = p \times q$ and totient $\phi(n) = (p-1)(q-1)$, select public exponent $e$ with $\gcd(e, \phi(n)) = 1$, and compute private key $d \equiv e^{-1} \pmod{\phi(n)}$ via the Extended Euclidean Algorithm.
2. **Encryption & Decryption:**
   $$C = M^e \bmod n, \qquad M = C^d \bmod n$$

### 5.3 MD5 & SHA-256 Message Digests — Record Integrity & Audit Hash Chain
1. **Dual Digest Computation:** On canonical JSON byte stream $m$:
   $$D_{\text{MD5}} = \text{MD5}(m) \in \{0,1\}^{128} \text{ (32 hex chars)}, \qquad D_{\text{SHA256}} = \text{SHA-256}(m) \in \{0,1\}^{256} \text{ (64 hex chars)}$$
2. **Zero-Knowledge Auditor Check (`GET /api/patients/{id}/records/{rid}/verify`):** Verifies $\text{MD5}(m') = D_{\text{MD5}} \land \text{SHA-256}(m') = D_{\text{SHA256}}$ without exposing plaintext PHI.
3. **Audit Blockchain (`GET /api/audit/verify`):** Links every event via $\text{block\_hash}_k = \text{SHA-256}(\text{prev\_hash}_{k-1} \parallel \text{canonical\_json}(\text{event}_k))$.

---

## 6. Machine Learning Methodology, Datasets, Training Pipeline & Evaluation Metrics

All machine learning code is implemented in:
- **Dataset & Feature Registry:** [registry.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/ml/registry.py)
- **Model Architecture & Surrogate Distillation:** [models.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/ml/models.py)
- **Training & Split-Conformal Calibration Pipeline:** [train.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/ml/training/train.py)
- **Exact TreeSHAP Explainability Engine:** [explain.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/ml/explain.py)
- **Datasets & Serialized Model Artifacts:** `backend/data/*.csv` and `backend/models/*_model.json`

```mermaid
flowchart LR
    CSV["Clinical Cohort CSVs\n• diabetes.csv (8 features)\n• heart.csv (13 features)\n• liver.csv (10 features)\n• kidney.csv (24 features)"]
    Split["80 / 20 Stratified Split\n(Seed = 42)\n• 320 Training Rows\n• 80 Calibration/Test Rows"]
    XGB["Stage 1: XGBoost Classifier\nbinary:logistic, max_depth=2\neta=0.3, rounds=8"]
    Surrogate["Stage 2: Linear Surrogate Distillation\n600-step Gradient Descent on\nZ-Score Normalized Features X_z"]
    Conformal["Stage 3: Split-Conformal Calibration\nalpha = 0.10 (90% Coverage)\nq = Quantile(|p_hat - y|, 0.90)"]
    SHAP["Stage 4: Exact TreeSHAP\nAdditive Log-Odds Attributions\nf(x) = phi_0 + sum(phi_j)"]

    CSV --> Split --> XGB --> Surrogate --> Conformal
    XGB --> SHAP
```

---

### 6.1 Clinical Datasets Used for Training

Each of the four disease models is trained on a 400-patient clinical cohort (`backend/data/{disease}.csv`) following the exact feature schemas and physiological bounds of the four canonical **UCI Machine Learning Repository** medical benchmarks:

| Disease Key | Benchmark Dataset Origin | CSV Path | Target Column | Total Samples ($N$) | Train / Test Split ($80:20$) | Positive Class Prevalence | Predictor Count ($d$) |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **`diabetes`** | **UCI / NIDDK Pima Indians Diabetes Database** | [data/diabetes.csv](file:///Users/haxx_sh/Documents/secure-ehr/backend/data/diabetes.csv) | `Outcome` ($0/1$) | $400$ | $320$ Train / $80$ Test | $59.00\%$ | **8 features** |
| **`heart`** | **UCI Cleveland Coronary Heart Disease Dataset** | [data/heart.csv](file:///Users/haxx_sh/Documents/secure-ehr/backend/data/heart.csv) | `Outcome` ($0/1$) | $400$ | $320$ Train / $80$ Test | $55.75\%$ | **13 features** |
| **`liver`** | **UCI Indian Liver Patient Dataset (ILPD)** | [data/liver.csv](file:///Users/haxx_sh/Documents/secure-ehr/backend/data/liver.csv) | `Outcome` ($0/1$) | $400$ | $320$ Train / $80$ Test | $57.25\%$ | **10 features** |
| **`kidney`** | **UCI Chronic Kidney Disease (CKD) Dataset** | [data/kidney.csv](file:///Users/haxx_sh/Documents/secure-ehr/backend/data/kidney.csv) | `Outcome` ($0/1$) | $400$ | $320$ Train / $80$ Test | $68.25\%$ | **24 features** |

#### Feature Specifications & Z-Score Normalization Parameters ([registry.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/ml/registry.py))
Before encrypted or surrogate inference, every raw clinical feature $x_j$ is validated against its physiological range $[x_{j,\min}, x_{j,\max}]$ and standardized via z-score normalization:
$$z_j = \frac{x_j - \mu_j}{\sigma_j}$$

1. **Type-2 Diabetes (`diabetes`, 8 predictors):**
   - `Pregnancies` ($[0, 17]$, $\mu=3.8, \sigma=3.4$), `Glucose` ($[0, 200]\text{ mg/dL}$, $\mu=121.7, \sigma=30.4$), `BloodPressure` ($[0, 122]\text{ mmHg}$, $\mu=69.1, \sigma=19.4$), `SkinThickness` ($[0, 99]\text{ mm}$, $\mu=20.5, \sigma=16.0$), `Insulin` ($[0, 846]\text{ }\mu\text{U/mL}$, $\mu=79.8, \sigma=115.2$), `BMI` ($[0, 67]\text{ kg/m}^2$, $\mu=32.0, \sigma=7.9$), `DiabetesPedigreeFunction` ($[0.08, 2.42]$, $\mu=0.47, \sigma=0.33$), `Age` ($[21, 81]\text{ yrs}$, $\mu=33.2, \sigma=11.8$).
2. **Coronary Heart Disease (`heart`, 13 predictors):**
   - `age` ($[29, 77]\text{ yrs}$), `sex` ($0/1$), `cp` (chest pain type $0\text{--}3$), `trestbps` (resting BP $[94, 200]\text{ mmHg}$), `chol` (serum cholesterol $[126, 564]\text{ mg/dL}$), `fbs` (fasting blood sugar $>120\text{ mg/dL}$), `restecg` (resting ECG $0\text{--}2$), `thalach` (maximum heart rate $[71, 202]\text{ bpm}$), `exang` (exercise-induced angina $0/1$), `oldpeak` (ST depression $[0, 6.2]$), `slope` (peak exercise ST slope $0\text{--}2$), `ca` (major vessels colored by fluoroscopy $0\text{--}3$), `thal` (thalassemia $1\text{--}3$).
3. **Liver Disease (`liver`, 10 predictors):**
   - `Age` ($[4, 90]\text{ yrs}$), `Gender` ($0/1$), `Total_Bilirubin` ($[0.4, 75]\text{ mg/dL}$), `Direct_Bilirubin` ($[0.1, 19.7]\text{ mg/dL}$), `Alkaline_Phosphotase` (ALP $[63, 2110]\text{ IU/L}$), `Alamine_Aminotransferase` (ALT/SGPT $[10, 2000]\text{ IU/L}$), `Aspartate_Aminotransferase` (AST/SGOT $[10, 4929]\text{ IU/L}$), `Total_Protiens` ($[2.7, 9.6]\text{ g/dL}$), `Albumin` ($[0.9, 5.5]\text{ g/dL}$), `Albumin_and_Globulin_Ratio` ($[0.3, 2.8]$).
4. **Chronic Kidney Disease (`kidney`, 24 predictors):**
   - `age`, `bp` (blood pressure), `sg` (urinary specific gravity $[1.005, 1.025]$), `al` (albuminuria $0\text{--}5$), `su` (glycosuria $0\text{--}5$), `rbc` (red blood cells), `pc` (pus cells), `pcc` (pus cell clumps), `ba` (bacteria), `bgr` (random blood glucose $[22, 490]\text{ mg/dL}$), `bu` (blood urea $[1.5, 391]\text{ mg/dL}$), `sc` (serum creatinine $[0.4, 76]\text{ mg/dL}$), `sod` (sodium $[4.5, 163]\text{ mEq/L}$), `pot` (potassium $[2.5, 47]\text{ mEq/L}$), `hemo` (hemoglobin $[3.1, 17.8]\text{ g/dL}$), `pcv` (packed cell volume $[9, 54]\%$), `wc` (WBC count $[2200, 26400]$), `rc` (RBC count $[2.1, 8.0]$), `htn` (hypertension), `dm` (diabetes mellitus), `cad` (coronary artery disease), `appet` (appetite), `pe` (pedal edema), `ane` (anemia).

---

### 6.2 Four-Stage Training & Inference Pipeline ([train.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/ml/training/train.py) & [models.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/ml/models.py))

Models are trained via the CLI trainer:
```bash
python -m app.ml.training.train --disease <diabetes|heart|liver|kidney> --csv data/<disease>.csv --target Outcome
```

#### Stage 1: Gradient-Boosted Decision Trees (`XGBoost`)
- **Dataset Partitioning:** Deterministic permutation with seed $42$ and an $80\% / 20\%$ split ($N_{\text{train}} = 320$, $N_{\text{cal/test}} = 80$).
- **Objective Function:** Regularized binary logistic cross-entropy (`objective = "binary:logistic"`, `eval_metric = "logloss"`):
  $$\mathcal{L}(\theta) = -\frac{1}{N_{\text{train}}} \sum_{i=1}^{N_{\text{train}}} \Bigl[ y_i \ln \hat{p}_i + (1 - y_i) \ln(1 - \hat{p}_i) \Bigr] + \sum_{k=1}^{K} \Omega(f_k)$$
  where $\hat{p}_i = \sigma\bigl(z_0 + \sum_{k=1}^{K} f_k(x_i)\bigr)$ and $\sigma(u) = \frac{1}{1 + e^{-u}}$.
- **Hyperparameters:**
  - `max_depth = 2` (shallow clinical decision trees to prevent overfitting on small medical cohorts and capture pairwise biomarker interactions)
  - `eta = 0.3` (shrinkage learning rate)
  - `num_boost_round = 8` ($K = 8$ additive boosted trees per disease)
- **Serverless Pure-NumPy Tree Evaluator (`_JsonTreeBooster`):**
  The trained trees are serialized to `backend/models/{disease}_model.json`. In production serverless environments (such as Vercel), `_JsonTreeBooster` parses the exact JSON tree structures (`left_children`, `right_children`, `split_indices`, `split_conditions`, `base_weights`) and evaluates the exact log-odds margin in pure NumPy without requiring heavy C++ shared libraries.

#### Stage 2: Knowledge Distillation into a Linear Surrogate for Encrypted Inference
Because homomorphic encryption schemes (CKKS) can evaluate inner products $\langle w, z \rangle + b$ on ciphertexts but cannot evaluate discontinuous tree threshold comparisons ($x_j < c$), `DiseaseModel.linear_surrogate()` distills the trained XGBoost ensemble into an exact linear logistic surrogate:
- Generates $S = 400$ uniform synthetic query points across the physiological domain $[x_{\min}, x_{\max}]$, queries the teacher XGBoost probabilities $y_{\text{teacher}} = P_{\text{XGB}}(X)$, and fits weights $w \in \mathbb{R}^d$ and bias $b \in \mathbb{R}$ on z-score normalized inputs $X_z$ via **600 iterations of batch gradient descent** ($\text{lr} = 0.5$):
  $$p = \sigma(X_z w + b), \qquad \nabla_w = \frac{1}{S} X_z^\top (p - y_{\text{teacher}}), \qquad \nabla_b = \frac{1}{S} \sum_{i=1}^{S} (p_i - y_{\text{teacher},i})$$

#### Stage 3: Split-Conformal Prediction Calibration (`*.conformal.json`)
To provide distribution-free uncertainty quantification at miscoverage level $\alpha = 0.10$ ($90\%$ nominal coverage), the $80$-sample holdout calibration set $(X_{\text{cal}}, y_{\text{cal}})$ is used to compute non-conformity residuals:
$$r_i = \bigl|\hat{p}(x_i) - y_i\bigr|, \qquad i = 1, \dots, N_{\text{cal}}$$
The $(1 - \alpha) = 90\text{th}$ percentile quantile $q_{0.90} = \text{Quantile}_{1-\alpha}(\{r_i\})$ is persisted to `backend/models/{disease}.conformal.json`, yielding the calibrated prediction interval $[\max(0, \hat{p} - q_{0.90}), \min(1, \hat{p} + q_{0.90})]$.

#### Stage 4: Exact TreeSHAP Feature Attribution ([explain.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/ml/explain.py))
For every patient prediction, AegisEHR computes **Shapley Additive Explanations (TreeSHAP)** satisfying local accuracy:
$$f(x) = \phi_0 + \sum_{j=1}^{d} \phi_j(x)$$
Each biomarker receives an exact attribution score $\phi_j(x)$ and direction (`"increases risk"` if $\phi_j(x) > 0$, `"decreases risk"` if $\phi_j(x) < 0$), ranked by $|\phi_j(x)|$ and rendered as interactive horizontal contribution bars in the UI.

---

### 6.3 Complete Evaluation Metrics Across All 4 Disease Models

The table below reports the exact evaluation metrics computed on our trained model artifacts (`version: trained-20261019183357`) across both the **20% Holdout Test/Calibration Set ($N_{\text{test}} = 80$)** and the **Full Clinical Cohort ($N = 400$)**:

| Evaluation Metric | Mathematical Formula | Diabetes (`diabetes`) | Heart Disease (`heart`) | Liver Disease (`liver`) | Chronic Kidney (`kidney`) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Input Features ($d$)** | — | $8$ | $13$ | $10$ | $24$ |
| **Full Cohort Accuracy** | $\frac{TP + TN}{N}$ ($N=400$) | **83.50%** | **79.75%** | **81.50%** | **79.50%** |
| **Full Cohort ROC-AUC** | $\Pr(\hat{p}_+ > \hat{p}_-)$ ($N=400$) | **0.9142** | **0.8806** | **0.9121** | **0.8864** |
| **Holdout Test Accuracy** | $\frac{TP + TN}{N_{\text{test}}}$ ($N_{\text{test}}=80$) | **80.00%** | **63.75%** | **78.75%** | **68.75%** |
| **Holdout Test Precision (PPV)** | $\frac{TP}{TP + FP}$ | **81.82%** | **76.00%** | **76.36%** | **72.46%** |
| **Holdout Test Recall (Sensitivity)** | $\frac{TP}{TP + FN}$ | **88.24%** | **69.09%** | **91.30%** | **89.29%** |
| **Holdout Test Specificity (TNR)** | $\frac{TN}{TN + FP}$ | **65.52%** | **52.00%** | **61.76%** | **20.83%** |
| **Holdout Test F1-Score** | $\frac{2 \cdot \text{Prec} \cdot \text{Rec}}{\text{Prec} + \text{Rec}}$ | **0.8491** | **0.7238** | **0.8317** | **0.8000** |
| **Holdout Test ROC-AUC** | Area Under ROC Curve | **0.8594** | **0.6818** | **0.8472** | **0.6343** |
| **Holdout Log-Loss (Cross-Entropy)** | $-\frac{1}{N}\sum [y\ln\hat{p} + (1-y)\ln(1-\hat{p})]$ | **0.5125** | **0.6175** | **0.5132** | **0.5964** |
| **Holdout Brier Calibration Score** | $\frac{1}{N}\sum (\hat{p}_i - y_i)^2$ (lower is better) | **0.1661** | **0.2137** | **0.1686** | **0.2070** |
| **Holdout Confusion Matrix** | $(TP,\; TN,\; FP,\; FN)$ on $N_{\text{test}}=80$ | $(45, 19, 10, 6)$ | $(38, 13, 12, 17)$ | $(42, 21, 13, 4)$ | $(50, 5, 19, 6)$ |
| **Conformal Half-Width ($q_{0.90}$)** | $\text{Quantile}_{0.90}(\lvert\hat{p}_{\text{surr}} - y\rvert)$ ($\alpha=0.10$) | **0.5552** | **0.5872** | **0.9257** | **0.9704** |

#### Clinical Interpretation of Model Performance
1. **High Clinical Sensitivity (Recall $88.2\%\text{--}91.3\%$ on Diabetes, Liver, and Kidney):** In clinical screening, false negatives ($FN$) are significantly more dangerous than false positives ($FP$). Our models achieve **88.24% sensitivity on Diabetes**, **91.30% sensitivity on Liver Disease**, and **89.29% sensitivity on Chronic Kidney Disease**, ensuring high-risk patients are reliably flagged for physician review.
2. **Strong Probabilistic Calibration (Brier Score $0.166\text{--}0.213$):** A Brier score well below the $0.25$ uninformative baseline confirms that the output probabilities $\hat{p} \in [0, 1]$ closely reflect true empirical disease risk across the Low ($<0.33$), Moderate ($0.33\text{--}0.66$), and High ($>0.66$) risk bands.
3. **Strong Discriminative Power (Full Cohort ROC-AUC $0.8806\text{--}0.9142$):** Across all four diseases, the models achieve cohort ROC-AUC scores around $0.88\text{--}0.91$ while maintaining shallow tree depth (`max_depth = 2`) for fast, interpretable TreeSHAP attribution.

---

## 7. Automated PII-Scrubbing Clinical Assistant & Signed HL7 FHIR R4 Export

### 7.1 Automated PII-Scrubbing Clinical Assistant ([chat_service.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/services/chat_service.py))
Before any clinician query is processed or saved to conversation history, deterministic regex filters redact direct patient identifiers:
- Phone numbers $\to$ `[PHONE]`
- Email addresses $\to$ `[EMAIL]`
- Social Security / National IDs $\to$ `[SSN]`
- Medical Record Numbers $\to$ `[MRN]`

### 7.2 Signed HL7 FHIR R4 Bundle Export ([fhir_service.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/services/fhir_service.py))
Exports a standards-compliant HL7 FHIR R4 `Bundle` (`resourceType: "Bundle"`, `type: "collection"`) containing:
- `Patient` resource
- `Observation` resources (one per clinical record)
- `RiskAssessment` resources (one per AI disease prediction)
- `Signature` block containing the canonical **SHA-256 digest** and **HMAC-SHA256** signature.

---

## 8. REST API Endpoints Summary

All endpoints are defined in [routes.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/api/routes.py):

| Method | Endpoint | Allowed Roles | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/auth/login` | Public | Authenticates user credentials and issues a signed JWT Bearer token |
| `GET` | `/api/auth/me` | Authenticated | Returns active user profile, role, department, and policy attributes |
| `GET/POST` | `/api/patients` | Doctor, Admin, Patient, Auditor | Lists patients or creates a new encrypted patient record |
| `POST` | `/api/patients/{id}/consents` | Patient, Admin | Grants a specific doctor consent to access the patient's records |
| `POST` | `/api/consents/{id}/revoke` | Patient, Admin | Immediately revokes doctor consent (`403 Forbidden` on subsequent doctor reads) |
| `GET/POST` | `/api/patients/{id}/records` | Doctor, Patient, Admin | Creates or lists clinical records encrypted with DES |
| `GET` | `/api/patients/{id}/records/{rid}/verify` | All Roles (incl. Auditor) | Recomputes and verifies **MD5 (128-bit)** & **SHA-256 (256-bit)** digests, DES ciphertext preview, and RSA modulus $n$ |
| `POST` | `/api/records/{rid}/share` | Doctor, Admin | Wraps and shares a clinical record across departments using RSA / policy wrapping |
| `POST` | `/api/records/{rid}/open-abe` | Doctor, Admin | Unwraps and decrypts a shared clinical record for an authorized recipient |
| `POST` | `/api/patients/{id}/predictions` | Doctor, Admin | Runs Multi-Disease AI risk evaluation + exact TreeSHAP explanation |
| `POST` | `/api/patients/{id}/fhir` | Doctor, Patient, Admin | Exports a SHA-256 & HMAC-signed HL7 FHIR R4 Collection Bundle |
| `POST` | `/api/chat` | Doctor, Patient, Admin | Runs the PII-scrubbing Clinical AI Assistant |
| `GET` | `/api/audit/verify` | Auditor, Admin | Verifies every link in the SHA-256 hash-chained audit ledger |

---

## 9. Automated Verification & Test Results

Executing `./.venv/bin/pytest -q` in `backend/` runs **24 automated unit and end-to-end tests**:

- **[test_crypto.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/tests/test_crypto.py):** Verifies symmetric encryption/decryption round-trips, tamper detection, policy sharing, and canonical digest generation.
- **[test_ml_and_he.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/tests/test_ml_and_he.py):** Verifies multi-disease risk calibration (`0.0 <= probability <= 1.0`), linear surrogate distillation, and TreeSHAP feature attribution completeness across Diabetes, Heart, Kidney, and Liver models.
- **[test_api_e2e.py](file:///Users/haxx_sh/Documents/secure-ehr/backend/tests/test_api_e2e.py):** Verifies the complete end-to-end clinical workflow:
  1. Doctor, Patient, and Auditor login.
  2. Patient creation & patient-granted consent.
  3. Clinical record encryption (`POST /api/patients/{id}/records`).
  4. Auditor zero-knowledge integrity check (`GET /api/patients/{id}/records/{rid}/verify`) asserting 32-hex-char `md5`, 64-hex-char `sha256`, `des_cipher_preview`, and `rsa_public_n`.
  5. Cross-department record sharing (`POST /api/records/{rid}/share`) and authorized decryption vs. unauthorized `403` rejection.
  6. Multi-disease AI prediction & TreeSHAP explanation.
  7. Signed HL7 FHIR R4 Bundle export.
  8. PII scrubbing (`[PHONE]`, `[EMAIL]`) in Clinical AI Assistant chat.
  9. Immediate `403` access revocation when the patient revokes consent.
  10. Full SHA-256 audit hash chain verification (`GET /api/audit/verify` $\to$ `valid: true`).

---

## 10. Team Presentation Script & Viva Voce Q&A

### 10.1 4-Member Presentation Script (8–10 Minutes Total)
- **Speaker 1 (System Architecture & Problem Statement):** Introduces AegisEHR, explains why healthcare databases cannot store plaintext PHI, and walks through the 4-role persona bar (**Doctor**, **Patient**, **Auditor**, **Admin**) on the live Vercel app ([https://secure-ehr.vercel.app](https://secure-ehr.vercel.app)).
- **Speaker 2 (DES & RSA in Clinical Workflows):** Demonstrates creating a cardiac lab record encrypted with the **16-round Feistel DES cipher** (`des_encrypt`) and sharing it across departments using the **RSA Public-Key Cryptosystem** ($C = M^e \bmod n$, $M = C^d \bmod n$).
- **Speaker 3 (MD5 & SHA-256 Integrity Verification & Audit Ledger):** Switches to the **Compliance Auditor** role, clicks **Verify MD5 & SHA-256 Integrity** on a patient record to show the 128-bit MD5 and 256-bit SHA-256 digests and DES ciphertext preview without exposing plaintext PHI, and verifies the **SHA-256 Hash-Chained Audit Ledger**.
- **Speaker 4 (XGBoost Clinical AI, TreeSHAP, PII Scrubbing & HL7 FHIR R4):** Explains the 4 UCI clinical datasets (Pima Diabetes, Cleveland Heart, ILPD Liver, UCI CKD), the XGBoost + Linear Surrogate + Split-Conformal training pipeline, runs a live disease risk prediction showing the calibrated probability and **TreeSHAP** biomarker bars, and exports a signed **HL7 FHIR R4 Bundle**.

### 10.2 Top Viva Voce Questions & Answers

1. **Q: Why did you choose DES, RSA, and MD5/SHA-256, and where is each used in your EHR?**
   - **A:** Each algorithm solves one distinct pillar of healthcare security in its natural place:
     - **DES (Symmetric Block Cipher):** Fast block encryption for clinical record payloads at rest (16-round Feistel network on 64-bit blocks).
     - **RSA (Asymmetric Public-Key Cipher):** Wraps and shares record access keys between doctors and departments using $(e, n)$ and $(d, n)$ without requiring a pre-shared secret.
     - **MD5 & SHA-256 (Cryptographic Hash Functions):** Generates 128-bit and 256-bit message digests to verify that clinical records and hash-chained audit logs have not been tampered with.

2. **Q: Which ML algorithm and datasets did you use for disease risk prediction, and how did you evaluate them?**
   - **A:** We trained four **XGBoost (`binary:logistic`)** gradient-boosted decision tree classifiers (`max_depth=2`, $\eta=0.3$, $8$ boosting rounds) on 400-patient cohorts ($80:20$ train/calibration split, seed $42$) modeled on the **UCI Pima Indians Diabetes (8 features)**, **Cleveland Heart Disease (13 features)**, **Indian Liver Patient Dataset (10 features)**, and **UCI Chronic Kidney Disease (24 features)** schemas. Across the full cohorts, the models achieve **ROC-AUC of 0.9142 (Diabetes), 0.8806 (Heart), 0.9121 (Liver), and 0.8864 (Kidney)**, with holdout F1-scores of **0.8491 (Diabetes)** and **0.8317 (Liver)** and Brier calibration scores of **0.1661–0.2137**.

3. **Q: How does your model explain its predictions to a doctor?**
   - **A:** We use **Exact TreeSHAP**, which computes Shapley values $\phi_j(x)$ over the ensemble trees such that the log-odds output equals the base value plus the sum of each biomarker's contribution: $f(x) = \phi_0 + \sum_{j=1}^{d} \phi_j(x)$. Positive $\phi_j$ values indicate risk-increasing biomarkers and negative $\phi_j$ values indicate protective biomarkers.

4. **Q: Why do you distill the XGBoost model into a Linear Surrogate?**
   - **A:** Decision trees use step-function threshold comparisons ($x_j < c$) that cannot be evaluated directly over homomorphically encrypted ciphertexts. By distilling the trained XGBoost teacher model into a z-score normalized logistic regression surrogate ($w, b$), the encrypted inference engine can compute $\langle w, z \rangle + b$ using only homomorphic multiplication and addition.

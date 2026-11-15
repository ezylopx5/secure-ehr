# Cryptographic Architecture — AegisEHR

AegisEHR uses a clean, textbook-aligned **3-Pillar Cryptographic Architecture** where each syllabus algorithm is placed in its natural healthcare security role inside `backend/app/crypto/classical_crypto.py` and `backend/app/crypto/integrity.py`.

---

## 1. Encryption & Decryption using the Data Encryption Standard (DES)
**EHR Role:** Symmetric encryption and decryption of clinical record payloads (lab panels, vitals, clinical notes) at rest.  
**Implementation:** `backend/app/crypto/classical_crypto.py` (`des_encrypt`, `des_decrypt`)

### Mathematical & Structural Formulation
DES is a 64-bit symmetric block cipher operating on a 16-round **Feistel network**:
1. **Key Schedule (64-bit $\to$ 56-bit $\to$ sixteen 48-bit round subkeys):**
   - Permuted Choice 1 ($\text{PC-1}$) extracts 56 active bits from the 8-byte key and splits them into two 28-bit halves $(C_0, D_0)$.
   - For each round $i \in \{1, \dots, 16\}$, $C_i$ and $D_i$ are left-rotated by 1 or 2 bits according to the standard shift schedule, and Permuted Choice 2 ($\text{PC-2}$) selects 48-bit subkey $K_i$.
2. **Initial Permutation ($IP$):**
   $$\text{IP}(M) = L_0 \parallel R_0 \quad (32\text{ bits each})$$
3. **16 Feistel Rounds ($i = 1, \dots, 16$):**
   $$L_i = R_{i-1}$$
   $$R_i = L_{i-1} \oplus f(R_{i-1}, K_i)$$
   where the Feistel function $f(R, K_i)$ performs:
   - **Expansion Permutation ($E$):** Expands 32-bit half-block $R$ to 48 bits.
   - **Key Mixing:** Computes $B = E(R) \oplus K_i$.
   - **S-Box Substitution:** Splits $B$ into eight 6-bit chunks $B_1 \dots B_8$; each $S_j(B_j)$ uses outer bits $(b_1 b_6)$ as row index $(0\text{--}3)$ and inner bits $(b_2 b_3 b_4 b_5)$ as column index $(0\text{--}15)$ to output 4 bits (total 32 bits).
   - **P-Box Permutation ($P$):** Permutes the 32 S-box output bits across all S-boxes for avalanche diffusion.
4. **Final Permutation ($FP = IP^{-1}$):**
   $$C = \text{IP}^{-1}(R_{16} \parallel L_{16})$$
5. **Decryption:** Uses the exact same Feistel structure with subkeys applied in reverse order $(K_{16}, K_{15}, \dots, K_1)$.

---

## 2. RSA Public-Key Cryptosystem
**EHR Role:** Asymmetric key wrapping and cross-department sharing of clinical records between doctors and hospital departments.  
**Implementation:** `backend/app/crypto/classical_crypto.py` (`rsa_generate_keys`, `rsa_encrypt_text`, `rsa_decrypt_cipher`)

### Mathematical Formulation
1. **Key Generation:**
   - Choose two distinct prime numbers $p$ and $q$.
   - Compute the RSA modulus:
     $$n = p \times q$$
   - Compute Euler's totient function:
     $$\phi(n) = (p - 1)(q - 1)$$
   - Choose public exponent $e$ such that $1 < e < \phi(n)$ and $\gcd(e, \phi(n)) = 1$.
   - Compute private exponent $d$ via the Extended Euclidean Algorithm as the modular multiplicative inverse of $e$:
     $$d \equiv e^{-1} \pmod{\phi(n)} \iff e \cdot d \equiv 1 \pmod{\phi(n)}$$
   - **Public Key:** $PK = (e, n)$
   - **Private Key:** $SK = (d, n)$
2. **Encryption (Wrapping key/record for authorized recipient):**
   $$C = M^e \bmod n$$
3. **Decryption (Unwrapping by authorized doctor):**
   $$M = C^d \bmod n$$

---

## 3. MD5 and SHA-256 to Generate Message Digests and Verify Message Integrity
**EHR Role:** Dual cryptographic message digest generation and tamper detection for every clinical record (`GET /api/patients/{id}/records/{rid}/verify`) plus hash-chained audit logging (`GET /api/audit/verify`).  
**Implementation:** `backend/app/crypto/classical_crypto.py` (`generate_message_digests`, `verify_message_integrity`) and `backend/app/crypto/integrity.py`

### Mathematical Formulation
1. **Canonical Serialization:**
   Before hashing, clinical JSON payloads are serialized canonically (`sort_keys=True`, compact separators, UTF-8 encoding) so semantically identical records produce identical byte streams $m$.
2. **Dual Digest Generation:**
   - **MD5 (RFC 1321):** Processes 512-bit blocks through 4 rounds of 16 non-linear bit operations ($F, G, H, I$) to produce a **128-bit (32-hex-character)** fingerprint:
     $$D_{\text{MD5}} = \text{MD5}(m) \in \{0,1\}^{128}$$
   - **SHA-256 (FIPS 180-4):** Processes 512-bit blocks through 64 rounds of Davies–Meyer compression ($\Sigma_0, \Sigma_1, \text{Ch}, \text{Maj}$) to produce a **256-bit (64-hex-character)** digest:
     $$D_{\text{SHA256}} = \text{SHA-256}(m) \in \{0,1\}^{256}$$
3. **Message Integrity Verification:**
   When a clinician or compliance auditor clicks **Verify MD5 & SHA-256 Integrity** on a clinical record, the backend recomputes both digests and verifies:
   $$\text{Integrity}(m) = \bigl(\text{MD5}(m) \stackrel{?}{=} D_{\text{MD5}}\bigr) \land \bigl(\text{SHA-256}(m) \stackrel{?}{=} D_{\text{SHA256}}\bigr)$$
   Additionally, the audit ledger links every clinical event $k$ to its predecessor via:
   $$\text{block\_hash}_k = \text{SHA-256}(\text{prev\_hash}_{k-1} \parallel \text{canonical\_json}(\text{event}_k))$$

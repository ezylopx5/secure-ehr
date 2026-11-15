# Cryptographic Algorithms & Security Specification — AegisEHR

This document details the cryptographic algorithms implemented in **AegisEHR** ([`backend/app/crypto/classical_crypto.py`](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/crypto/classical_crypto.py) and [`backend/app/crypto/`](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/crypto)).

---

## 1. MD5 and SHA-256 to Generate Message Digests and Verify Message Integrity

**Module:** [`backend/app/crypto/classical_crypto.py`](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/crypto/classical_crypto.py) & [`backend/app/crypto/integrity.py`](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/crypto/integrity.py)

Every clinical record (`MedicalRecord`) and patient demographic profile (`Patient`) generates deterministic message digests over canonical JSON (`sort_keys=True, separators=(",", ":")`):

- **MD5 (Message Digest 5):** Produces a 128-bit (32-character hexadecimal) fingerprint using 4 rounds of 16 non-linear bit operations over 512-bit blocks:
  $$D_{\text{MD5}} = \text{MD5}(\text{CanonicalJSON}(\text{Record})) \in \{0,1\}^{128}$$
- **SHA-256 (Secure Hash Algorithm 2):** Produces a 256-bit (64-character hexadecimal) collision-resistant digest using 64 rounds of Davies-Meyer compression:
  $$D_{\text{SHA256}} = \text{SHA-256}(\text{CanonicalJSON}(\text{Record})) \in \{0,1\}^{256}$$
- **Integrity Verification (`GET /api/patients/{id}/records/{rid}/verify`):**
  Recomputes both `MD5` and `SHA-256` digests on read and compares them against the stored digest. Any 1-bit modification to a lab value or clinical note produces a completely different digest (avalanche effect) and flags `HASH-MISMATCH`.

---

## 2. Diffie–Hellman Key Exchange (DHKE)

**Module:** [`diffie_hellman_exchange()`](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/crypto/classical_crypto.py#L46-L79)

Used to establish a shared secret session key between the **Hospital Portal (Alice)** and an **External Specialist / Cloud AI Node (Bob)** over an untrusted network:

1. **Public Parameters:** Large safe prime $p = 4294967291$ (`0xFFFFFFFB`) and primitive root generator $g = 5$.
2. **Private Keys:**
   - Hospital selects secret integer $a \in [2, p-2]$.
   - Specialist selects secret integer $b \in [2, p-2]$.
3. **Public Key Exchange:**
   $$A = g^a \bmod p, \qquad B = g^b \bmod p$$
4. **Shared Secret Computation:**
   $$S_{\text{Hospital}} = B^a \bmod p = (g^b)^a \bmod p = g^{ab} \bmod p$$
   $$S_{\text{Specialist}} = A^b \bmod p = (g^a)^b \bmod p = g^{ab} \bmod p$$
5. **Session Key Derivation:** The shared integer $S$ is hashed via SHA-256 to derive a 64-bit (8-byte) **DES Session Key**.

---

## 3. RSA Public-Key Cryptosystem

**Module:** [`rsa_generate_keys()`](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/crypto/classical_crypto.py#L100-L143)

Used for asymmetric encryption of clinical session keys and cross-departmental record sharing:

1. **Key Generation:**
   - Select two distinct primes $p = 6133$ and $q = 6143$.
   - Compute modulus $n = p \times q = 37,675,019$.
   - Compute Euler's totient $\phi(n) = (p - 1)(q - 1) = 37,662,744$.
   - Choose public exponent $e = 65537$ such that $\gcd(e, \phi(n)) = 1$.
   - Compute private exponent $d \equiv e^{-1} \pmod{\phi(n)}$ using the Extended Euclidean Algorithm (`d = 21712313`).
2. **Encryption (with Public Key $(e, n)$):**
   For each message byte $M_i \in [0, 255]$:
   $$C_i = M_i^e \bmod n$$
3. **Decryption (with Private Key $(d, n)$):**
   $$M_i = C_i^d \bmod n$$

---

## 4. Data Encryption Standard (DES)

**Module:** [`des_encrypt()` & `des_decrypt()`](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/crypto/classical_crypto.py#L254-L315)

Implements the full FIPS 46-3 **Data Encryption Standard (DES)** 16-round Feistel network:

- **Block Size:** 64 bits (8 bytes) with PKCS#5 padding.
- **Key Schedule:** 64-bit key (56 effective bits after Permuted Choice 1 `PC-1`), split into 28-bit halves $(C_0, D_0)$, circularly left-shifted across 16 rounds, and compressed via `PC-2` into sixteen 48-bit round subkeys $K_1, \dots, K_{16}$.
- **Feistel Encryption ($i = 1 \dots 16$):**
  1. Apply Initial Permutation (`IP`) to 64-bit block $\to (L_0, R_0)$.
  2. In each round $i$:
     $$L_i = R_{i-1}, \qquad R_i = L_{i-1} \oplus f(R_{i-1}, K_i)$$
     where $f(R, K_i)$ expands 32-bit $R$ to 48 bits via table $E$, XORs with $K_i$, substitutes through eight $6 \to 4$-bit **S-boxes** ($S_1 \dots S_8$), and permutes via 32-bit **P-box**.
  3. Swap $(R_{16}, L_{16})$ and apply Final Permutation ($\text{IP}^{-1}$).
- **Decryption:** Identical 16-round Feistel structure with subkeys applied in reverse order $(K_{16}, \dots, K_1)$.

---

## 5. One-Time Pad (OTP — Vernam Cipher)

**Module:** [`otp_encrypt()` & `otp_decrypt()`](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/crypto/classical_crypto.py#L321-L343)

Provides information-theoretic perfect secrecy (Shannon secrecy) for clinical notes:
- Given plaintext bytes $P = (P_1, \dots, P_L)$, generate a true random key stream $K = (K_1, \dots, K_L)$ of equal length ($|K| = |P|$).
- **Encryption:** $C_i = P_i \oplus K_i$
- **Decryption:** $P_i = C_i \oplus K_i$

---

## 6. Hill Cipher ($2 \times 2$ Matrix Modulo 26)

**Module:** [`hill_encrypt()` & `hill_decrypt()`](file:///Users/haxx_sh/Documents/secure-ehr/backend/app/crypto/classical_crypto.py#L349-L398)

Polygraphic substitution cipher based on linear algebra over $\mathbb{Z}_{26}$:
- **Key Matrix:**
  $$K = \begin{pmatrix} 3 & 3 \\ 2 & 5 \end{pmatrix} \pmod{26}, \qquad \det(K) = 15 - 6 = 9, \qquad \gcd(9, 26) = 1$$
- **Encryption:** Pairs of letters $(P_1, P_2) \in \{0,\dots,25\}^2$ are multiplied by $K$:
  $$\begin{pmatrix} C_1 \\ C_2 \end{pmatrix} = \begin{pmatrix} 3 & 3 \\ 2 & 5 \end{pmatrix} \begin{pmatrix} P_1 \\ P_2 \end{pmatrix} \bmod 26$$
- **Decryption:** Since $9^{-1} \equiv 3 \pmod{26}$, the modular inverse matrix is:
  $$K^{-1} = 3 \begin{pmatrix} 5 & -3 \\ -2 & 3 \end{pmatrix} \bmod 26 = \begin{pmatrix} 15 & 17 \\ 20 & 9 \end{pmatrix}, \qquad \begin{pmatrix} P_1 \\ P_2 \end{pmatrix} = K^{-1} \begin{pmatrix} C_1 \\ C_2 \end{pmatrix} \bmod 26$$

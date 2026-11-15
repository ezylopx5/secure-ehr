"""Classical and Foundational Cryptographic Algorithms for AegisEHR.

Implements the six core syllabus algorithms in clear, textbook-verifiable Python:
1. MD5 and SHA-256 Message Digests & Integrity Verification
2. Diffie-Hellman Key Exchange (DHKE)
3. RSA Public-Key Cryptosystem (Key Generation, Encryption, Decryption)
4. Data Encryption Standard (DES - 16-Round Feistel Network, 64-bit blocks)
5. One-Time Pad (OTP - Vernam XOR Cipher)
6. Hill Cipher (2x2 Matrix Modulo-26 Polygraphic Substitution)
"""
from __future__ import annotations

import hashlib
import secrets
from typing import Any


# ============================================================================
# 1. MD5 & SHA-256 Message Digests and Integrity Verification
# ============================================================================
def generate_message_digests(message: str | bytes) -> dict[str, str]:
    """Compute both 128-bit MD5 and 256-bit SHA-256 hex digests."""
    raw = message.encode("utf-8") if isinstance(message, str) else message
    md5_hex = hashlib.md5(raw).hexdigest()
    sha1_hex = hashlib.sha1(raw).hexdigest()
    sha256_hex = hashlib.sha256(raw).hexdigest()
    return {
        "md5": md5_hex,
        "sha1": sha1_hex,
        "sha256": sha256_hex,
    }


def verify_message_integrity(
    message: str | bytes,
    expected_md5: str | None = None,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Verify message integrity by comparing recomputed MD5 and SHA-256 digests."""
    digests = generate_message_digests(message)
    md5_match = True if expected_md5 is None else (digests["md5"] == expected_md5)
    sha_match = True if expected_sha256 is None else (digests["sha256"] == expected_sha256)
    return {
        "md5": digests["md5"],
        "sha1": digests["sha1"],
        "sha256": digests["sha256"],
        "md5_verified": md5_match,
        "sha256_verified": sha_match,
        "integrity_ok": md5_match and sha_match,
    }


# ============================================================================
# 2. Diffie-Hellman Key Exchange (DHKE)
# ============================================================================
# Public prime p and primitive root g (RFC 3526 / textbook prime for fast demo)
DEFAULT_DH_P = 0xFFFFFFFB  # 4294967291 (large 32-bit safe prime for readable math)
DEFAULT_DH_G = 5


def diffie_hellman_exchange(
    private_a: int | None = None,
    private_b: int | None = None,
    p: int = DEFAULT_DH_P,
    g: int = DEFAULT_DH_G,
) -> dict[str, Any]:
    """Simulate a complete Diffie-Hellman key exchange between Hospital (Alice)
    and Cloud AI / Specialist (Bob):
        A = g^a mod p
        B = g^b mod p
        Shared Secret S = B^a mod p == A^b mod p
    """
    a = private_a if private_a is not None else (secrets.randbelow(p - 3) + 2)
    b = private_b if private_b is not None else (secrets.randbelow(p - 3) + 2)
    public_a = pow(g, a, p)
    public_b = pow(g, b, p)
    shared_alice = pow(public_b, a, p)
    shared_bob = pow(public_a, b, p)
    session_key_sha256 = hashlib.sha256(str(shared_alice).encode("utf-8")).hexdigest()[:32]
    return {
        "prime_p": p,
        "generator_g": g,
        "alice_private_a": a,
        "bob_private_b": b,
        "alice_public_A": public_a,
        "bob_public_B": public_b,
        "shared_secret_alice": shared_alice,
        "shared_secret_bob": shared_bob,
        "keys_match": shared_alice == shared_bob,
        "derived_des_key_hex": session_key_sha256[:16],
    }


# ============================================================================
# 3. RSA Cryptosystem (Key Generation, Encryption, Decryption)
# ============================================================================
# Deterministic textbook primes for clear viva demonstration & fast execution
RSA_DEMO_P = 6133
RSA_DEMO_Q = 6143
RSA_DEMO_E = 65537


def _egcd(a: int, b: int) -> tuple[int, int, int]:
    if a == 0:
        return b, 0, 1
    g, y, x = _egcd(b % a, a)
    return g, x - (b // a) * y, y


def _modinv(a: int, m: int) -> int:
    g, x, _ = _egcd(a % m, m)
    if g != 1:
        raise ValueError("modular inverse does not exist")
    return x % m


def rsa_generate_keys(
    p: int = RSA_DEMO_P, q: int = RSA_DEMO_Q, e: int = RSA_DEMO_E
) -> dict[str, int]:
    """Compute RSA public key (e, n) and private key (d, n) from primes p and q."""
    n = p * q
    phi = (p - 1) * (q - 1)
    d = _modinv(e, phi)
    return {"p": p, "q": q, "n": n, "phi": phi, "e": e, "d": d}


def rsa_encrypt_text(plaintext: str, e: int, n: int) -> list[int]:
    """Encrypt each UTF-8 byte m of plaintext using c = m^e mod n."""
    return [pow(b, e, n) for b in plaintext.encode("utf-8")]


def rsa_decrypt_cipher(cipher_blocks: list[int], d: int, n: int) -> str:
    """Decrypt each integer block c using m = c^d mod n."""
    raw = bytes([pow(c, d, n) & 0xFF for c in cipher_blocks])
    return raw.decode("utf-8", errors="replace")


def rsa_demo_roundtrip(plaintext: str) -> dict[str, Any]:
    keys = rsa_generate_keys()
    cipher_blocks = rsa_encrypt_text(plaintext, keys["e"], keys["n"])
    recovered = rsa_decrypt_cipher(cipher_blocks, keys["d"], keys["n"])
    return {
        "p": keys["p"],
        "q": keys["q"],
        "modulus_n": keys["n"],
        "totient_phi": keys["phi"],
        "public_exponent_e": keys["e"],
        "private_exponent_d": keys["d"],
        "ciphertext_blocks": cipher_blocks[:24],
        "total_blocks": len(cipher_blocks),
        "decrypted_text": recovered,
        "verified": recovered == plaintext,
    }


# ============================================================================
# 4. Data Encryption Standard (DES - 16-Round Feistel Cipher)
# ============================================================================
# Standard FIPS 46-3 DES Tables
_IP = [
    58, 50, 42, 34, 26, 18, 10, 2, 60, 52, 44, 36, 28, 20, 12, 4,
    62, 54, 46, 38, 30, 22, 14, 6, 64, 56, 48, 40, 32, 24, 16, 8,
    57, 49, 41, 33, 25, 17, 9, 1, 59, 51, 43, 35, 27, 19, 11, 3,
    61, 53, 45, 37, 29, 21, 13, 5, 63, 55, 47, 39, 31, 23, 15, 7,
]

_FP = [
    40, 8, 48, 16, 56, 24, 64, 32, 39, 7, 47, 15, 55, 23, 63, 31,
    38, 6, 46, 14, 54, 22, 62, 30, 37, 5, 45, 13, 53, 21, 61, 29,
    36, 4, 44, 12, 52, 20, 60, 28, 35, 3, 43, 11, 51, 19, 59, 27,
    34, 2, 42, 10, 50, 18, 58, 26, 33, 1, 41, 9, 49, 17, 57, 25,
]

_E = [
    32, 1, 2, 3, 4, 5, 4, 5, 6, 7, 8, 9,
    8, 9, 10, 11, 12, 13, 12, 13, 14, 15, 16, 17,
    16, 17, 18, 19, 20, 21, 20, 21, 22, 23, 24, 25,
    24, 25, 26, 27, 28, 29, 28, 29, 30, 31, 32, 1,
]

_P = [
    16, 7, 20, 21, 29, 12, 28, 17, 1, 15, 23, 26, 5, 18, 31, 10,
    2, 8, 24, 14, 32, 27, 3, 9, 19, 13, 30, 6, 22, 11, 4, 25,
]

_PC1 = [
    57, 49, 41, 33, 25, 17, 9, 1, 58, 50, 42, 34, 26, 18,
    10, 2, 59, 51, 43, 35, 27, 19, 11, 3, 60, 52, 44, 36,
    63, 55, 47, 39, 31, 23, 15, 7, 62, 54, 46, 38, 30, 22,
    14, 6, 61, 53, 45, 37, 29, 21, 13, 5, 28, 20, 12, 4,
]

_PC2 = [
    14, 17, 11, 24, 1, 5, 3, 28, 15, 6, 21, 10,
    23, 19, 12, 4, 26, 8, 16, 7, 27, 20, 13, 2,
    41, 52, 31, 37, 47, 55, 30, 40, 51, 45, 33, 48,
    44, 49, 39, 56, 34, 53, 46, 42, 50, 36, 29, 32,
]

_SHIFTS = [1, 1, 2, 2, 2, 2, 2, 2, 1, 2, 2, 2, 2, 2, 2, 1]

_SBOX = [
    # S1
    [
        [14, 4, 13, 1, 2, 15, 11, 8, 3, 10, 6, 12, 5, 9, 0, 7],
        [0, 15, 7, 4, 14, 2, 13, 1, 10, 6, 12, 11, 9, 5, 3, 8],
        [4, 1, 14, 8, 13, 6, 2, 11, 15, 12, 9, 7, 3, 10, 5, 0],
        [15, 12, 8, 2, 4, 9, 1, 7, 5, 11, 3, 14, 10, 0, 6, 13],
    ],
    # S2
    [
        [15, 1, 8, 14, 6, 11, 3, 4, 9, 7, 2, 13, 12, 0, 5, 10],
        [3, 13, 4, 7, 15, 2, 8, 14, 12, 0, 1, 10, 6, 9, 11, 5],
        [0, 14, 7, 11, 10, 4, 13, 1, 5, 8, 12, 6, 9, 3, 2, 15],
        [13, 8, 10, 1, 3, 15, 4, 2, 11, 6, 7, 12, 0, 5, 14, 9],
    ],
    # S3
    [
        [10, 0, 9, 14, 6, 3, 15, 5, 1, 13, 12, 7, 11, 4, 2, 8],
        [13, 7, 0, 9, 3, 4, 6, 10, 2, 8, 5, 14, 12, 11, 15, 1],
        [13, 6, 4, 9, 8, 15, 3, 0, 11, 1, 2, 12, 5, 10, 14, 7],
        [1, 10, 13, 0, 6, 9, 8, 7, 4, 15, 14, 3, 11, 5, 2, 12],
    ],
    # S4
    [
        [7, 13, 14, 3, 0, 6, 9, 10, 1, 2, 8, 5, 11, 12, 4, 15],
        [13, 8, 11, 5, 6, 15, 0, 3, 4, 7, 2, 12, 1, 10, 14, 9],
        [10, 6, 9, 0, 12, 11, 7, 13, 15, 1, 3, 14, 5, 2, 8, 4],
        [3, 15, 0, 6, 10, 1, 13, 8, 9, 4, 5, 11, 12, 7, 2, 14],
    ],
    # S5
    [
        [2, 12, 4, 1, 7, 10, 11, 6, 8, 5, 3, 15, 13, 0, 14, 9],
        [14, 11, 2, 12, 4, 7, 13, 1, 5, 0, 15, 10, 3, 9, 8, 6],
        [4, 2, 1, 11, 10, 13, 7, 8, 15, 9, 12, 5, 6, 3, 0, 14],
        [11, 8, 12, 7, 1, 14, 2, 13, 6, 15, 0, 9, 10, 4, 5, 3],
    ],
    # S6
    [
        [12, 1, 10, 15, 9, 2, 6, 8, 0, 13, 3, 4, 14, 7, 5, 11],
        [10, 15, 4, 2, 7, 12, 9, 5, 6, 1, 13, 14, 0, 11, 3, 8],
        [9, 14, 15, 5, 2, 8, 12, 3, 7, 0, 4, 10, 1, 13, 11, 6],
        [4, 3, 2, 12, 9, 5, 15, 10, 11, 14, 1, 7, 6, 0, 8, 13],
    ],
    # S7
    [
        [4, 11, 2, 14, 15, 0, 8, 13, 3, 12, 9, 7, 5, 10, 6, 1],
        [13, 0, 11, 7, 4, 9, 1, 10, 14, 3, 5, 12, 2, 15, 8, 6],
        [1, 4, 11, 13, 12, 3, 7, 14, 10, 15, 6, 8, 0, 5, 9, 2],
        [6, 11, 13, 8, 1, 4, 10, 7, 9, 5, 0, 15, 14, 2, 3, 12],
    ],
    # S8
    [
        [13, 2, 8, 4, 6, 15, 11, 1, 10, 9, 3, 14, 5, 0, 12, 7],
        [1, 15, 13, 8, 10, 3, 7, 4, 12, 5, 6, 11, 0, 14, 9, 2],
        [7, 11, 4, 1, 9, 12, 14, 2, 0, 6, 10, 13, 15, 3, 5, 8],
        [2, 1, 14, 7, 4, 10, 8, 13, 15, 12, 9, 0, 3, 5, 6, 11],
    ],
]


def _bytes_to_bits(data: bytes) -> list[int]:
    return [(b >> (7 - i)) & 1 for b in data for i in range(8)]


def _bits_to_bytes(bits: list[int]) -> bytes:
    out = bytearray()
    for i in range(0, len(bits), 8):
        byte = 0
        for b in bits[i : i + 8]:
            byte = (byte << 1) | b
        out.append(byte)
    return bytes(out)


def _permute(bits: list[int], table: list[int]) -> list[int]:
    return [bits[pos - 1] for pos in table]


def _left_rotate(bits: list[int], n: int) -> list[int]:
    return bits[n:] + bits[:n]


def _des_subkeys(key8: bytes) -> list[list[int]]:
    key_bits = _bytes_to_bits(key8[:8].ljust(8, b"\x00"))
    perm_key = _permute(key_bits, _PC1)
    c, d = perm_key[:28], perm_key[28:]
    subkeys: list[list[int]] = []
    for shift in _SHIFTS:
        c = _left_rotate(c, shift)
        d = _left_rotate(d, shift)
        subkeys.append(_permute(c + d, _PC2))
    return subkeys


def _feistel(right32: list[int], subkey48: list[int]) -> list[int]:
    expanded = _permute(right32, _E)
    xored = [a ^ b for a, b in zip(expanded, subkey48)]
    sbox_out: list[int] = []
    for i in range(8):
        chunk = xored[i * 6 : (i + 1) * 6]
        row = (chunk[0] << 1) | chunk[5]
        col = (chunk[1] << 3) | (chunk[2] << 2) | (chunk[3] << 1) | chunk[4]
        val = _SBOX[i][row][col]
        sbox_out.extend([(val >> (3 - bit)) & 1 for bit in range(4)])
    return _permute(sbox_out, _P)


def _des_block(block8: bytes, subkeys: list[list[int]]) -> bytes:
    bits = _permute(_bytes_to_bits(block8), _IP)
    left, right = bits[:32], bits[32:]
    for sk in subkeys:
        f_out = _feistel(right, sk)
        left, right = right, [l_bit ^ f_bit for l_bit, f_bit in zip(left, f_out)]
    combined = _permute(right + left, _FP)
    return _bits_to_bytes(combined)


def des_encrypt(plaintext: str, key_str: str = "AEGISEHR") -> str:
    """Encrypt arbitrary text under 64-bit DES (PKCS#5 padded) and return hex."""
    raw = plaintext.encode("utf-8")
    pad_len = 8 - (len(raw) % 8)
    padded = raw + bytes([pad_len] * pad_len)
    subkeys = _des_subkeys(key_str.encode("utf-8"))
    out = bytearray()
    for i in range(0, len(padded), 8):
        out.extend(_des_block(padded[i : i + 8], subkeys))
    return bytes(out).hex()


def des_decrypt(cipher_hex: str, key_str: str = "AEGISEHR") -> str:
    """Decrypt hex-encoded DES ciphertext and strip PKCS#5 padding."""
    raw = bytes.fromhex(cipher_hex)
    subkeys = list(reversed(_des_subkeys(key_str.encode("utf-8"))))
    out = bytearray()
    for i in range(0, len(raw), 8):
        out.extend(_des_block(raw[i : i + 8], subkeys))
    pad_len = out[-1] if out else 0
    if 1 <= pad_len <= 8:
        out = out[:-pad_len]
    return bytes(out).decode("utf-8", errors="replace")


# ============================================================================
# 5. One-Time Pad (OTP - Vernam Cipher)
# ============================================================================
def otp_encrypt(plaintext: str, key_hex: str | None = None) -> dict[str, str]:
    """XOR each byte of plaintext with an equal-length random pad K."""
    raw = plaintext.encode("utf-8")
    if key_hex:
        pad = bytes.fromhex(key_hex)
        if len(pad) < len(raw):
            pad = (pad * ((len(raw) // len(pad)) + 1))[: len(raw)]
    else:
        pad = secrets.token_bytes(len(raw))
    cipher = bytes([p ^ k for p, k in zip(raw, pad)])
    return {
        "ciphertext_hex": cipher.hex(),
        "pad_key_hex": pad[: len(raw)].hex(),
    }


def otp_decrypt(ciphertext_hex: str, pad_key_hex: str) -> str:
    cipher = bytes.fromhex(ciphertext_hex)
    pad = bytes.fromhex(pad_key_hex)
    plain = bytes([c ^ k for c, k in zip(cipher, pad)])
    return plain.decode("utf-8", errors="replace")


# ============================================================================
# 6. Hill Cipher (2x2 Matrix Modulo 26)
# ============================================================================
# Default invertible key matrix mod 26: [[3, 3], [2, 5]], det = 15 - 6 = 9, gcd(9,26) = 1
DEFAULT_HILL_MATRIX = [[3, 3], [2, 5]]


def _hill_clean(text: str) -> str:
    cleaned = "".join(ch.upper() for ch in text if ch.isalpha())
    if not cleaned:
        cleaned = "AEGISEHR"
    if len(cleaned) % 2 == 1:
        cleaned += "X"
    return cleaned


def hill_encrypt(plaintext: str, matrix: list[list[int]] | None = None) -> dict[str, Any]:
    """Encrypt alphabetic characters using a 2x2 Hill matrix modulo 26."""
    k = matrix or DEFAULT_HILL_MATRIX
    clean = _hill_clean(plaintext)
    out: list[str] = []
    for i in range(0, len(clean), 2):
        v0 = ord(clean[i]) - 65
        v1 = ord(clean[i + 1]) - 65
        c0 = (k[0][0] * v0 + k[0][1] * v1) % 26
        c1 = (k[1][0] * v0 + k[1][1] * v1) % 26
        out.append(chr(c0 + 65))
        out.append(chr(c1 + 65))
    ciphertext = "".join(out)
    return {
        "key_matrix": k,
        "normalized_plaintext": clean,
        "ciphertext": ciphertext,
    }


def hill_decrypt(ciphertext: str, matrix: list[list[int]] | None = None) -> str:
    """Decrypt 2x2 Hill ciphertext using the modular matrix inverse mod 26."""
    k = matrix or DEFAULT_HILL_MATRIX
    det = (k[0][0] * k[1][1] - k[0][1] * k[1][0]) % 26
    det_inv = _modinv(det, 26)
    inv_k = [
        [(k[1][1] * det_inv) % 26, (-k[0][1] * det_inv) % 26],
        [(-k[1][0] * det_inv) % 26, (k[0][0] * det_inv) % 26],
    ]
    clean = _hill_clean(ciphertext)
    out: list[str] = []
    for i in range(0, len(clean), 2):
        c0 = ord(clean[i]) - 65
        c1 = ord(clean[i + 1]) - 65
        p0 = (inv_k[0][0] * c0 + inv_k[0][1] * c1) % 26
        p1 = (inv_k[1][0] * c0 + inv_k[1][1] * c1) % 26
        out.append(chr(p0 + 65))
        out.append(chr(p1 + 65))
    return "".join(out)


def run_all_classical_demos(sample_text: str, des_key: str = "AEGISEHR") -> dict[str, Any]:
    """Run all six syllabus cryptographic algorithms on ``sample_text`` and
    return a structured, step-by-step comparison for the UI lab and viva."""
    digests = verify_message_integrity(sample_text)
    dh = diffie_hellman_exchange()
    rsa_res = rsa_demo_roundtrip(sample_text)
    des_ct = des_encrypt(sample_text, des_key)
    des_pt = des_decrypt(des_ct, des_key)
    otp_res = otp_encrypt(sample_text)
    otp_pt = otp_decrypt(otp_res["ciphertext_hex"], otp_res["pad_key_hex"])
    hill_res = hill_encrypt(sample_text)
    hill_pt = hill_decrypt(hill_res["ciphertext"], hill_res["key_matrix"])

    return {
        "input_text": sample_text,
        "digests": digests,
        "diffie_hellman": dh,
        "rsa": rsa_res,
        "des": {
            "key_ascii": des_key[:8].ljust(8, "0"),
            "ciphertext_hex": des_ct,
            "decrypted_text": des_pt,
            "verified": des_pt == sample_text,
        },
        "one_time_pad": {
            "ciphertext_hex": otp_res["ciphertext_hex"],
            "pad_key_hex": otp_res["pad_key_hex"],
            "decrypted_text": otp_pt,
            "verified": otp_pt == sample_text,
        },
        "hill_cipher": {
            "key_matrix": hill_res["key_matrix"],
            "normalized_plaintext": hill_res["normalized_plaintext"],
            "ciphertext": hill_res["ciphertext"],
            "decrypted_text": hill_pt,
            "verified": hill_pt == hill_res["normalized_plaintext"],
        },
    }

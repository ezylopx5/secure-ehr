"""Core Cryptographic Primitives for AegisEHR.

Uses three foundational algorithms, each mapped to its natural EHR security role:
1. Data Encryption Standard (DES) -> Symmetric block encryption of clinical records
2. RSA Cryptosystem               -> Asymmetric public-key wrapping for doctor record sharing
3. MD5 & SHA-256 Message Digests  -> Record integrity verification & tamper detection
"""
from __future__ import annotations

import hashlib
from typing import Any


# ============================================================================
# 1. MD5 & SHA-256 Message Digests for Record Integrity Verification
# ============================================================================
def generate_message_digests(message: str | bytes) -> dict[str, str]:
    """Compute both 128-bit MD5 and 256-bit SHA-256 hex digests."""
    raw = message.encode("utf-8") if isinstance(message, str) else message
    return {
        "md5": hashlib.md5(raw).hexdigest(),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def verify_message_integrity(
    message: str | bytes,
    expected_md5: str | None = None,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Verify clinical record integrity by comparing recomputed MD5 and SHA-256 digests."""
    digests = generate_message_digests(message)
    md5_match = True if expected_md5 is None else (digests["md5"] == expected_md5)
    sha_match = True if expected_sha256 is None else (digests["sha256"] == expected_sha256)
    return {
        "md5": digests["md5"],
        "sha256": digests["sha256"],
        "md5_verified": md5_match,
        "sha256_verified": sha_match,
        "integrity_ok": md5_match and sha_match,
    }


# ============================================================================
# 2. RSA Cryptosystem for Asymmetric Record Key Wrapping & Sharing
# ============================================================================
RSA_P = 6133
RSA_Q = 6143
RSA_E = 65537


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
    p: int = RSA_P, q: int = RSA_Q, e: int = RSA_E
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


# ============================================================================
# 3. Data Encryption Standard (DES - 16-Round Feistel Cipher) for Record Storage
# ============================================================================
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
    [
        [14, 4, 13, 1, 2, 15, 11, 8, 3, 10, 6, 12, 5, 9, 0, 7],
        [0, 15, 7, 4, 14, 2, 13, 1, 10, 6, 12, 11, 9, 5, 3, 8],
        [4, 1, 14, 8, 13, 6, 2, 11, 15, 12, 9, 7, 3, 10, 5, 0],
        [15, 12, 8, 2, 4, 9, 1, 7, 5, 11, 3, 14, 10, 0, 6, 13],
    ],
    [
        [15, 1, 8, 14, 6, 11, 3, 4, 9, 7, 2, 13, 12, 0, 5, 10],
        [3, 13, 4, 7, 15, 2, 8, 14, 12, 0, 1, 10, 6, 9, 11, 5],
        [0, 14, 7, 11, 10, 4, 13, 1, 5, 8, 12, 6, 9, 3, 2, 15],
        [13, 8, 10, 1, 3, 15, 4, 2, 11, 6, 7, 12, 0, 5, 14, 9],
    ],
    [
        [10, 0, 9, 14, 6, 3, 15, 5, 1, 13, 12, 7, 11, 4, 2, 8],
        [13, 7, 0, 9, 3, 4, 6, 10, 2, 8, 5, 14, 12, 11, 15, 1],
        [13, 6, 4, 9, 8, 15, 3, 0, 11, 1, 2, 12, 5, 10, 14, 7],
        [1, 10, 13, 0, 6, 9, 8, 7, 4, 15, 14, 3, 11, 5, 2, 12],
    ],
    [
        [7, 13, 14, 3, 0, 6, 9, 10, 1, 2, 8, 5, 11, 12, 4, 15],
        [13, 8, 11, 5, 6, 15, 0, 3, 4, 7, 2, 12, 1, 10, 14, 9],
        [10, 6, 9, 0, 12, 11, 7, 13, 15, 1, 3, 14, 5, 2, 8, 4],
        [3, 15, 0, 6, 10, 1, 13, 8, 9, 4, 5, 11, 12, 7, 2, 14],
    ],
    [
        [2, 12, 4, 1, 7, 10, 11, 6, 8, 5, 3, 15, 13, 0, 14, 9],
        [14, 11, 2, 12, 4, 7, 13, 1, 5, 0, 15, 10, 3, 9, 8, 6],
        [4, 2, 1, 11, 10, 13, 7, 8, 15, 9, 12, 5, 6, 3, 0, 14],
        [11, 8, 12, 7, 1, 14, 2, 13, 6, 15, 0, 9, 10, 4, 5, 3],
    ],
    [
        [12, 1, 10, 15, 9, 2, 6, 8, 0, 13, 3, 4, 14, 7, 5, 11],
        [10, 15, 4, 2, 7, 12, 9, 5, 6, 1, 13, 14, 0, 11, 3, 8],
        [9, 14, 15, 5, 2, 8, 12, 3, 7, 0, 4, 10, 1, 13, 11, 6],
        [4, 3, 2, 12, 9, 5, 15, 10, 11, 14, 1, 7, 6, 0, 8, 13],
    ],
    [
        [4, 11, 2, 14, 15, 0, 8, 13, 3, 12, 9, 7, 5, 10, 6, 1],
        [13, 0, 11, 7, 4, 9, 1, 10, 14, 3, 5, 12, 2, 15, 8, 6],
        [1, 4, 11, 13, 12, 3, 7, 14, 10, 15, 6, 8, 0, 5, 9, 2],
        [6, 11, 13, 8, 1, 4, 10, 7, 9, 5, 0, 15, 14, 2, 3, 12],
    ],
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
        col = (chunk[1] << 3) | (chunk[2] << 2) | (chunk[3] << 1) | (chunk[4])
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

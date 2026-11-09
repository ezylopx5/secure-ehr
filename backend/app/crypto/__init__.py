"""Cryptographic core of the Secure EHR system.

Every primitive here is a REAL implementation backed by standard libraries:

* AES-256-GCM (cryptography)  -> confidentiality at rest
* HKDF-SHA256 (cryptography)  -> key derivation / hierarchy
* SHA-256 + HMAC-SHA256       -> integrity + tamper-evident audit chain
* CKKS via TenSEAL (SEAL 4.x) -> computing on encrypted patient features
* CP-ABE over BN254 (py_ecc)  -> fine-grained, policy-based record sharing
"""

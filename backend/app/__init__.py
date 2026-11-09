"""Secure AI-Powered EHR System (PS02) - FastAPI backend package.

Course: Information Security & Cryptography, NIT Surat (4-month capstone).

Package layout:
    app.core       - configuration, logging, JWT/bcrypt security primitives
    app.crypto     - the cryptographic core: key hierarchy (HKDF), AES-256-GCM
                     envelope encryption, SHA-256/HMAC-SHA256 integrity,
                     append-only audit blockchain, CKKS (TenSEAL) homomorphic
                     encryption helpers, CP-ABE over BN254 pairings (py_ecc)
    app.db         - SQLAlchemy ORM models and session management
    app.middleware - 7-layer API middleware stack (rate limit, trusted host,
                     CORS, security headers, gzip, PII-scrubbed exceptions,
                     request logging)
    app.schemas    - Pydantic request/response models
    app.services   - business logic (records, consent, audit, prediction, FHIR)
    app.api        - FastAPI routers (auth, patients, records, consent,
                     predictions, audit, chat, FHIR, admin)
    app.ml         - XGBoost disease models + encrypted inference client
    app.cloud      - the "untrusted cloud" inference engine: imports ONLY
                     tenseal/numpy, never touches the database or secret keys
    app.ai         - Ollama LLM client + LangGraph clinical decision agent
"""

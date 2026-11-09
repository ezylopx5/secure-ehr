"""Root FastAPI entrypoint for Vercel zero-config FastAPI deployment."""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("VERCEL", "1")

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app, ensure_bootstrapped  # noqa: E402

ensure_bootstrapped()

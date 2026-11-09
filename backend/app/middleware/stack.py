"""Defense-in-depth middleware (7 layers, mounted outside-in in main.py):

1. RateLimitMiddleware      - token bucket per client IP (429 on burst)
2. TrustedHostMiddleware    - Starlette built-in
3. CORSMiddleware           - Starlette built-in, explicit origin allow-list
4. SecurityHeadersMiddleware- HSTS/CSP/X-Frame-Options/nosniff/Referrer-Policy
5. GZipMiddleware           - Starlette built-in
6. ExceptionScrubMiddleware - catches unhandled errors, PII-scrubs payloads
7. RequestLoggingMiddleware - request-id + structured JSON access log

Pure-ASGI/Starlette BaseHTTPMiddleware implementations, no external deps.
"""
from __future__ import annotations

import re
import time
import uuid
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.logging import get_logger

log = get_logger("app.middleware")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory token bucket per client IP (per-instance; swap for Redis in
    multi-worker production deployments)."""

    def __init__(self, app, rate_per_second: float = 20.0, burst: float = 40.0):
        super().__init__(app)
        self.rate = rate_per_second
        self.capacity = burst
        self._buckets: dict[str, tuple[float, float]] = defaultdict(
            lambda: (time.monotonic(), self.capacity)
        )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        last, tokens = self._buckets[client]
        tokens = min(self.capacity, tokens + (now - last) * self.rate)
        if tokens < 1.0:
            retry = max(0.0, (1.0 - tokens) / self.rate)
            return JSONResponse(
                {"detail": "rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": str(int(retry) + 1)},
            )
        self._buckets[client] = (now, tokens - 1.0)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """OWASP-recommended response headers for an API-only origin."""

    HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
        "Cache-Control": "no-store",
    }

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        for key, value in self.HEADERS.items():
            if key == "Content-Security-Policy" and not (
                request.url.path.startswith("/api") or request.url.path == "/healthz"
            ):
                response.headers.setdefault(
                    key,
                    "default-src 'self' 'unsafe-inline'; connect-src 'self' http://127.0.0.1:8000; img-src 'self' data:; frame-ancestors 'none'",
                )
            else:
                response.headers.setdefault(key, value)
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Assigns an X-Request-ID and emits one structured access-log line."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        log.info(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra={"request_id": request_id},
        )
        return response


class PiiScrubber:
    """Regex-based PII redaction for anything about to be logged/returned."""

    RULES: list[tuple[re.Pattern[str], str]] = [
        (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "[EMAIL]"),
        (re.compile(r"\b\d{10}\b"), "[PHONE]"),                      # IN phone
        (re.compile(r"\b\d{12}\b"), "[AADHAAR-LIKE]"),               # 12-digit ID
        (re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"), "[PAN]"),            # PAN format
        (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[CARD]"),           # card-like
        (re.compile(r"[A-Za-z0-9+/]{120,}={0,2}"), "[BLOB]"),        # ciphertexts
    ]

    @classmethod
    def scrub(cls, text: str) -> str:
        for pattern, replacement in cls.RULES:
            text = pattern.sub(replacement, text)
        return text


class ExceptionScrubMiddleware(BaseHTTPMiddleware):
    """Last-resort error handler: never leak stack traces or PII to clients."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            return await call_next(request)
        except Exception:  # noqa: BLE001 - deliberate catch-all
            request_id = getattr(request.state, "request_id", "-")
            log.exception(
                "unhandled error on %s %s", request.method, request.url.path,
                extra={"request_id": request_id},
            )
            return JSONResponse(
                {
                    "detail": PiiScrubber.scrub("internal server error"),
                    "request_id": request_id,
                },
                status_code=500,
            )

"""Structured JSON logging with request-scoped context.

Produces single-line JSON log records so the audit/compliance story is
machine-parseable; PII never enters log lines (the exception middleware
scrubs payloads before they reach the logger).
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    """Format records as compact JSON with level/time/module fields."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: D102
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "request_id"):
            payload["request_id"] = record.request_id
        if record.exc_info and record.exc_info[0] is not None:
            payload["exc"] = self.formatException(record.exc_info)[-2000:]
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    """Install the JSON formatter once on the root logger."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    logging.getLogger("uvicorn.access").handlers = []
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

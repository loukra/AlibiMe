"""Structured JSON logging.

Never write raw phone numbers to logs. Helpers here only accept already-safe
fields (ids, codes, masked values).
"""
from __future__ import annotations

import json
import logging
import sys
from typing import Any

# Fields we promote to top-level of the structured log line when present in `extra`.
_CONTEXT_KEYS = (
    "request_id",
    "user_id",
    "interaction_request_id",
    "call_attempt_id",
    "message_attempt_id",
    "provider",
    "provider_external_id",
    "template_code",
    "channel",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in _CONTEXT_KEYS:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)

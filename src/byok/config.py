"""Small env-based configuration for the relay."""

from __future__ import annotations

import os


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    normalized = value.strip().lower()
    if normalized in ("1", "true", "yes", "on"):
        return True
    if normalized in ("0", "false", "no", "off"):
        return False
    return default


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = _get_int("PORT", 8082)

# Upstream (OpenAI-compatible API)
UPSTREAM_BASE_URL = os.getenv("UPSTREAM_BASE_URL", "").rstrip("/")
UPSTREAM_API_KEY = os.getenv("UPSTREAM_API_KEY", "")

# Relay auth
RELAY_API_KEY = os.getenv("RELAY_API_KEY", "")

# Logging & Dashboard
LOG_BODY_LIMIT = _get_int("LOG_BODY_LIMIT", 20000)
LOG_STORE_LIMIT = _get_int("LOG_STORE_LIMIT", 200)
DASHBOARD_ENABLED = _get_bool("DASHBOARD_ENABLED", True)
DASHBOARD_TITLE = os.getenv("DASHBOARD_TITLE", "BYOK Relay Logs")

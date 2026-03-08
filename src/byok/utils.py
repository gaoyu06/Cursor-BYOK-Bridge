"""
Utility functions for the proxy.
"""
import os
import time


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime())


def truncate_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...<truncated>"


def decode_body(body: bytes) -> str:
    if not body:
        return ""
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        return body.decode("utf-8", errors="replace")


def mask_secret(value: str) -> str:
    if not value:
        return value
    if len(value) <= 10:
        return "******"
    return value[:6] + "***" + value[-4:]


def sanitize_headers_for_log(headers: dict) -> dict:
    """Sanitize headers for logging (mask secrets)."""
    sanitized = {}
    for key, value in headers.items():
        lower_key = key.lower()
        if lower_key == "authorization":
            v = str(value)
            sanitized[key] = "Bearer " + mask_secret(v[7:]) if v.startswith("Bearer ") else mask_secret(v)
        elif lower_key == "x-api-key":
            sanitized[key] = mask_secret(str(value))
        else:
            sanitized[key] = value
    return sanitized

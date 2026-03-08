#!/usr/bin/env python3
"""NewAPI Cursor BYOK Adapter entry point."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import uvicorn

# Ensure src is on path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

REQUIRED_ENV_VARS = ("UPSTREAM_BASE_URL", "UPSTREAM_API_KEY", "RELAY_API_KEY")


def load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return
    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def validate_env() -> None:
    missing = [n for n in REQUIRED_ENV_VARS if not os.getenv(n)]
    if missing:
        raise SystemExit(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Set them in the environment or the .env file."
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="NewAPI Cursor BYOK Adapter")
    parser.add_argument("--host", default=None, help="Public host")
    parser.add_argument("--port", default=None, help="Public port")
    parser.add_argument(
        "--env-file", default=str(PROJECT_ROOT / ".env"), help="Path to .env"
    )
    args = parser.parse_args()

    load_dotenv(Path(args.env_file))
    validate_env()

    from byok import config as byok_config
    from byok.proxy import app

    host = args.host or byok_config.HOST
    port = int(args.port or byok_config.PORT)
    print(f"Starting adapter on http://{host}:{port}")
    print(f"Forwarding upstream requests to {byok_config.UPSTREAM_BASE_URL}")
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

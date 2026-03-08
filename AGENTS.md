# PROJECT KNOWLEDGE BASE

**Generated:** 2026-03-08 15:08 UTC
**Commit:** N/A (not a git repository)
**Branch:** N/A (not a git repository)

## OVERVIEW
NewAPI Cursor BYOK Adapter is a small FastAPI relay that keeps `/v1/chat/completions` compatibility while translating Responses API payloads and streams. Runtime stack: FastAPI + Uvicorn + HTTPX.

## STRUCTURE
```text
./
|- run.py                    # process bootstrap; loads env and starts app
|- src/byok/                 # core proxy, config, payload conversion
|  |- dashboard/             # HTML dashboard and log API
|- deploy/                   # remote deployment script + systemd unit
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Startup and process lifecycle | `run.py` | Env validation and Uvicorn startup |
| Request proxying | `src/byok/proxy.py` | Route mode selection, upstream forwarding, SSE logic |
| Responses -> Chat conversion | `src/byok/responses_compat.py` | Mapping logic for payloads and chunks |
| Runtime configuration | `src/byok/config.py` | Env parsing and defaults |
| Header/body sanitization | `src/byok/utils.py` | Masking and truncation for logs |
| Dashboard routes | `src/byok/dashboard/routes.py` | `/` and `/api/logs` endpoints |
| Deployment flow | `deploy/deploy.ps1` | SCP/SSH, venv install, systemd restart |

## CODE MAP
LSP symbol map unavailable in this environment (`basedpyright` not installed). Use direct file scan:

| Symbol | Type | Location | Refs | Role |
|--------|------|----------|------|------|
| `main` | function | `run.py` | entrypoint only | Bootstraps adapter server |
| `create_app` | function | `src/byok/proxy.py` | module-level app init | Registers health + catch-all proxy route |
| `_handle_proxy` | function | `src/byok/proxy.py` | called by catch-all route | Core request forwarding and response adaptation |
| `_handle_stream` | function | `src/byok/proxy.py` | called for SSE media type | Translates Responses stream events to chat chunks |
| `responses_to_chat_completion` | function | `src/byok/responses_compat.py` | used in `_handle_proxy` | Non-stream Responses -> Chat payload mapping |
| `register_routes` | function | `src/byok/dashboard/routes.py` | called in `create_app` | Dashboard HTML + logs API wiring |

## CONVENTIONS
- Env-first configuration only; no external config file parsing.
- In logs, secrets are masked and payloads truncated by `LOG_BODY_LIMIT`.
- Responses-style POSTs on chat-completions path are rerouted to `/v1/responses` automatically.
- `x-byok-route-mode` response header indicates `chat-completions` vs `responses-compat`.

## ANTI-PATTERNS (THIS PROJECT)
- Do not log raw Authorization or API keys; use `sanitize_headers_for_log`.
- Do not bypass `sanitize_responses_payload`; metadata/stream_options stripping is hardcoded for compatibility.
- Do not add blocking work to request path without considering SSE stream latency.

## UNIQUE STYLES
- Uses one catch-all FastAPI route for proxying all methods and paths.
- Keeps in-memory rolling request log (`REQUEST_LOGS`) with explicit max size.
- Adapts both function and custom tool call streaming deltas into Chat Completions chunk schema.

## COMMANDS
```bash
pip install -r requirements.txt
python run.py
python -m compileall ./src ./run.py
```

## NOTES
- No CI workflow directory exists in this repository.
- No automated test suite is currently present.
- `.env` is required at runtime for `UPSTREAM_BASE_URL`, `UPSTREAM_API_KEY`, `RELAY_API_KEY`.

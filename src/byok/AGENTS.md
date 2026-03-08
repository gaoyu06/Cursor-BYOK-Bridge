# MODULE KNOWLEDGE BASE: src/byok

## OVERVIEW
Core relay package: request routing, Responses compatibility transforms, environment config, and logging helpers.

## STRUCTURE
```text
src/byok/
|- proxy.py             # main FastAPI app + forwarding + streaming adapter
|- responses_compat.py  # payload conversion primitives
|- config.py            # env loaders and defaults
|- utils.py             # log-safe helpers
|- dashboard/           # UI + logs endpoints (separate local domain)
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add/adjust route-mode logic | `src/byok/proxy.py` | `is_chat_completions_path`, `_handle_proxy` |
| Change Responses payload detection | `src/byok/responses_compat.py` | `looks_like_responses_payload` |
| Change field stripping | `src/byok/responses_compat.py` | `sanitize_responses_payload` |
| Tune upstream forwarding | `src/byok/proxy.py` | request headers + `UPSTREAM_BASE_URL` |
| Tune secret masking/truncation | `src/byok/utils.py` | `mask_secret`, `sanitize_headers_for_log`, `truncate_text` |
| Add env variables | `src/byok/config.py` | keep bool/int parser pattern |

## CONVENTIONS
- Keep compatibility logic in `responses_compat.py`; avoid embedding protocol mapping constants inside dashboard or config modules.
- Keep HTTP transport concerns in `proxy.py`; helper functions in `utils.py` should remain transport-agnostic.
- Env parsing uses `_get_bool` and `_get_int` with forgiving defaults (invalid values fall back).
- Headers forwarded upstream must pass through hop-by-hop header filtering.

## ANTI-PATTERNS
- Do not duplicate secret masking logic in route handlers.
- Do not mutate `request.headers`; build new filtered header dict.
- Do not return raw Responses payload on compat path once conversion to chat-completion is expected.
- Do not let in-memory `REQUEST_LOGS` grow unbounded; always respect `LOG_STORE_LIMIT`.

## LOCAL GOTCHAS
- `route_mode` changes both target path and downstream response conversion.
- Streaming branch (`text/event-stream`) has separate conversion path; non-stream fixes may not affect stream behaviour.

"""Proxy logic: forward requests upstream and adapt Responses payloads."""

import json
import time
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from . import config
from .responses_compat import (
    make_chat_completion_chunk,
    looks_like_responses_payload,
    response_payload_to_tool_calls,
    responses_to_chat_completion,
    sanitize_responses_payload,
)
from .utils import (
    decode_body,
    now_iso,
    sanitize_headers_for_log,
    truncate_text,
)

HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "host",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

REQUEST_LOGS = []


def filter_headers(headers) -> dict:
    return {k: v for k, v in headers.items() if k.lower() not in HOP_BY_HOP_HEADERS}


def extract_api_key(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.headers.get("x-api-key", "")


def is_authorized(request: Request) -> bool:
    expected = config.RELAY_API_KEY
    if not expected:
        return True
    return extract_api_key(request) == expected


def unauthorized_response() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"error": {"message": "Unauthorized", "type": "auth_error"}},
    )


def store_log(entry: dict) -> None:
    if not config.DASHBOARD_ENABLED:
        return
    REQUEST_LOGS.insert(0, entry)
    del REQUEST_LOGS[config.LOG_STORE_LIMIT :]


def finalize_log(entry: dict) -> None:
    entry["duration_ms"] = int((time.time() - entry["started_at_ts"]) * 1000)


def append_stream_preview(entry: dict, event_type: str, preview: str) -> None:
    if not config.DASHBOARD_ENABLED:
        return
    if "stream_previews" not in entry:
        entry["stream_previews"] = []
    entry["stream_previews"].append(
        {
            "type": event_type,
            "preview": truncate_text(preview, config.LOG_BODY_LIMIT),
        }
    )


def is_chat_completions_path(path: str) -> bool:
    n = path.rstrip("/")
    return n in ("/v1/chat/completions", "/chat/completions")


def make_sse_data(payload) -> bytes:
    return ("data: {}\n\n".format(json.dumps(payload, ensure_ascii=True))).encode(
        "utf-8"
    )


def make_sse_done() -> bytes:
    return b"data: [DONE]\n\n"


@asynccontextmanager
async def lifespan(app: FastAPI):
    timeout = httpx.Timeout(connect=30.0, read=None, write=30.0, pool=30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        app.state.http_client = client
        yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="NewAPI Cursor BYOK Adapter",
        description="OpenAI-compatible proxy with Responses API support",
        lifespan=lifespan,
    )

    from .dashboard import register_routes

    register_routes(app)

    @app.get("/health/liveliness")
    async def health_liveliness():
        return {"status": "ok"}

    @app.api_route(
        "/{full_path:path}",
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
    )
    async def proxy_request(full_path: str, request: Request):
        return await _handle_proxy(app, full_path, request)

    return app


async def _handle_proxy(app: FastAPI, full_path: str, request: Request):
    client = app.state.http_client
    incoming_path = "/" + full_path
    target_path = incoming_path
    body = await request.body()
    original_body = body
    route_mode = "chat-completions"

    if request.method.upper() == "POST" and is_chat_completions_path(incoming_path):
        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None

        if looks_like_responses_payload(payload):
            target_path = (
                "/v1/responses" if incoming_path.startswith("/v1/") else "/responses"
            )
            route_mode = "responses-compat"
            payload = sanitize_responses_payload(payload)
            body = json.dumps(payload).encode("utf-8")

    base_url = config.UPSTREAM_BASE_URL.rstrip("/")
    headers = dict(filter_headers(request.headers))
    if config.UPSTREAM_API_KEY:
        headers["Authorization"] = "Bearer {}".format(config.UPSTREAM_API_KEY)

    upstream_url = "{base}{path}".format(base=base_url, path=target_path)

    log_entry = {
        "id": str(uuid.uuid4()),
        "method": request.method,
        "path": incoming_path,
        "target_path": target_path,
        "route_mode": route_mode,
        "upstream_mode": "direct",
        "request_headers": sanitize_headers_for_log(dict(request.headers)),
        "request_body": truncate_text(
            decode_body(original_body), config.LOG_BODY_LIMIT
        ),
        "forwarded_request_body": truncate_text(
            decode_body(body), config.LOG_BODY_LIMIT
        ),
        "started_at": now_iso(),
        "started_at_ts": time.time(),
    }

    try:
        upstream_request = client.build_request(
            method=request.method,
            url=upstream_url,
            headers=headers,
            params=request.query_params,
            content=body,
        )
        upstream_response = await client.send(upstream_request, stream=True)
    except httpx.HTTPError as exc:
        log_entry["status_code"] = 502
        log_entry["response_status"] = 502
        log_entry["error"] = str(exc)
        finalize_log(log_entry)
        store_log(log_entry)
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": "Failed to reach upstream API: {}".format(str(exc)),
                    "type": "bad_gateway",
                }
            },
        )

    response_headers = filter_headers(upstream_response.headers)
    response_headers["x-byok-route-mode"] = route_mode
    media_type = upstream_response.headers.get("content-type")

    if "text/event-stream" in (media_type or ""):
        return await _handle_stream(
            upstream_response,
            response_headers,
            media_type,
            route_mode,
            log_entry,
        )

    content = await upstream_response.aread()
    await upstream_response.aclose()

    if (
        route_mode == "responses-compat"
        and upstream_response.status_code < 400
        and "application/json" in (media_type or "")
    ):
        try:
            response_payload = json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            response_payload = None

        if (
            isinstance(response_payload, dict)
            and response_payload.get("object") == "response"
        ):
            content = json.dumps(responses_to_chat_completion(response_payload)).encode(
                "utf-8"
            )

    log_entry["status_code"] = upstream_response.status_code
    log_entry["response_status"] = upstream_response.status_code
    log_entry["response_headers"] = sanitize_headers_for_log(
        dict(upstream_response.headers)
    )
    log_entry["response_body"] = truncate_text(
        decode_body(content), config.LOG_BODY_LIMIT
    )
    finalize_log(log_entry)
    store_log(log_entry)

    return Response(
        content=content,
        status_code=upstream_response.status_code,
        headers=response_headers,
        media_type=media_type,
    )


async def _handle_stream(
    upstream_response, response_headers, media_type, route_mode, log_entry
):
    """Handle SSE streaming response."""

    async def event_stream():
        sent_role_chunk = False
        sent_done = False
        stream_event_count = 0
        tool_calls_by_index = {}  # output_index -> {id, name, arguments, tool_index}
        next_tool_index = 0
        model_for_chunks = None
        chunk_id_for_chunks = "chatcmpl-responses-compat"

        def _emit_tool_call_added(idx, tc):
            nonlocal sent_role_chunk
            tool_idx = tc["tool_index"]
            delta_payload = {
                "tool_calls": [
                    {
                        "index": tool_idx,
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]},
                    }
                ]
            }
            if not sent_role_chunk:
                delta_payload["role"] = "assistant"
                sent_role_chunk = True
            return delta_payload

        try:
            if route_mode != "responses-compat":
                async for chunk in upstream_response.aiter_bytes():
                    stream_event_count += 1
                    yield chunk
                return

            async for line in upstream_response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue

                payload_text = line[6:]
                if payload_text == "[DONE]":
                    if not sent_done:
                        sent_done = True
                        yield make_sse_done()
                    continue

                try:
                    event_payload = json.loads(payload_text)
                except json.JSONDecodeError:
                    continue

                event_type = event_payload.get("type")
                stream_event_count += 1

                if event_type == "response.output_item.added":
                    item = event_payload.get("item") or {}
                    item_type = item.get("type")
                    if item_type == "function_call":
                        idx = event_payload.get("output_index", 0)
                        tool_calls_by_index[idx] = {
                            "id": item.get("id")
                            or item.get("call_id")
                            or ("call-%s" % idx),
                            "name": item.get("name", ""),
                            "arguments": "",
                            "tool_index": next_tool_index,
                        }
                        next_tool_index += 1
                        model_for_chunks = model_for_chunks or event_payload.get(
                            "model"
                        )
                        chunk_id_for_chunks = (
                            event_payload.get("item_id")
                            or event_payload.get("response_id")
                            or chunk_id_for_chunks
                        )
                        delta_payload = _emit_tool_call_added(
                            idx, tool_calls_by_index[idx]
                        )
                        append_stream_preview(
                            log_entry, event_type, json.dumps(item, ensure_ascii=True)
                        )
                        yield make_sse_data(
                            make_chat_completion_chunk(
                                chunk_id=chunk_id_for_chunks,
                                model=model_for_chunks,
                                delta=delta_payload,
                            )
                        )
                    elif item_type == "custom_tool_call":
                        idx = event_payload.get("output_index", 0)
                        tool_calls_by_index[idx] = {
                            "id": item.get("call_id")
                            or item.get("id")
                            or ("call-%s" % idx),
                            "name": item.get("name")
                            or item.get("namespace")
                            or "custom_tool",
                            "arguments": item.get("input", ""),
                            "tool_index": next_tool_index,
                        }
                        next_tool_index += 1
                        model_for_chunks = model_for_chunks or event_payload.get(
                            "model"
                        )
                        chunk_id_for_chunks = (
                            event_payload.get("item_id")
                            or event_payload.get("response_id")
                            or chunk_id_for_chunks
                        )
                        delta_payload = _emit_tool_call_added(
                            idx, tool_calls_by_index[idx]
                        )
                        append_stream_preview(
                            log_entry, event_type, json.dumps(item, ensure_ascii=True)
                        )
                        yield make_sse_data(
                            make_chat_completion_chunk(
                                chunk_id=chunk_id_for_chunks,
                                model=model_for_chunks,
                                delta=delta_payload,
                            )
                        )
                    continue

                if event_type == "response.function_call_arguments.delta":
                    idx = event_payload.get("output_index", 0)
                    delta = event_payload.get("delta", "")
                    if idx in tool_calls_by_index:
                        tool_calls_by_index[idx]["arguments"] += delta
                        tc = tool_calls_by_index[idx]
                        delta_payload = {
                            "tool_calls": [
                                {
                                    "index": tc["tool_index"],
                                    "function": {"arguments": delta},
                                }
                            ]
                        }
                        if not sent_role_chunk:
                            delta_payload["role"] = "assistant"
                            sent_role_chunk = True
                        append_stream_preview(log_entry, event_type, delta)
                        yield make_sse_data(
                            make_chat_completion_chunk(
                                chunk_id=chunk_id_for_chunks,
                                model=model_for_chunks,
                                delta=delta_payload,
                            )
                        )
                    continue

                if event_type == "response.function_call_arguments.done":
                    idx = event_payload.get("output_index", 0)
                    if idx in tool_calls_by_index:
                        tool_calls_by_index[idx]["arguments"] = event_payload.get(
                            "arguments", tool_calls_by_index[idx]["arguments"]
                        )
                        tool_calls_by_index[idx]["name"] = event_payload.get(
                            "name", tool_calls_by_index[idx]["name"]
                        )
                    append_stream_preview(
                        log_entry,
                        event_type,
                        json.dumps(event_payload, ensure_ascii=True),
                    )
                    continue

                if event_type == "response.custom_tool_call_input.delta":
                    idx = event_payload.get("output_index", 0)
                    delta = event_payload.get("delta", "")
                    if idx in tool_calls_by_index:
                        tool_calls_by_index[idx]["arguments"] += delta
                        tc = tool_calls_by_index[idx]
                        delta_payload = {
                            "tool_calls": [
                                {
                                    "index": tc["tool_index"],
                                    "function": {"arguments": delta},
                                }
                            ]
                        }
                        if not sent_role_chunk:
                            delta_payload["role"] = "assistant"
                            sent_role_chunk = True
                        append_stream_preview(log_entry, event_type, delta)
                        yield make_sse_data(
                            make_chat_completion_chunk(
                                chunk_id=chunk_id_for_chunks,
                                model=model_for_chunks,
                                delta=delta_payload,
                            )
                        )
                    continue

                if event_type == "response.custom_tool_call_input.done":
                    idx = event_payload.get("output_index", 0)
                    if idx in tool_calls_by_index:
                        tool_calls_by_index[idx]["arguments"] = event_payload.get(
                            "input", tool_calls_by_index[idx]["arguments"]
                        )
                    append_stream_preview(
                        log_entry,
                        event_type,
                        json.dumps(event_payload, ensure_ascii=True),
                    )
                    continue

                if event_type == "response.output_text.delta":
                    delta_payload = {"content": event_payload.get("delta", "")}
                    if not sent_role_chunk:
                        delta_payload["role"] = "assistant"
                        sent_role_chunk = True
                    append_stream_preview(
                        log_entry, event_type, event_payload.get("delta", "")
                    )
                    yield make_sse_data(
                        make_chat_completion_chunk(
                            chunk_id=event_payload.get("item_id")
                            or event_payload.get("response_id")
                            or "chatcmpl-responses-compat",
                            model=event_payload.get("model"),
                            delta=delta_payload,
                        )
                    )
                    continue

                if event_type == "response.completed":
                    response_payload = event_payload.get("response") or {}
                    append_stream_preview(
                        log_entry,
                        event_type,
                        json.dumps(response_payload, ensure_ascii=True),
                    )
                    tool_calls = response_payload_to_tool_calls(response_payload)
                    finish_reason = "tool_calls" if tool_calls else "stop"
                    final_delta = {}

                    if tool_calls:
                        if not tool_calls_by_index:
                            if not sent_role_chunk:
                                final_delta["role"] = "assistant"
                                sent_role_chunk = True
                            final_delta["tool_calls"] = tool_calls
                        elif not sent_role_chunk:
                            final_delta["role"] = "assistant"
                            sent_role_chunk = True

                    yield make_sse_data(
                        make_chat_completion_chunk(
                            chunk_id=response_payload.get("id") or chunk_id_for_chunks,
                            model=response_payload.get("model") or model_for_chunks,
                            created=response_payload.get("created_at"),
                            delta=final_delta,
                            finish_reason=finish_reason,
                        )
                    )
                    if not sent_done:
                        sent_done = True
                        yield make_sse_done()
        finally:
            await upstream_response.aclose()
            log_entry["status_code"] = upstream_response.status_code
            log_entry["response_status"] = upstream_response.status_code
            log_entry["response_headers"] = sanitize_headers_for_log(
                dict(upstream_response.headers)
            )
            log_entry["stream_event_count"] = stream_event_count
            previews = log_entry.get("stream_previews") or []
            log_entry["stream_preview"] = "\n\n".join(
                "[{}] {}".format(p.get("type", ""), p.get("preview", ""))
                for p in previews
            )
            finalize_log(log_entry)
            store_log(log_entry)

    return StreamingResponse(
        event_stream(),
        status_code=upstream_response.status_code,
        headers=response_headers,
        media_type=media_type,
    )


app = create_app()

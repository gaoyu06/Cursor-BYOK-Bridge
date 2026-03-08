"""
OpenAI Responses API to Chat Completions format conversion.
"""

import json
import time


def _item_to_tool_call(item: dict) -> dict | None:
    """Convert a function_call or custom_tool_call output item to Chat Completions tool call format."""
    item_type = item.get("type")
    if item_type == "function_call":
        return {
            "id": item.get("call_id") or item.get("id"),
            "type": "function",
            "function": {
                "name": item.get("name", ""),
                "arguments": item.get("arguments", ""),
            },
        }
    if item_type == "custom_tool_call":
        # custom_tool_call uses "input" instead of "arguments", "name" for tool name
        return {
            "id": item.get("call_id") or item.get("id"),
            "type": "function",
            "function": {
                "name": item.get("name") or item.get("namespace") or "custom_tool",
                "arguments": item.get("input", ""),
            },
        }
    return None


def responses_output_to_chat_message(response_payload: dict) -> dict:
    """Convert Responses API output to chat completion message format."""
    text_parts = []
    tool_calls = []
    reasoning_parts = []

    for item in response_payload.get("output", []) or []:
        item_type = item.get("type")

        tc = _item_to_tool_call(item)
        if tc:
            tool_calls.append(tc)
            continue

        if item_type != "message":
            continue

        for content_item in item.get("content", []) or []:
            ct = content_item.get("type")
            if ct == "output_text":
                text_parts.append(content_item.get("text", ""))
            elif ct == "reasoning":
                reasoning_parts.append(content_item.get("text", ""))

    message = {
        "role": "assistant",
        "content": "".join(text_parts),
    }
    if reasoning_parts:
        message["reasoning_content"] = "".join(reasoning_parts)
    if tool_calls:
        message["tool_calls"] = tool_calls

    return message


def responses_to_chat_completion(response_payload: dict) -> dict:
    """Convert full Responses API response to Chat Completions format."""
    usage = response_payload.get("usage") or {}
    input_details = usage.get("input_tokens_details") or {}
    output_details = usage.get("output_tokens_details") or {}
    message = responses_output_to_chat_message(response_payload)
    finish_reason = "tool_calls" if message.get("tool_calls") else "stop"

    return {
        "id": response_payload.get("id"),
        "object": "chat.completion",
        "created": response_payload.get("created_at"),
        "model": response_payload.get("model"),
        "choices": [
            {
                "index": 0,
                "finish_reason": finish_reason,
                "message": message,
            }
        ],
        "usage": {
            "prompt_tokens": usage.get("input_tokens"),
            "completion_tokens": usage.get("output_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "prompt_tokens_details": {
                "cached_tokens": input_details.get("cached_tokens", 0),
            },
            "completion_tokens_details": {
                "reasoning_tokens": output_details.get("reasoning_tokens", 0),
            },
        },
    }


def make_chat_completion_chunk(
    chunk_id, model, delta, finish_reason=None, created=None
):
    """Build a chat completion chunk for SSE streaming."""
    return {
        "id": chunk_id,
        "object": "chat.completion.chunk",
        "created": created or int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
    }


def response_payload_to_tool_calls(response_payload: dict) -> list:
    """Extract tool calls from Responses API payload for chunk format."""
    tool_calls = []
    for item in response_payload.get("output", []) or []:
        tc = _item_to_tool_call(item)
        if tc:
            tc["index"] = len(tool_calls)
            tool_calls.append(tc)
    return tool_calls


def looks_like_responses_payload(payload) -> bool:
    """Check if request body looks like OpenAI Responses API format."""
    if not isinstance(payload, dict):
        return False
    if "messages" in payload:
        return False
    if "input" in payload:
        return True
    response_markers = (
        "previous_response_id",
        "instructions",
        "parallel_tool_calls",
        "reasoning",
        "text",
        "truncation",
    )
    return any(marker in payload for marker in response_markers)


def sanitize_responses_payload(payload: dict) -> dict:
    """Remove fields that commonly break upstream compatibility."""
    sanitized = dict(payload)
    sanitized.pop("metadata", None)
    sanitized.pop("stream_options", None)
    return sanitized

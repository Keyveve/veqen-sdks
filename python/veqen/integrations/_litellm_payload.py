"""Allowlisted cost metadata from LiteLLM's StandardLoggingPayload.

Never copy messages, response bodies, headers, exception text, or arbitrary metadata.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone


def _object(value) -> dict:
    return value if isinstance(value, dict) else {}


def _tokens(value) -> int:
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("invalid token count")
    if not math.isfinite(value) or value < 0 or value > 2**40 or int(value) != value:
        raise ValueError("invalid token count")
    return int(value)


def standard_call(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("expected a StandardLoggingPayload object")
    identifier = payload.get("litellm_call_id") or payload.get("id")
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("missing request id")
    end = float(payload["endTime"])
    start = float(payload.get("startTime", end))
    metadata = _object(payload.get("metadata"))
    hidden = _object(payload.get("hidden_params"))
    usage = _object(hidden.get("usage_object")) or _object(metadata.get("usage_object"))
    details = _object(usage.get("prompt_tokens_details")) or _object(usage.get("input_tokens_details"))
    cache_read = _tokens(details.get("cached_tokens") or usage.get("cache_read_input_tokens"))
    cache_write = _tokens(usage.get("cache_creation_input_tokens"))
    one_hour = _tokens(_object(usage.get("cache_creation")).get("ephemeral_1h_input_tokens"))
    # LiteLLM's normalized prompt_tokens includes caches; native Anthropic input_tokens does not.
    if "prompt_tokens" in usage:
        total_input = _tokens(usage["prompt_tokens"])
    elif "cache_read_input_tokens" in usage or "cache_creation_input_tokens" in usage:
        total_input = _tokens(usage.get("input_tokens")) + cache_read + cache_write
    else:
        total_input = _tokens(usage.get("input_tokens", payload.get("prompt_tokens")))
    output = _tokens(usage.get("completion_tokens", usage.get("output_tokens", payload.get("completion_tokens"))))
    if cache_read + cache_write > total_input or one_hour > cache_write:
        raise ValueError("inconsistent cache usage")
    if not isinstance(payload.get("model"), str) or not payload["model"]:
        raise ValueError("missing model")
    tags = _object(_object(metadata.get("requester_metadata")).get("veqen")) or _object(metadata.get("veqen"))
    params = _object(payload.get("model_parameters"))
    event = {
        "id": "litellm:" + hashlib.sha256(identifier.encode()).hexdigest()[:56],
        "ts": datetime.fromtimestamp(end, timezone.utc).isoformat(),
        "provider": payload.get("custom_llm_provider") or "unknown",
        "model": payload.get("model"),
        "input_tokens": total_input - cache_read - cache_write,
        "output_tokens": output,
        "cache_read_tokens": cache_read,
        "cache_write_tokens": cache_write - one_hour,
        "cache_write_1h_tokens": one_hour,
        "cost_usd": payload.get("response_cost"),
        "latency_ms": round((end - start) * 1000),
        "status": "error" if payload.get("status") == "failure" else "ok",
        "service_tier": params.get("service_tier"),
        **{name: str(tags[name]) for name in ("customer", "feature", "user", "project", "environment")
           if tags.get(name) is not None and isinstance(tags[name], (str, int, float, bool))},
    }
    # A proxy cache hit made no provider request. Keep the zero charge without repricing its replayed tokens.
    if payload.get("cache_hit") is True:
        for name in (
            "input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "cache_write_1h_tokens",
        ):
            event[name] = 0
        event["cost_usd"] = 0
    return event

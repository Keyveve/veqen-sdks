"""LiteLLM success callback (works for the SDK and the proxy's custom callbacks). Covers every provider and
model type LiteLLM supports: chat, embeddings, images (counted per image) and transcription (per second).

    import litellm
    from veqen.integrations.litellm import callback
    litellm.success_callback = [callback]

Per-request tags come from ``metadata={"veqen": {"customer": "acme"}}`` or ``veqen.tags(...)``.
"""

from __future__ import annotations

from typing import Any

from veqen.client import client, current_tags
from veqen.pricing import Usage
from veqen.wrap import _usage_openai


def callback(kwargs: dict, response: Any, start_time: Any = None, end_time: Any = None) -> None:
    params = kwargs.get("litellm_params") or {}
    options = kwargs.get("optional_params") or {}
    extracted = _usage_openai(response)
    if extracted is None:  # images and transcriptions carry no token usage
        data = getattr(response, "data", None)
        units = len(data) if isinstance(data, list) else float(getattr(response, "duration", None) or 0)
        extracted = (None, Usage(units=units), None)
    model, usage, tier = extracted
    variant = "/".join(str(x) for x in (options.get("quality"), options.get("size")) if x and x != "auto") or None
    request_tags = ((params.get("metadata") or {}).get("veqen")) or {}
    latency = int((end_time - start_time).total_seconds() * 1000) if start_time and end_time else None
    client.record(
        params.get("custom_llm_provider"),
        str(kwargs.get("model") or model),
        usage,
        tags={**current_tags(), **{k: str(v) for k, v in request_tags.items()}},
        service_tier=tier,
        variant=variant,
        latency_ms=latency,
        cost_usd=kwargs.get("response_cost"),  # kept only for models Veqen's price book doesn't know
    )

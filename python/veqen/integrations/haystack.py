"""Post-generation cost recording for Haystack's OpenAI-compatible chat replies."""

from __future__ import annotations

from haystack import component, default_from_dict, default_to_dict
from haystack.dataclasses import ChatMessage

from veqen import record


@component
class VeqenOpenAICostTracker:
    """Pass replies through and record one request with OpenAI-shaped usage.

    Connect after a chat generator configured for one reply (n=1). This component
    runs after inference, so it does not prevent calls or enforce budgets.
    """

    def __init__(self, provider: str = "openai", tags: dict[str, str] | None = None) -> None:
        self.provider = provider
        self.tags = dict(tags or {})
        if set(self.tags) - {"customer", "feature", "user", "project", "environment"}:
            raise ValueError("Use customer, feature, user, project or environment tags")

    def to_dict(self) -> dict:
        return default_to_dict(self, provider=self.provider, tags=self.tags)

    @classmethod
    def from_dict(cls, data: dict) -> VeqenOpenAICostTracker:
        return default_from_dict(cls, data)

    @component.output_types(replies=list[ChatMessage], recorded=bool, recording_status=str)
    def run(self, replies: list[ChatMessage], customer: str | None = None,
            feature: str | None = None) -> dict:
        result = {"replies": replies, "recorded": False, "recording_status": "missing_usage"}
        # Multiple alternatives can repeat the request's aggregate usage. Never sum them.
        if len(replies) != 1:
            return {**result, "recording_status": "requires_one_reply"}
        meta = replies[0].meta
        usage = meta.get("usage")
        model = meta.get("model")
        if not isinstance(usage, dict) or not isinstance(model, str) or not model:
            return result
        details = usage.get("prompt_tokens_details") or {}
        output_details = usage.get("completion_tokens_details") or {}
        if not isinstance(details, dict) or not isinstance(output_details, dict):
            return {**result, "recording_status": "invalid_usage"}
        if details.get("audio_tokens") or output_details.get("audio_tokens") or details.get("cache_write_tokens"):
            return {**result, "recording_status": "unsupported_usage"}
        input_tokens, output_tokens = usage.get("prompt_tokens"), usage.get("completion_tokens")
        cached = details.get("cached_tokens", 0)
        if any(type(value) is not int or value < 0 for value in (input_tokens, output_tokens, cached)):
            return {**result, "recording_status": "invalid_usage"}
        if cached > input_tokens:
            return {**result, "recording_status": "invalid_usage"}
        tags = {**self.tags, **({"customer": customer} if customer is not None else {}),
                **({"feature": feature} if feature is not None else {})}
        record(model, provider=self.provider, input_tokens=input_tokens - cached,
               output_tokens=output_tokens, cache_read_tokens=cached, **tags)
        return {**result, "recorded": True, "recording_status": "recorded"}

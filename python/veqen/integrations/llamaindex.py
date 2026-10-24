"""LlamaIndex event handler: prices every LLM call LlamaIndex makes, whichever LLM class makes it.

    from llama_index.core.instrumentation import get_dispatcher
    from veqen.integrations.llamaindex import VeqenEventHandler
    get_dispatcher().add_event_handler(VeqenEventHandler(tags={"feature": "rag"}))
"""

from __future__ import annotations

from collections import deque
from types import SimpleNamespace
from typing import Any

from llama_index.core.instrumentation.event_handlers import BaseEventHandler
from llama_index.core.instrumentation.events.llm import LLMChatEndEvent, LLMCompletionEndEvent

from veqen.client import client, current_tags
from veqen.wrap import _usage_anthropic, _usage_google, _usage_openai

_EXTRACT = {"openai": _usage_openai, "anthropic": _usage_anthropic, "google": _usage_google}


def _namespace(value: Any) -> Any:
    return SimpleNamespace(**{k: _namespace(v) for k, v in value.items()}) if isinstance(value, dict) else value


def _sdk(usage: Any) -> str:
    """Which provider SDK's usage this is: by its type's module, or for a plain dict, by its fields."""
    if not isinstance(usage, SimpleNamespace):
        return type(usage).__module__.split(".")[0]
    fields = vars(usage)
    if "prompt_token_count" in fields:
        return "google"
    if "prompt_tokens" in fields or "input_tokens_details" in fields:  # Chat Completions, or the Responses API
        return "openai"
    return "anthropic" if "input_tokens" in fields else ""


def extract(raw: Any, provider: str | None = None) -> tuple[str, Any] | None:
    """The provider and (model, usage, service tier) from an LLM response's raw provider object. Some LLM classes
    keep it, or its usage, as a dict of the response's fields."""
    obj = _namespace(raw)
    usage = _namespace(getattr(obj, "usage", None) or getattr(obj, "usage_metadata", None))
    if usage is None:
        return None
    view = SimpleNamespace(model=getattr(obj, "model", None), model_version=getattr(obj, "model_version", None),
                           service_tier=getattr(obj, "service_tier", None), usage=usage, usage_metadata=usage)
    sdk = _sdk(usage)
    extracted = _EXTRACT.get(sdk, lambda _: None)(view)
    # An OpenAI-compatible host reports through the OpenAI SDK; the ledger prices its model at that host when named.
    return (provider or sdk, extracted) if extracted and extracted[0] else None


class VeqenEventHandler(BaseEventHandler):
    """Records each chat or completion response once it ends, with its usage and the tags in effect. Responses
    that carry no usage (a stream without usage reporting, for one) are skipped rather than estimated, and one
    reported twice (a completion some LLM classes make through their own chat) is recorded once."""

    tags: dict[str, str] = {}
    provider: str | None = None

    @classmethod
    def class_name(cls) -> str:
        return "VeqenEventHandler"

    def handle(self, event: Any, **kwargs: Any) -> None:
        if not isinstance(event, (LLMChatEndEvent, LLMCompletionEndEvent)) or event.response is None:
            return
        raw = event.response.raw
        response_id = raw.get("id") if isinstance(raw, dict) else getattr(raw, "id", None)
        if response_id is not None and response_id in _seen:
            return
        if found := extract(raw, self.provider):
            if response_id is not None:
                _seen.append(response_id)
            provider, (model, usage, tier) = found
            client.record(provider, str(model), usage, tags={**self.tags, **current_tags()}, service_tier=tier)


_seen: deque = deque(maxlen=256)  # the latest responses recorded, by the provider's response id

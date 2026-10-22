"""LangChain / LangGraph callback handler.

    from veqen.integrations.langchain import VeqenCallbackHandler
    llm = ChatOpenAI(model="gpt-4o-mini", callbacks=[VeqenCallbackHandler(feature="research-agent")])
"""

from __future__ import annotations

from itertools import chain
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler

from veqen.client import client, current_tags
from veqen.pricing import Usage


class VeqenCallbackHandler(BaseCallbackHandler):
    raise_error = True  # let BudgetExceeded stop the call instead of being logged and ignored

    def __init__(self, **tags: str) -> None:
        self.tags = tags
        self._runs: dict[Any, dict] = {}

    def on_chat_model_start(self, serialized, messages, *, run_id, metadata=None, **kwargs) -> None:
        self._runs[run_id] = metadata or {}
        client.check({**self.tags, **current_tags()})

    def on_llm_start(self, serialized, prompts, *, run_id, metadata=None, **kwargs) -> None:
        self.on_chat_model_start(serialized, prompts, run_id=run_id, metadata=metadata)

    def on_llm_error(self, error, *, run_id, **kwargs) -> None:
        self._runs.pop(run_id, None)

    def on_llm_end(self, response, *, run_id, **kwargs) -> None:
        meta = self._runs.pop(run_id, {})
        for generation in chain.from_iterable(response.generations):
            message = getattr(generation, "message", None)
            usage = getattr(message, "usage_metadata", None)
            if not usage:
                continue
            details = usage.get("input_token_details") or {}
            read, write = int(details.get("cache_read") or 0), int(details.get("cache_creation") or 0)
            response_meta = getattr(message, "response_metadata", None) or {}
            model = response_meta.get("model_name") or response_meta.get("model") or meta.get("ls_model_name")
            if model:
                client.record(
                    meta.get("ls_provider"),
                    str(model),
                    Usage(int(usage["input_tokens"]) - read - write, int(usage["output_tokens"]), read, write),
                    tags={**self.tags, **current_tags()},
                )

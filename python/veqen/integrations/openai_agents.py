"""OpenAI Agents SDK trace processor.

    from agents import add_trace_processor
    from veqen.integrations.openai_agents import VeqenTracingProcessor
    add_trace_processor(VeqenTracingProcessor(feature="support-agent"))
"""

from __future__ import annotations

from typing import Any

from veqen.client import client, current_tags
from veqen.pricing import Usage
from veqen.wrap import _usage_openai


class VeqenTracingProcessor:
    def __init__(self, **tags: str) -> None:
        self.tags = tags

    def on_span_end(self, span: Any) -> None:
        data = span.span_data
        kind = getattr(data, "type", "")
        if kind == "response" and getattr(data, "response", None) is not None:
            extracted = _usage_openai(data.response)
        elif kind == "generation" and getattr(data, "usage", None):
            usage = data.usage
            extracted = (data.model, Usage(int(usage.get("input_tokens", 0)), int(usage.get("output_tokens", 0))), None)
        else:
            return
        if extracted and extracted[0]:
            client.record("openai", str(extracted[0]), extracted[1], tags={**self.tags, **current_tags()},
                          service_tier=extracted[2])

    def on_trace_start(self, trace: Any) -> None: ...

    def on_trace_end(self, trace: Any) -> None: ...

    def on_span_start(self, span: Any) -> None: ...

    def shutdown(self) -> None:
        client.flush()

    def force_flush(self) -> None:
        client.flush()

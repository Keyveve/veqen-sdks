import json
import os

import pytest

os.environ["HAYSTACK_TELEMETRY_ENABLED"] = "false"
pytest.importorskip("haystack")

from haystack import Pipeline, component
from haystack.dataclasses import ChatMessage

from veqen.integrations.haystack import VeqenOpenAICostTracker


def reply(**usage):
    return ChatMessage.from_assistant("PRIVATE_RESPONSE", meta={"model": "gpt-4o", "usage": {
        "prompt_tokens": 100, "completion_tokens": 20, "prompt_tokens_details": {"cached_tokens": 50}, **usage}})


def test_real_pipeline_cache_attribution_and_content_exclusion(ledger):
    @component
    class FakeGenerator:
        @component.output_types(replies=list[ChatMessage])
        def run(self):
            return {"replies": [reply()]}

    pipeline = Pipeline()
    pipeline.add_component("generator", FakeGenerator())
    pipeline.add_component("cost", VeqenOpenAICostTracker(tags={"feature": "assistant"}))
    pipeline.connect("generator.replies", "cost.replies")
    result = pipeline.run({"cost": {"customer": "synthetic-123"}})["cost"]
    assert result["recorded"] and result["replies"][0].text == "PRIVATE_RESPONSE"
    event, = ledger()
    assert (event["input_tokens"], event["output_tokens"], event["cache_read_tokens"]) == (50, 20, 50)
    assert event["customer"] == "synthetic-123" and event["feature"] == "assistant"
    assert "PRIVATE_RESPONSE" not in json.dumps(event)


@pytest.mark.parametrize("replies,status", [
    ([], "requires_one_reply"),
    ([reply(), reply()], "requires_one_reply"),
    ([ChatMessage.from_assistant("text")], "missing_usage"),
    ([reply(prompt_tokens=True)], "invalid_usage"),
    ([reply(prompt_tokens=-1)], "invalid_usage"),
    ([reply(prompt_tokens_details={"cached_tokens": 101})], "invalid_usage"),
    ([reply(prompt_tokens_details={"audio_tokens": 10})], "unsupported_usage"),
])
def test_missing_ambiguous_or_invalid_usage_is_not_invented(ledger, replies, status):
    result = VeqenOpenAICostTracker().run(replies)
    assert not result["recorded"] and result["recording_status"] == status
    assert result["replies"] is replies and ledger() == []


def test_serialized_pipeline_roundtrip_and_request_override(ledger):
    original = Pipeline()
    original.add_component("cost", VeqenOpenAICostTracker(tags={"feature": "default", "customer": "default"}))
    restored = Pipeline.loads(original.dumps(), allowed_modules=["veqen.integrations.haystack"])
    restored.run({"cost": {"replies": [reply()], "feature": "request", "customer": "request"}})
    event, = ledger()
    assert event["feature"] == "request" and event["customer"] == "request"


def test_haystack_generator_actual_reply_metadata(ledger, monkeypatch):
    from haystack.components.generators.chat import OpenAIChatGenerator
    from haystack.utils import Secret
    from openai.types.chat import ChatCompletion

    generator = OpenAIChatGenerator(api_key=Secret.from_token("synthetic-test-key"), model="gpt-4o")
    generator.warm_up()
    response = ChatCompletion(
        id="synthetic-completion", object="chat.completion", created=1, model="gpt-4o",
        choices=[{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": "PRIVATE_REPLY"}}],
        usage={"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120,
               "prompt_tokens_details": {"cached_tokens": 50}},
    )
    monkeypatch.setattr(generator.client.chat.completions, "create", lambda **kwargs: response)
    try:
        pipeline = Pipeline()
        pipeline.add_component("llm", generator)
        pipeline.add_component("cost", VeqenOpenAICostTracker())
        pipeline.connect("llm.replies", "cost.replies")
        result = pipeline.run({"llm": {"messages": [ChatMessage.from_user("PRIVATE_PROMPT")]}})
        assert result["cost"]["recorded"]
        event, = ledger()
        assert event["input_tokens"] == 50 and event["cache_read_tokens"] == 50
        assert "PRIVATE" not in json.dumps(event)
    finally:
        generator.close()

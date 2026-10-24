"""The LlamaIndex event handler against the real llama-index-core: its dispatcher, events and LLM base classes."""

import json

import pytest

pytest.importorskip("llama_index.core")

from llama_index.core.base.llms.types import CompletionResponse, LLMMetadata
from llama_index.core.instrumentation import get_dispatcher
from llama_index.core.llms import ChatMessage, CustomLLM
from llama_index.core.llms.callbacks import llm_completion_callback

import veqen
from veqen.integrations.llamaindex import VeqenEventHandler


class ReplayLLM(CustomLLM):
    """An LLM that answers with a fixed provider response, the way LlamaIndex's provider classes keep it in ``raw``."""

    raw: dict = {}

    @property
    def metadata(self) -> LLMMetadata:
        return LLMMetadata(model_name="replay")

    @llm_completion_callback()
    def complete(self, prompt: str, formatted: bool = False, **kwargs) -> CompletionResponse:
        return CompletionResponse(text="PRIVATE_ANSWER", raw=self.raw)

    @llm_completion_callback()
    def stream_complete(self, prompt: str, formatted: bool = False, **kwargs):
        # A stream that doesn't report usage
        yield CompletionResponse(text="PRIVATE_ANSWER", delta="PRIVATE_ANSWER", raw={"id": "stream_1"})


OPENAI = {"id": "chatcmpl_1", "model": "gpt-4o-mini", "usage": {"prompt_tokens": 1200, "completion_tokens": 300,
                                                                 "prompt_tokens_details": {"cached_tokens": 200}}}
ANTHROPIC = {"id": "msg_1", "model": "claude-sonnet-4-5", "usage": {"input_tokens": 500, "output_tokens": 40,
                                                                     "cache_read_input_tokens": 100}}


@pytest.fixture
def handler():
    """Veqen's handler on LlamaIndex's root dispatcher, taken off again after the test."""
    dispatcher = get_dispatcher()

    def add(**fields):
        added = VeqenEventHandler(**fields)
        dispatcher.add_event_handler(added)
        handlers.append(added)
        return added

    handlers: list = []
    yield add
    for added in handlers:
        dispatcher.event_handlers.remove(added)


def test_completions_are_priced_from_the_providers_own_usage_with_tags(ledger, handler):
    handler(tags={"feature": "docs-search"})
    with veqen.tags(customer="acme"):
        ReplayLLM(raw=OPENAI).complete("PRIVATE_QUESTION")
        ReplayLLM(raw=ANTHROPIC).complete("PRIVATE_QUESTION")
    openai, anthropic = ledger()
    counts = ("provider", "model", "input_tokens", "cache_read_tokens", "output_tokens")
    assert tuple(openai[k] for k in counts) == ("openai", "gpt-4o-mini", 1000, 200, 300)
    expected = veqen.lookup("openai/gpt-4o-mini").cost(veqen.pricing.Usage(1000, 300, 200))
    assert openai["cost_usd"] == pytest.approx(expected)
    assert (anthropic["provider"], anthropic["input_tokens"], anthropic["cache_read_tokens"]) == ("anthropic", 500, 100)
    assert openai["customer"] == anthropic["customer"] == "acme" and openai["feature"] == "docs-search"
    assert "PRIVATE" not in json.dumps([openai, anthropic])


def test_a_chat_made_through_completion_is_recorded_once(ledger, handler):
    # CustomLLM answers chat() through complete(), so LlamaIndex reports one response as a chat and a completion
    handler()
    ReplayLLM(raw={**OPENAI, "id": "chatcmpl_2"}).chat([ChatMessage(role="user", content="PRIVATE_QUESTION")])
    [event] = ledger()
    assert event["input_tokens"] == 1000


def test_usage_kept_as_the_provider_sdks_own_object_is_read_too(ledger, handler):
    fields = {"__module__": "openai.types.completion_usage", "prompt_tokens": 80, "completion_tokens": 8}
    usage = type("CompletionUsage", (), fields)()
    handler()
    ReplayLLM(raw={"id": "chatcmpl_4", "model": "gpt-4o-mini", "usage": usage}).complete("q")
    [event] = ledger()
    assert (event["provider"], event["input_tokens"], event["output_tokens"]) == ("openai", 80, 8)


def test_responses_without_usage_are_skipped_and_hosts_can_be_named(ledger, handler):
    handler(provider="together")
    ReplayLLM(raw={"id": "x", "model": "gpt-4o-mini"}).complete("q")  # no usage reported
    for _ in ReplayLLM(raw=OPENAI).stream_complete("q"):
        pass
    ReplayLLM(raw={**OPENAI, "id": "chatcmpl_3", "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo"}).complete("q")
    [event] = ledger()
    assert (event["provider"], event["model"]) == ("together", "meta-llama/Llama-3.3-70B-Instruct-Turbo")

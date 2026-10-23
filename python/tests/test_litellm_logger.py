import asyncio
import json
import threading
from datetime import datetime, timezone

import pytest

pytest.importorskip("litellm")

from litellm.integrations.custom_logger import CustomLogger

from veqen.integrations.litellm_logger import VeqenLogger


@pytest.fixture(autouse=True)
def isolated_litellm_callbacks(monkeypatch):
    import litellm

    # LiteLLM promotes configured callbacks into process-global lists on the first request.
    for name in ("callbacks", "input_callback", "success_callback", "failure_callback",
                 "_async_input_callback", "_async_success_callback", "_async_failure_callback"):
        monkeypatch.setattr(litellm, name, [])


def test_real_custom_logger_sync_async_and_failure_paths_only_store_metadata(ledger):
    logger = VeqenLogger()
    assert isinstance(logger, CustomLogger)
    now = datetime.now(timezone.utc).timestamp()
    payload = {"id": "request-123", "startTime": now - 1, "endTime": now,
               "model": "gpt-4o", "custom_llm_provider": "openai", "prompt_tokens": 100,
               "completion_tokens": 20, "response_cost": 1, "status": "success",
               "messages": [{"content": "PRIVATE-CONTENT"}], "response": "PRIVATE-CONTENT",
               "metadata": {"requester_metadata": {"veqen": {"customer": "demo"}, "secret": "PRIVATE-CONTENT"}}}
    kwargs = {"standard_logging_object": payload}
    logger.log_success_event(kwargs, None, None, None)
    asyncio.run(logger.async_log_success_event(kwargs, None, None, None))
    payload["status"] = "failure"
    logger.log_failure_event(kwargs, None, None, None)
    asyncio.run(logger.async_log_failure_event(kwargs, None, None, None))
    events = ledger()
    assert len(events) == 4
    assert [e["status"] for e in events] == ["ok", "ok", "error", "error"]
    assert all(e["input_tokens"] == 100 and e["customer"] == "demo" for e in events)
    assert "PRIVATE-CONTENT" not in json.dumps(events)


def test_malformed_metadata_does_not_break_model_request(ledger):
    logger = VeqenLogger()
    logger.log_success_event({"standard_logging_object": {"id": "bad"}}, None, None, None)
    assert ledger() == []


@pytest.mark.parametrize("usage", [
    {"prompt_tokens": 1.5}, {"prompt_tokens": -1}, {"prompt_tokens": True},
    {"prompt_tokens": 1, "prompt_tokens_details": {"cached_tokens": 2}},
    {"prompt_tokens": 2, "cache_creation_input_tokens": 1, "cache_creation": {"ephemeral_1h_input_tokens": 2}},
])
def test_invalid_counts_are_not_silently_priced(ledger, usage):
    VeqenLogger().log_success_event({"standard_logging_object": {
        "id": "invalid-usage", "endTime": datetime.now(timezone.utc).timestamp(),
        "model": "gpt-4o", "hidden_params": {"usage_object": usage},
    }}, None, None, None)
    assert ledger() == []


def test_non_object_request_metadata_is_ignored(ledger):
    VeqenLogger().log_success_event({"litellm_params": ["invalid"], "standard_logging_object": {
        "id": "valid-usage", "endTime": datetime.now(timezone.utc).timestamp(),
        "model": "gpt-4o", "prompt_tokens": 1,
    }}, None, None, None)
    assert len(ledger()) == 1


def test_litellm_invokes_async_logger_once_for_mocked_completion(ledger, monkeypatch):
    import litellm

    async def run():
        finished = asyncio.Event()

        class ObservedLogger(VeqenLogger):
            async def async_log_success_event(self, *args, **kwargs):
                await super().async_log_success_event(*args, **kwargs)
                finished.set()

        monkeypatch.setattr(litellm, "callbacks", [ObservedLogger()])
        await litellm.acompletion(model="openai/gpt-4o", messages=[{"role": "user", "content": "ASYNC-PRIVATE"}],
                                 mock_response="ASYNC-RESPONSE", metadata={"veqen": {"feature": "async-test"}})
        await asyncio.wait_for(finished.wait(), timeout=10)

    asyncio.run(run())
    [event] = ledger()
    assert event["feature"] == "async-test"
    assert "ASYNC-PRIVATE" not in json.dumps(event) and "ASYNC-RESPONSE" not in json.dumps(event)


def test_litellm_invokes_logger_for_mocked_completion(ledger, monkeypatch):
    import litellm

    finished = threading.Event()

    class ObservedLogger(VeqenLogger):
        def log_success_event(self, *args, **kwargs):
            super().log_success_event(*args, **kwargs)
            finished.set()

    monkeypatch.setattr(litellm, "callbacks", [ObservedLogger()])
    litellm.completion(model="openai/gpt-4o", messages=[{"role": "user", "content": "SYNTHETIC-CONTENT"}],
                       mock_response="SYNTHETIC-RESPONSE", metadata={"veqen": {"feature": "integration-test"}})
    assert finished.wait(10), "LiteLLM never delivered its terminal success callback"
    [event] = ledger()
    assert event["model"] == "gpt-4o"
    assert event["feature"] == "integration-test"
    assert "SYNTHETIC-CONTENT" not in json.dumps(event) and "SYNTHETIC-RESPONSE" not in json.dumps(event)

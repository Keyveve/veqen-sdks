import json

import pytest
import veqen
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_veqen import VeqenCallbackHandler
from veqen.client import client


@pytest.fixture
def ledger(tmp_path, monkeypatch):
    for name in ("VEQEN_API_KEY", "VEQEN_ENDPOINT", "VEQEN_LEDGER_FILE"):
        monkeypatch.delenv(name, raising=False)
    client.configure(api_key="", ledger_file=None)
    client.budgets.clear()
    client.blocked.clear()
    path = tmp_path / "costs.jsonl"
    veqen.init(ledger_file=str(path))
    yield path
    client.budgets.clear()
    client.blocked.clear()


def model():
    return FakeMessagesListChatModel(responses=[AIMessage(
        content="private output must not be recorded",
        response_metadata={"model_name": "gpt-4o"},
        usage_metadata={"input_tokens": 1500, "output_tokens": 200, "total_tokens": 1700,
                        "input_token_details": {"cache_read": 1000}},
    )])


def test_real_callback_dispatch_prices_usage_without_content(ledger):
    model().invoke("private input must not be recorded", config={
        "callbacks": [VeqenCallbackHandler(customer="sample", feature="support")],
        "metadata": {"ls_provider": "openai"},
    })
    text = ledger.read_text()
    [event] = [json.loads(line) for line in text.splitlines()]
    assert (event["input_tokens"], event["output_tokens"], event["cache_read_tokens"]) == (500, 200, 1000)
    assert event["customer"] == "sample" and event["feature"] == "support"
    assert "private input" not in text and "private output" not in text


def test_budget_prevents_framework_model_execution(ledger):
    veqen.budget(0, feature="blocked")
    with pytest.raises(veqen.BudgetExceeded):
        model().invoke("unused", config={"callbacks": [VeqenCallbackHandler(feature="blocked")]})
    assert not ledger.exists()

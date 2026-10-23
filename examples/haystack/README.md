# Haystack chat costs by customer

`VeqenOpenAICostTracker` is a Haystack pipeline component that records usage from an OpenAI-compatible chat generator's completed reply. It passes the reply through unchanged and reads only its model and usage metadata.

```sh
pip install 'veqen[haystack]>=1.2,<2'
export HAYSTACK_TELEMETRY_ENABLED=false
```

Requires Python 3.10+ and Haystack 3.4+. The base Veqen SDK still has no dependencies; Haystack is optional.

```python
import veqen
from haystack import Pipeline
from haystack.components.generators.chat import OpenAIChatGenerator
from haystack.dataclasses import ChatMessage
from veqen.integrations.haystack import VeqenOpenAICostTracker

# Local recording needs no Veqen account. The generator needs OPENAI_API_KEY.
veqen.init(ledger_file="ai-costs.jsonl")

pipeline = Pipeline()
pipeline.add_component("llm", OpenAIChatGenerator(model="gpt-4o-mini", generation_kwargs={"n": 1}))
pipeline.add_component("cost", VeqenOpenAICostTracker(tags={"feature": "support-bot"}))
pipeline.connect("llm.replies", "cost.replies")

result = pipeline.run({
    "llm": {"messages": [ChatMessage.from_user("Explain input and output tokens briefly.")]},
    "cost": {"customer": "customer-123"},
})
veqen.flush()
assert result["cost"]["recorded"], result["cost"]["recording_status"]
print(result["cost"]["replies"][0].text)
```

To send usage to [Veqen](https://veqen-app.com/signup?utm_source=haystack&utm_medium=integration&utm_campaign=launch-v1), set `VEQEN_API_KEY` to an ingest-only key before initializing the SDK. Keep it on your server. Customer and feature inputs override configured defaults per invocation; do not change shared component state for individual users. Use pseudonymous allocation IDs, not names, email addresses or secrets.

## Supported usage

This component supports a single reply containing `meta.model` and OpenAI-shaped `meta.usage.prompt_tokens`, `completion_tokens`, and optional `prompt_tokens_details.cached_tokens`. Cached tokens are separated from uncached input. OpenAI-compatible hosts can be identified with `provider="azure"` or another provider name supported by the Veqen price book; use your actual provider and rates.

Check `recorded` and `recording_status`. Missing usage, multiple alternatives, invalid counts, audio-token usage, and cache-write variants are not guessed or silently summed. They return the original replies with `recorded=False`. Streaming is supported only when the generator's final reply contains complete usage metadata. This is not a generic adapter for every Haystack generator or modality.

The component runs **after** generation and does not block requests or enforce a pre-call budget. A repeated component execution records another event, so connect it once after each provider request. Do not also wrap that request with another Veqen recorder or export its usage through OTLP.

Costs use the local price book and standard pricing rules; negotiated prices, nonstandard service tiers, region adjustments and provider invoices require the appropriate explicit pricing/reconciliation workflow. These estimates are not invoice reconciliation.

## Serialization

Haystack 3 restricts deserialization to trusted modules. For a pipeline definition you trust:

```python
restored = Pipeline.loads(
    pipeline.dumps(),
    allowed_modules=["veqen.integrations.haystack"],
)
```

The serialized component contains provider and allocation defaults, never API keys. Keep default tags non-sensitive.

## Verification

The SDK tests exercise actual Haystack pipelines, reply pass-through, cache accounting, missing/ambiguous usage, per-invocation attribution, content exclusion and YAML serialization. Tests use synthetic replies and need no paid provider account.

Source: [component](../../python/veqen/integrations/haystack.py), [tests](../../python/tests/test_haystack.py). Code is [MIT licensed](../../LICENSE). [Report an issue](https://github.com/Keyveve/veqen-sdks/issues).

# veqen

The cost ledger for AI inference. Usage-based cost for supported model calls (text, embeddings, images, video, speech and transcription, from about 2,000 models across labs, open-model hosts and clouds), attributed to the customer, feature, user or project that caused it, with budgets that check recorded spend before each wrapped request.

```bash
pip install veqen
```

Python 3.10+, no dependencies (LangChain support is the `veqen[langchain]` extra), works offline.

```python
import veqen
from openai import OpenAI

client = veqen.wrap(OpenAI(), feature="support-bot")

with veqen.tags(customer="acme", user="u_42"):
    client.responses.create(model="gpt-5-mini", input="Where is my order?")
```

Every call is priced from the usage the provider reports, with the rules providers bill by: cached input, 5-minute and 1-hour cache writes, batch, priority and flex tiers, long-context rates and data residency. Prompts and responses are never read.

- **Wrap** OpenAI (sync and async, streams, Responses, Chat Completions, embeddings, images and audio), Anthropic (messages and streams) and Google GenAI clients. An OpenAI client pointed at Together, Fireworks, Groq, Azure AI Foundry or another compatible host is priced as that host; name your own servers with `veqen.wrap(client, provider="self-hosted")`.
- **Tag** calls with `veqen.tags(customer=..., feature=..., user=..., project=...)`; tags follow `asyncio` code.
- **Budget**: `veqen.budget(5.00, customer="*")` raises `veqen.BudgetExceeded` before subsequent wrapped calls once recorded spend reaches the limit.
- **Record** anything else: `veqen.record("claude-sonnet-5-5", provider="anthropic", input_tokens=1200, output_tokens=300)`, or by unit for media models: `veqen.record("veo-3.1-generate-001", provider="google", units=8, variant="1080p")`.
- **Price** without recording: `veqen.cost("gpt-4o", 1000, 500)` returns `0.0075`.
- **Integrations**: `veqen.integrations.langchain`, `veqen.integrations.litellm`, `veqen.integrations.openai_agents`.

In serverless functions, call `veqen.flush()` before returning. Write a local ledger with `veqen.init(ledger_file=".veqen/ledger.jsonl")` and see cost per customer, feature and model with `npx veqen report`. Set `VEQEN_API_KEY` to send calls to the [Veqen dashboard](https://veqen-app.com) for shared budgets, reconciliation with your provider bills, custom and self-hosted prices, margin per customer and month-end journal entries. Free for 60,000 tracked calls a month.

Docs: https://veqen-app.com/docs/python · Model prices: https://veqen-app.com/models · MIT licensed.

Budgets are not guaranteed spending caps. In-flight and concurrent calls can exceed the limit. Local counters are per process and reset on restart; dashboard budgets also depend on ingestion and polling delays.

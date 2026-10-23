# Veqen for LangChain and LangGraph

Record model usage and estimated AI cost by customer, feature and project. This package exposes the callback maintained in the [Veqen SDK](https://github.com/Keyveve/veqen-sdks/tree/main/python); it does not wrap or alter your model's response.

```bash
pip install langchain-veqen langchain-openai
```

```python
import veqen
from langchain_openai import ChatOpenAI
from langchain_veqen import VeqenCallbackHandler

# No Veqen account needed for local JSONL recording.
veqen.init(ledger_file="ai-costs.jsonl")
model = ChatOpenAI(model="gpt-4o-mini", stream_usage=True)
answer = model.invoke(
    "Explain the difference between input and output tokens.",
    config={"callbacks": [VeqenCallbackHandler(customer="demo", feature="assistant")]},
)
veqen.flush()
```

Set `OPENAI_API_KEY` for this example. To send usage to your organization's ledger, set `VEQEN_API_KEY` to an ingest-only key from [Veqen](https://veqen-app.com/app/settings/keys) before starting the process. Keep credentials on the server.

Attach the handler to a LangGraph invocation's callback configuration to propagate it to model calls in the graph. Use either this handler or a wrapped provider client for each call, to avoid recording twice.

The handler reads standard `AIMessage.usage_metadata` and model/provider metadata. Chat integrations must expose that information, including streaming usage when streaming. It separates cache reads and writes from uncached input tokens. Calls without usage metadata or a model identifier are not recorded; it does not guess their token counts. This callback supports token-based chat usage, not every provider-specific media billing field.

Only usage and allocation metadata enter the ledger; prompt and response text are not recorded. Cost uses the SDK's versioned price book and is an estimate until reconciled against the provider bill. Local budgets and cached cloud budget decisions are checked before model execution. See [budget behavior and limits](https://veqen-app.com/docs/budgets).

[Integration documentation](https://veqen-app.com/docs/langchain) · [Price book](https://veqen-app.com/docs/price-book) · [Report a problem](https://github.com/Keyveve/veqen-sdks/issues)

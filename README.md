# Veqen: the cost ledger for AI inference

Record model usage, calculate cost from a versioned price book, and attribute it to a customer, feature, user or project. The Python and JavaScript SDKs work locally without an account. Connect the optional [Veqen dashboard](https://veqen-app.com/signup?utm_source=github&utm_medium=referral&utm_campaign=launch-v1) for shared budgets, provider reconciliation and finance exports.

## Python

```sh
pip install 'veqen>=1,<2'
```

```python
import veqen
from openai import OpenAI

client = veqen.wrap(OpenAI(), feature="support-bot")
with veqen.tags(customer="acme"):
    client.responses.create(model="gpt-5-mini", input="Where is my order?")
```

Python 3.10+, no runtime dependencies. See [Python documentation](python/README.md) for optional integrations.

## JavaScript and TypeScript

```sh
npm install veqen@^1
```

```javascript
import OpenAI from "openai";
import { wrap, withTags } from "veqen";

const client = wrap(new OpenAI(), { feature: "support-bot" });
await withTags({ customer: "acme" }, () =>
  client.responses.create({ model: "gpt-5-mini", input: "Where is my order?" }));
```

Node.js 20+, ESM, TypeScript declarations, no runtime dependencies. See [JavaScript documentation](js/README.md).

## Free CLI and pull-request reviews

```sh
npx veqen@1 scan
npx veqen@1 diff origin/main
npx veqen@1 audit
npx veqen@1 report
```

Scan model references for prices and retirement dates, compare model changes, import provider usage locally with your admin key, or report on a local ledger. The [cost-review Action](github-action/README.md) adds a pull-request summary and optional retirement checks. It never executes the reviewed application's code. Use `pull_request`, not `pull_request_target`.

## Accuracy, budgets and privacy

Costs use provider-reported usage and the bundled price book, including supported cache, batch, tier and residency rules. Negotiated rates, missing usage and unsupported model variants need explicit prices or reconciliation; calculated costs are not a provider invoice. Derived price data retains its [upstream MIT attribution](pricebook/THIRD_PARTY_NOTICES).

Budgets check recorded spend before a wrapped call. They block subsequent calls once the observed limit is reached; a call already in flight can exceed it. Local budgets are per process and reset on restart. Dashboard budgets are polled, so concurrency, ingestion and polling delays can also cause overshoot. These are not guaranteed spending caps.

No account or network reporting is required for local cost tracking. Set `VEQEN_API_KEY` to send usage metadata and your tags to Veqen. Avoid personal data and secrets in tags. The SDK does not send prompt or response content.

## Agent integration

Connect to `https://veqen-app.com/mcp` using OAuth or a Veqen API key. Root `plugin.json`, `mcp.json` and [skills](skills/) describe the agent integration. See [connection instructions](https://veqen-app.com/ai-agents).

## Migrating from 0.x

Version 1 is a different product and a breaking API change. The old `Veqen().signup(...)` risk-check client and `@veqen/sdk` JavaScript package are not compatible with these APIs. Remove those integrations before upgrading; the retired signup-check endpoints must not be used for new implementations. The historical `data/` blocklist remains for attribution and compatibility, but is no longer refreshed here.

## Development

```sh
python -m pip install -e 'python[test]'
python -m pytest python/tests
cd js
npm ci --ignore-scripts
npm test
```

Code: [MIT](LICENSE). Historical dataset: [CC0](data/README.md). Support: [support@veqen-app.com](mailto:support@veqen-app.com).

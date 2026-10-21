# Veqen SDKs and disposable-email data

Official Python and JavaScript/TypeScript clients for [Veqen](https://veqen-app.com), a product of Keyveve, Inc.

Check signup risk from email, IP, phone and domain signals. Responses include a score, an admit/review/refuse verdict, and reasons. Scores are heuristic signals, not probabilities or guarantees of fraud.

## Start with 1,000 free monthly credits

[Create an account](https://veqen-app.com/signup), verify your email, and create an API key. Keep it on your server in `VEQEN_API_KEY`.

### Python

```sh
pip install veqen==0.1.0
```

```python
from veqen import Veqen
with Veqen() as client:
    result = client.signup(email="example@mailinator.com", ip="8.8.8.8")
    print(result["risk"])
```

### JavaScript / TypeScript

```sh
npm install https://veqen-app.com/static/sdk/veqen-sdk-0.1.0.tgz
```

```javascript
import { Veqen } from "@veqen/sdk";
const client = new Veqen();
console.log((await client.signup({email: "example@mailinator.com", ip: "8.8.8.8"})).risk);
```

The Python SDK is published on PyPI; the JavaScript download works while npm publication is being completed. See [Python](python/README.md), [JavaScript](js/README.md), [API documentation](https://veqen-app.com/docs), [pricing](https://veqen-app.com/pricing), and the [free tools](https://veqen-app.com/tools).

## Connect an AI agent

MCP endpoint: `https://veqen-app.com/mcp`. Use OAuth or a Veqen API key. The official registry name is `io.github.Keyveve/veqen`. [Connection instructions](https://veqen-app.com/ai-agents).

Compatible Agent Plugins clients and directories can import this repository: root `plugin.json` and `mcp.json` follow the [Agent Plugins 1.0.0 schemas](https://agent-plugins.org/). They point to the hosted server and contain no credentials; OAuth authentication is managed by your client. Other MCP clients can connect directly to the endpoint above.

Checks spend credits (one for individual checks, three for signup checks); balance reads are free. Enabled auto top-ups can charge a saved payment method when credits run low.

## Disposable-email data

[data/disposable-email-domains.txt](data/disposable-email-domains.txt) mirrors the upstream CC0 [disposable-email-domains](https://github.com/disposable-email-domains/disposable-email-domains) blocklist. The scheduled workflow refreshes it daily and records the upstream revision. A listed domain is a signal to investigate; it does not establish that a person is fraudulent. The API adds DNS and other context beyond this list.

## Development

```sh
python -m pip install -e python pytest
cd python && python -m pytest tests
cd ../js && npm ci --ignore-scripts && npm test
```

Client code: [MIT](LICENSE). Dataset: CC0; see [data/README.md](data/README.md). Support: [support@veqen-app.com](mailto:support@veqen-app.com).

# Veqen AI cost starter

See what one AI response costs, then what it could cost at scale. This Next.js and Vercel AI SDK starter puts a simple cost receipt beside each response. Try the recorded example without an account or API key; it calculates prices locally and makes no model calls. Add your own keys when you are ready to try a protected live request.

[Try the live demo](https://veqen-ai-cost-starter.vercel.app/).

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2FKeyveve%2Fveqen-sdks%2Ftree%2Fmain%2Fexamples%2Fvercel-ai-cost-starter&project-name=veqen-ai-cost-starter&repository-name=veqen-ai-cost-starter)

## Run locally

Node.js 22 or later:

```sh
npm ci
npm test
npm run dev
```

Open `http://localhost:3000`. Select a model, run the recorded example and adjust the monthly volume. The response and usage counts are a fixed sample; the cost is computed from the installed Veqen price book. Cheaper models are not presumed equally capable.

## Enable a protected live request

Copy `.env.example` to `.env.local`. Set your own `OPENAI_API_KEY` and a random `DEMO_ACCESS_TOKEN` of at least 32 characters, then restart. Use the deployment access token in the form's **Live inference** mode; never enter the provider API key in the browser. Live calls incur your provider's charges. The route allows only the two configured models, limits the prompt and output, disables retries and uses a request timeout.

The shared access token is for a private demo, not a multi-user authentication system. Before serving live inference to users, replace it with your own authenticated session and durable per-user quota. The public demonstration should keep the provider and access-token variables unset.

Optionally set `VEQEN_API_KEY` to your **send-only** key to record real usage in your ledger. The middleware emits only real provider usage, tags each call with a run ID, and `flush()` runs before the serverless response finishes. Recorded example fixtures bypass the middleware and are never sent. The browser receives the response, token counts, list-price estimate and book version, never server credentials.

The receipt separates cache-read tokens from fresh input. Its estimate excludes infrastructure, invoice credits and negotiated discounts. SDK sending is best effort; a successful response is not proof that a ledger event was accepted.

## Files and verification

- `app/api/run/route.js`: bounded example/live endpoint and AI SDK middleware.
- `lib/receipt.js`: server-side pricing calculation.
- `app/workbench.jsx`: accessible form, response, receipt and volume projection.
- `test/receipt.test.js`: cache accounting, unknown prices and input validation.

Run `npm run build` before deployment. This starter pins AI SDK 6, whose middleware uses `specificationVersion: 'v3'`; upgrading the AI SDK major requires retesting its usage shape. Do not silently use unsupported versions.

[Veqen documentation](https://veqen-app.com/docs) · [Open a cost ledger](https://veqen-app.com/signup?utm_source=vercel&utm_medium=integration&utm_campaign=launch-v1) · [Pricing methodology](https://veqen-app.com/docs/price-book)

MIT licensed; see the repository's root LICENSE. Model pricing data retains its third-party notices in `@veqen/sdk`.

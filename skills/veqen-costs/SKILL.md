---
name: veqen-costs
description: Add AI cost tracking to a codebase with Veqen (wrap OpenAI, Anthropic, Gemini or any OpenAI-compatible client, for text, embedding, image and audio calls; tag calls by customer, feature, user or project; set budgets), or answer questions about AI spend, model prices, model switches and what a workload would cost. Use when the user asks what their AI calls cost, wants cost per customer or feature, wants to cap AI spend, or is choosing between models on price.
---

# Veqen: AI cost tracking

## Adding Veqen to code

1. Detect the language and AI clients in use (`openai`, `anthropic`, `@anthropic-ai/sdk`, `google-genai`, `@google/genai`, the Vercel AI SDK `ai`, LangChain, LiteLLM, the OpenAI Agents SDK). OpenAI clients pointed at Together, Fireworks, Groq, Azure AI Foundry or another compatible host are priced as that host; for your own servers pass `provider="self-hosted"` to `wrap`. `npx @veqen/sdk init` prints the setup for the current project.
2. Install: `pip install veqen` (`veqen[langchain]` for LangChain) or `npm install @veqen/sdk`.
3. Wrap each client where it's created and name the feature:
   - Python: `client = veqen.wrap(OpenAI(), feature="support-bot")`
   - TypeScript: `const client = wrap(new OpenAI(), { feature: "support-bot" })`
   - Vercel AI SDK: `wrapLanguageModel({ model, middleware: veqen({ feature: "chat" }) })` from `@veqen/sdk/ai-sdk`
4. Set the customer and user (or, for internal and research work, the `project`) once per request, at the framework's middleware or request handler, not at each call:
   - Python: `with veqen.tags(customer=org_id, user=user_id): ...`
   - TypeScript: `withTags({ customer: org.id, user: user.id }, () => ...)`
   Use internal ids, never emails or names.
5. Tell the user to set `VEQEN_API_KEY` (an **ingest** key from Settings › API keys) where the app runs. Without it, costs are priced locally only.
6. In serverless handlers, call `veqen.flush()` / `await flush()` before returning.

Never log, send or store prompts or responses for Veqen; the SDK reads token usage only.

## Budgets

For free plans, add a per-user cap and handle the exception with an upgrade message:

```python
veqen.budget(2.00, user="*")   # each user: $2 of inference a month
try:
    ...
except veqen.BudgetExceeded as exc:
    return upgrade_prompt(exc.limit_usd)
```

Budgets shared across servers (per organization, customer, feature, user or project) are created in the dashboard (Budgets) or with the `set_budget` MCP tool.

## Answering cost questions

With the Veqen MCP server connected, prefer its tools over estimates:

- totals and breakdowns: `get_spend` (group_by provider, model, customer, feature, user, project or environment)
- one customer, or margin: `get_customer_cost`, `get_margin`
- "why did cost change": `explain_change`
- "what if we used model X": `estimate_switch` (real volumes), else `compare_models`
- "what would this workload cost" (any mix of text, image, video and audio models): `simulate_workload`
- prices: `get_model_price`, `list_models` (also on the public server at https://veqen-app.com/mcp/prices, with `compare_models` and `simulate_workload`)
- "does it match the invoice": `reconciliation_status`; "which credits expire": `credits_expiring`; plan and usage: `get_account`

Quote amounts in USD with the date range used. A cheaper model isn't automatically equivalent: recommend testing quality before switching.

Docs: https://veqen-app.com/docs

# Veqen Pricing plugin

A portable plugin package for the public, unauthenticated `https://veqen-app.com/mcp/prices` endpoint. It exposes exactly four read-only tools: model lookup, model listing, model comparison and workload simulation. It cannot access organization spend or change a ledger.

`plugin.json` supplies directory copy, icons, three starter prompts and five positive / three negative review cases. `mcp.json` declares the public server with no authentication. Zip those two files and `assets/` at the archive root to prepare an upload. Do not include this README in the review archive.

As of 2026-10-24 UTC, direct live MCP checks passed all six tested calls, including cached-input accounting and an unknown-model error. The [captured tool walkthrough](https://github.com/Keyveve/veqen-sdks/releases/tag/pricing-plugin-v1.5.0) demonstrates those calls using a local MCP client. It does not replace end-to-end host testing. Version 1.5.1 corrects only the review examples: the three negative prompts concern unavailable private spend, unsupported mutations and an educational request unrelated to pricing; the unknown-model check is a separate error-handling case. Runtime tools are unchanged.

OpenAI business verification is approved and the package is uploaded as a draft. Domain verification, tool discovery and final submission are still pending. No OpenAI directory approval is claimed.

The root repository plugin is the separate authenticated Veqen ledger integration. Do not swap its credentials or write-capable endpoint into this public pricing package.

[Connection documentation](https://veqen-app.com/docs/mcp) · [Pricing methodology](https://veqen-app.com/docs/price-book)

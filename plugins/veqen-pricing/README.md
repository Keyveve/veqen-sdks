# Veqen Pricing plugin

A portable plugin package for the public, unauthenticated `https://veqen-app.com/mcp/prices` endpoint. It exposes exactly four read-only tools: model lookup, model listing, model comparison and workload simulation. It cannot access organization spend or change a ledger.

`plugin.json` supplies directory copy, icons, three starter prompts and five positive / three negative review cases. `mcp.json` declares the public server with no authentication. Zip those two files and `assets/` at the archive root to prepare an upload. Do not include this README in the review archive.

As of 2026-10-23, direct live MCP checks passed all six tested calls, including cached-input accounting and an unknown-model error. These protocol checks do not replace an end-to-end host review or demo recording. OpenAI upload is blocked until the owner's developer identity is verified; no OpenAI directory approval is claimed. Domain verification and the requested reviewer recording must also be completed when the portal allows the submission.

The root repository plugin is the separate authenticated Veqen ledger integration. Do not swap its credentials or write-capable endpoint into this public pricing package.

[Connection documentation](https://veqen-app.com/docs/mcp) · [Pricing methodology](https://veqen-app.com/docs/price-book)

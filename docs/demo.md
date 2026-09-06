# Sharewell demo guide

Do not record or upload the demo during this commit. Video production is deferred
to the follow-up commit after the distribution PR is opened.

## Lane A: authenticated live Binance MCP

Show the host's Sharewell installation and the official Binance Agent OS MCP
connection. Complete OAuth in the browser, show the live tool catalog, query the
Spot account, and query a market symbol. If the development account is still
empty, show that state clearly. Do not expose tokens, cookies, account identifiers,
or private configuration.

## Lane B: deterministic Sharewell workflow

Use visibly labeled `SYNTHETIC / DEMO` data to show portfolio analysis, target
allocation, a rebalance proposal, proposal hash and approval record, bounded order
preparation, duplicate-dispatch protection, and synthetic fill reconciliation.
Synthetic fills are demonstrations of the local journal and must never be called
Binance fills.

## Optional future funded end-to-end

If funds are intentionally made available later, execute one minimal Spot rebalance
with explicit approval. Capture the order ID, fills, commission, before and after
balances, and update `docs/verification.md`. This is optional and is not required
for the current submission.

# Sharewell demo guide

Public demo video: [Sharewell on YouTube (2:27)](https://youtu.be/Y1d_f8lcif0)

The video demonstrates the core portfolio analysis and explicitly approved
rebalancing workflow. It does not visually demonstrate every adaptive V2
capability implemented in the repository.

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

## Adaptive V2 repository functionality

The repository also implements persistent portfolio memory and policies,
multi-numeraire analysis, the generic evaluator registry, historical Spot Kline
evaluation and verified-outcome execution learning. These capabilities are
separately testable and documented, but are not all shown in the current video.

## Optional future funded end-to-end

If funds are intentionally made available later, execute one minimal Spot rebalance
with explicit approval. Capture the order ID, fills, commission, before and after
balances, and update `docs/verification.md`. This is optional and is not required
for the current submission.

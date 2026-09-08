# Binance Agent OS Mini Hackathon submission

## X Handle URL

<OWNER TO FILL>

## Track

Track A — Agent Creation

## Theme

Trading Workflows

## Project description

Sharewell connects live evidence to an auditable, approval-gated Binance Spot
workflow:

```text
live evidence → persistent policies and memory → evaluation
→ adaptive recommendations → approved rebalance proposal
→ Binance confirmation → execution and reconciliation → execution learning
```

The official Binance Agent OS MCP supplies authenticated account and market
evidence. Sharewell's deterministic core evaluates portfolio state and supplied
historical Spot Klines, preserves account-scoped policies and snapshots, and
learns execution quality only from verified outcomes. It presents bounded routes,
quantities, prices, fees, residuals, and expiry for explicit user approval. The
host preserves Binance OAuth and native confirmation, then Sharewell records
client order IDs, queries fills, refreshes balances, and reports reconciliation.
One Python core is packaged for Codex, Claude Code, and compatible hosts. The
development Agentic Spot account is unfunded; no funded live execution is claimed.

## Video platform

YouTube

## Public video URL

https://youtu.be/Y1d_f8lcif0

## GitHub

https://github.com/ezpahlevi/sharewell

## Step-by-step replication guide

1. Install Sharewell in a supported agent host.
2. Connect or authorize the official Binance Agent OS MCP.
3. Grant market and account permissions; grant Spot Trade only if execution is desired.
4. Ask Sharewell to analyze the Binance Spot portfolio.
5. Provide target allocation percentages and a slippage constraint.
6. Review the generated rebalance proposal.
7. Explicitly approve the exact proposal.
8. Complete Binance's native confirmation for execution.
9. Sharewell queries order and fill results.
10. Sharewell refreshes balances and reports actual allocation and residual drift.
11. Optional read-only query: ask `Evaluate BTC, ETH and SOL over 3, 7, 14 and 30 days.`

Users without a funded Agentic Spot account can reproduce plugin installation,
OAuth, the live MCP catalog, live account and market reads, and the deterministic
Sharewell workflow. Funded execution requires the user's own funded Agentic Spot
sub-account.

## Evidence status

- 113 local tests pass.
- GitHub Actions tests, compileall and release packaging pass.
- Deterministic packaging is verified.
- Authenticated official Binance Agentic MCP reads are verified, including a
  read-only `spot.klines` Spot 1d sample.
- Historical UTC normalization and evaluator path are implemented.
- The current Agentic Spot account is unfunded; no funded live execution is
  verified or claimed.

## Video status

PUBLIC VIDEO AVAILABLE

The existing 2:27 video demonstrates the core analysis and approved-rebalancing
workflow. Adaptive portfolio memory and historical market evaluation are
implemented in the repository but are not all visually demonstrated in that
recording.

## Distribution boundary

This submission uses Codex repository distribution, Claude Code local plugin
loading, and compatible hosts with official Binance MCP. The full trading-capable
plugin is not submitted to the universal OpenAI public Plugins Directory under
its current crypto and investment execution policy.

## Submission post

<OWNER TO FILL AFTER VIDEO>

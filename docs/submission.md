# Binance Agent OS Mini Hackathon submission

## X Handle URL

<OWNER TO FILL>

## Track

Track A — Agent Creation

## Theme

Trading Workflows

## Project description

Sharewell turns Binance Spot rebalancing into a reviewable conversation. Instead
of manually checking balances, calculating weights, finding valid pairs, applying
filters and fees, and monitoring fills, a user asks Sharewell to inspect the
portfolio. Sharewell reads live account and market evidence through the official
Binance Agent OS MCP, calculates exposure and target allocation drift, and presents
a bounded rebalance proposal with routes, quantities, prices, fees, residuals, and
expiry. The user can modify or explicitly approve that proposal. The host preserves
Binance OAuth and its native confirmation step, then Sharewell records the stable
client order IDs, queries fills, refreshes balances, and reports actual allocation
and remaining drift. One Python core is packaged as a Codex plugin, Claude Code
plugin, and generic skill bundle, so the workflow stays consistent across agent
hosts. The development Agentic Spot account is unfunded; no funded live execution
is claimed.

## Video platform

<OWNER TO FILL AFTER VIDEO IS CREATED>

## Public video URL

<OWNER TO FILL AFTER VIDEO IS CREATED>

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

Users without a funded Agentic Spot account can reproduce plugin installation,
OAuth, the live MCP catalog, live account and market reads, and the deterministic
Sharewell workflow. Funded execution requires the user's own funded Agentic Spot
sub-account.

## Evidence status

- 68 local tests pass.
- GitHub Actions runs tests, compiles production Python, and verifies packaging.
- Authenticated official Binance MCP reads are verified.
- The current Agentic Spot account is unfunded.
- No funded live trade is claimed.

## Video status

NOT RECORDED YET

Video will be produced after the distribution PR is opened.

## Distribution boundary

This submission uses Codex repository distribution, Claude Code local plugin
loading, and compatible hosts with official Binance MCP. The full trading-capable
plugin is not submitted to the universal OpenAI public Plugins Directory under
its current crypto and investment execution policy.

## Submission post

<OWNER TO FILL AFTER VIDEO>

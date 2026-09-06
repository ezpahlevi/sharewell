# Sharewell judge guide

## Product

Sharewell is a conversational Binance Spot portfolio agent. It reads live account
and market state through the official Binance Agent OS MCP, calculates exposure and
allocation drift, prepares bounded rebalance plans, requires explicit approval, and
reconciles execution results in chat.

## Problem

Manual rebalancing means inspecting balances, calculating weights, finding valid
routes, applying symbol filters and fees, sizing orders, monitoring fills, and
checking the resulting allocation. Sharewell turns that chain into one reviewable
conversation.

## Architecture

```text
User
  ↓
Codex / Claude / compatible host
  ↓
Sharewell skill and Python core
  ↓
Official Binance Agent OS MCP
  ↓
Binance Spot account and market evidence
  ↓
Analysis → proposal → explicit approval
  ↓
Binance confirmation → execution → fills
  ↓
Fresh balances and reconciliation in chat
```

The host owns chat, OAuth, native MCP calls, and Binance confirmation. Sharewell
owns deterministic financial calculations and its persistent SQLite journal.

## Technical differentiators

- One shared financial core for multiple agent hosts.
- Official Binance MCP and host-managed OAuth; no API-key storage.
- Dynamic Spot symbol discovery and Decimal-based calculations.
- Exchange-filter-aware prices, quantities, minimums, maximums, and fees.
- Multi-pair route planning with bounded slippage and residual reporting.
- Immutable proposal hashes and stable client order IDs.
- Duplicate-dispatch protection, unknown-submission handling, and partial-fill state.
- Post-fill balance reconciliation with explicit fee reviews.

## Safety model

Sharewell supports Spot only. It has no Futures, Margin, withdrawal, or autonomous
background-trading path. Sharewell approval does not bypass Binance confirmation.
An ambiguous submission is queried by its stable client order ID and is never
blindly repeated.

## Verification matrix

| State | Evidence |
| --- | --- |
| VERIFIED LOCAL | 68 deterministic tests, packaging, installation, and source checks |
| VERIFIED AUTHENTICATED BINANCE READ | OAuth catalog, account, open orders, market, filter, commission, and execution-rule reads |
| IMPLEMENTED | Proposal, approval, dispatch guard, journaling, fill recording, and reconciliation paths |
| NOT VERIFIED FUNDED | Development Agentic Spot account has no balances; no funded order or live rebalance is claimed |

## Installation and reproduction

Codex repository marketplace:

```text
codex plugin marketplace add ezpahlevi/sharewell
codex plugin add sharewell@sharewell
```

The plugin supplies the endpoint configuration. The user completes Binance OAuth
and any required permissions in the host. Then ask Sharewell to analyze the Spot
portfolio. For a rebalance, provide exact targets and slippage, review the plan,
approve it explicitly, complete Binance confirmation, and wait for fresh balance
reconciliation.

Claude Code can load the repository with `claude --plugin-dir <sharewell-path>`;
its root `.mcp.json` is picked up after plugin reload. Generic skill-capable hosts
can use the installer in `adapters/generic/README.md`.

## Distribution boundary

The full Sharewell workflow is distributed through the Codex repository
marketplace, Claude Code repository or local plugin loading, and compatible
agent hosts using official Binance MCP. It is not submitted to the universal
OpenAI public Plugins Directory while that directory's current policy excludes
crypto or investment trade execution. This is a distribution-policy boundary;
the plugin's execution architecture is unchanged.

```text
Analyze → plan → explicit Sharewell approval → Binance confirmation
→ execute → reconcile
```

## Repository map

```text
core/       calculations, filters, journal, schemas
providers/  Binance MCP response and native binding logic
skills/     host-facing workflow and runtime entrypoint
adapters/   Codex, Claude, and generic installation notes
docs/       verification, integration, and submission material
```

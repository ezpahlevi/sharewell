# Sharewell

Analyze and rebalance a Binance Spot portfolio through chat. Your AI host handles
conversation and the official Binance MCP connection; Sharewell computes values,
allocation differences and bounded order proposals, then journals approved
execution and reconciles fills with balances.

[![Sharewell checks](https://github.com/ezpahlevi/sharewell/actions/workflows/ci.yml/badge.svg)](https://github.com/ezpahlevi/sharewell/actions/workflows/ci.yml)

Binance Agent OS Mini Hackathon · Track A — Agent Creation · Theme — Trading Workflows

**Demo video:** [Watch Sharewell on YouTube (2:27)](https://youtu.be/Y1d_f8lcif0)

The official Agentic OAuth connection, native Spot catalog, and authenticated
read-only account flow were verified in Codex on 2026-09-07. The tested Agentic
sub-account was empty, so no funded order was placed. See
[verification](docs/verification.md) for the exact evidence and limits.

## Judge Quickstart

Install the repository marketplace in Codex:

```text
codex plugin marketplace add ezpahlevi/sharewell
codex plugin add sharewell@sharewell
```

The plugin includes the official Binance Agent OS MCP endpoint. Complete Binance
OAuth in the host, then ask: `Analyze my Binance Spot portfolio.` For a rebalance,
provide exact target percentages and a slippage limit; Sharewell shows a proposal
before any execution.

Technical details: [judge guide](docs/judge-guide.md). Demo plan:
[demo guide](docs/demo.md). Submission fields: [submission](docs/submission.md).

## Install

Requires Python 3.11+ and an AI host with native remote MCP/OAuth, confirmations,
local command execution and file I/O. There are no Python runtime dependencies.

- [Codex](adapters/codex/README.md): plugin manifest or a project skill bundle.
- [Claude Code](adapters/claude/README.md): native plugin manifest.
- [Cursor and compatible hosts](adapters/generic/README.md): self-contained skill bundle.

Connect `https://agent.binance.com/mcp/agentic` using your host's official MCP
connection flow. Authentication stays in the host. Sharewell never requests API
keys. Main-account read access is for analysis; trading requires an authorized
Agentic Spot sub-account. Funding is not part of Sharewell.

## Chat flow

Ask "Use Sharewell to analyze my Binance Spot portfolio." Then provide the target
percentages and acceptable slippage when you want to rebalance. Sharewell shows
the account, orders, price bounds, estimated fees, residual allocation and expiry.
Approve that concrete proposal to proceed. Binance presents its own required
confirmation. Sharewell queries fills and reports reconciled actual allocation.

Partial fills, expired orders and unresolved submissions are not successful
completion. Unknown outcomes are queried by their persistent client order ID;
they are never blindly resubmitted.

## Architecture

```text
AI host chat + native Binance MCP tools
          | local JSON requests/results
Sharewell core + persistent SQLite journal
```

One core and skill are shared by thin host adapters. There is no custom MCP
server, dashboard, LLM API, background trader, margin, futures or withdrawal code.
The host must supply authentic tool evidence; the journal is not a sandbox
against a malicious host bypassing the skill.

## Safety

Sharewell is Spot-only. It has no Futures, Margin, withdrawal, or autonomous
background-trading path. Approval in Sharewell does not bypass Binance's native
confirmation.

Sharewell only accepts market and account evidence that is less than 60 seconds
old, and refreshes balances, quotes, filters, and open orders again immediately
before execution.

Ambiguous submissions are queried by their stable client order ID and are never
blindly repeated.

## Verification

Authenticated official Binance Agentic reads are verified. Local deterministic
tests and packaging checks are verified. Funded order execution and final live
rebalance remain not verified because the development Agentic Spot account is
unfunded. See [verification](docs/verification.md).

All symbols are discovered dynamically; there is no hardcoded coin or USDT list.
Disconnected pricing, invalid filters, locked funds and residual dust remain
explicit. Current routing limitations are listed in the verification document.

Implementation details: [architecture](docs/architecture.md),
[Binance MCP](docs/binance-mcp.md), [error codes](docs/errors.md), and
[development](docs/development.md).

## Development checks

```text
python -B -m unittest discover -s tests -v
```

Run from this directory. Tests use labeled synthetic fixtures and temporary
SQLite files, never a Binance account. Keep account data outside the plugin cache
and repository, and preserve its journal across upgrades and restarts.

Official references: [Binance Agent OS MCP](https://developers.binance.com/en/docs/agent-native/mcp-server/agentic),
[Binance documentation index](https://developers.binance.com/en/docs/llms.txt),
[Claude plugin reference](https://code.claude.com/docs/en/plugins-reference),
[Cursor skills](https://cursor.com/docs/skills).

# Sharewell

Analyze and rebalance a Binance Spot portfolio through chat. Your AI host handles
conversation and the official Binance MCP connection; Sharewell computes values,
allocation differences and bounded order proposals, then journals approved
execution and reconciles fills with balances.

The official Agentic OAuth connection, native Spot catalog, and authenticated
read-only account flow were verified in Codex on 2026-09-07. The tested Agentic
sub-account was empty, so no funded order was placed. See
[verification](docs/verification.md) for the exact evidence and limits.

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

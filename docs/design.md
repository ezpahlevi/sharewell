# Sharewell design

The approved build objective supersedes the earlier read-only concept. Sharewell is a chat plugin with an independent Python 3.11+ calculation core and native Binance MCP tool calls performed by the AI host. It includes no custom MCP server, dashboard, LLM API, direct Binance REST execution, autonomous trading, futures, margin or withdrawals.

## Trust and execution

The host owns authentication and user interaction. Sharewell does not copy OAuth tokens, accept API keys, or impersonate Binance confirmations. A skill directs the host to collect live tool results and call a finite local CLI for calculations and a durable execution journal. The journal issues exact approved order parameters; the host submits them using its existing official Binance MCP connection. This is a trusted-host workflow, not a sandbox against a malicious host with arbitrary filesystem/tool access.

Account identity, Spot wallet scope and account kind travel with every snapshot and proposal. Main-account read-only views can be analyzed but cannot be executed. Agentic sub-account trading requires the relevant Binance permissions. No implicit funding or account switching.

Every current Spot symbol is eligible through discovered exchange metadata, without a coin/USDT allowlist. Valuation and conversion use a graph of available pairs, including inverse and multi-hop routes. Disconnected assets are reported as unpriced and block a complete allocation proposal. Non-TRADING symbols and symbols without Spot permissions cannot be used. Locked balances count toward holdings but cannot be spent.

All amounts enter as decimal strings and are calculated with Decimal. Quotes are timestamped, spread-aware and not assumed pegged to USD. Rebalance proposals include targets, estimated orders, route dependencies, fee allowance, bounded limit prices, expiry and a hash. Orders use LIMIT IOC to bound execution prices. Rounding and dust are visible. Exchange filters are checked locally where their required data is available; Binance remains the final authority on admissibility.

Explicit approval is tied to an immutable proposal hash, account and expiry. Modifications require a new proposal. Before each order, refresh account, quotes, filters and open orders, then validate exact parameters and available funds. Persist a submission marker before emitting any external write. Never automatically repeat an ambiguous submission. Query the same client order ID. Awaiting Binance confirmation, open/partial orders, rejected orders and unknown outcomes are not completion. No following dependent leg proceeds until a terminal full fill has been verified. Partial execution stops the batch and requires a new proposal for the remaining allocation.

Final verification requires order evidence and a fresh matching-account Spot balance snapshot. Report actual allocation and residual drift rather than claiming the target was achieved exactly. External fees, partial fills and market movement may produce drift.

## Delivery

One canonical skill and core; Codex/Claude plugin manifests and a generic skill installer for Cursor and compatible hosts. A compatible host must support native remote Binance MCP authorization, confirmations, local Python execution and file I/O. Plain chat-only clients without those capabilities are not claimed supported. Actual cross-host and authenticated trading verification must be reported separately from fixture tests.

# Architecture

Sharewell keeps conversation and Binance access in the AI host. The Python core receives captured MCP results as JSON, validates them, calculates portfolio state and proposals, and records approval and execution state in SQLite.

```text
Codex / Claude / Cursor / compatible host
        | native MCP calls and user confirmation
Official Binance Agentic MCP

AI host
        | finite JSON files
Sharewell core and SQLite journal
```

The core has no network transport, credential storage, dashboard, custom LLM, scheduler, futures, margin, withdrawal, or autonomous trading path. Thin adapters package the same skill and runtime for different hosts.

Financial inputs remain decimal strings inside Sharewell. Calculations use `Decimal` and `Fraction`. Binance's native `spot.newOrder` schema requires JSON numbers for price and quantity, so the provider converts only at the final MCP argument boundary and rejects a value unless conversion round-trips to the exact approved decimal.

The journal binds approval to a deterministic proposal hash, account, expiry, and exact order parameters. It commits a dispatch marker before returning a native call. Unknown submission outcomes are queried using the persisted client order ID and are never blindly retried.

Persistent account-scoped memory uses the official source, account ID, account
kind and Spot wallet. Mutable `can_trade` permission remains live safety state
and is excluded from policy, history, learning and default-path identity.

Final verification compares starting balances, authoritative order fills, commissions, and fresh ending balances. A matching placement response alone is not proof of a fill.

Evaluation is a generic registry layer above evidence and below learning. The
same journal stores evaluator inputs, hashes, parameters, versions, metrics and
evidence in `evaluation_runs`; learned aggregate preferences are separate.

Historical market data follows the same seam: the host discovers and calls the
official Agentic MCP `spot.klines` read, the Binance provider validates the
native twelve-column rows and evidence reference, and `core/historical_data.py`
resolves direct or inverse Spot pairs into daily close `price_history`. The
generic evaluator then calculates the requested runtime windows and metrics.
No historical data acquisition is embedded in portfolio, rebalance, approval or
execution modules.

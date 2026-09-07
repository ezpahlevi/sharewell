# Sharewell verification

Status: release candidate verified locally on 2026-09-07. Authenticated Binance Agentic reads work. Live trading remains unverified because the tested Agentic Spot sub-account contained no balances.

The repository now includes a Codex repository marketplace entry, host-native MCP
configuration, MIT licensing, and a minimal GitHub Actions workflow. CI is
deterministic and never connects to Binance.

## Authenticated Binance evidence

The configured Codex MCP connection used the official `https://agent.binance.com/mcp/agentic` endpoint and an existing OAuth session. After fixing DNS on the active Ethernet adapter, OAuth protected-resource metadata, Agentic catalog discovery, and authenticated read-only calls succeeded.

The live catalog exposed the Spot account, open-order, exchange-info, account-filter, execution-rule, reference-price, commission, ticker, order, and trade-history tools documented in [binance-mcp.md](binance-mcp.md). Read-only calls succeeded for account state, open orders, BTCUSDT metadata, filters, PRICE_RANGE data, reference-price calculation, account commission, best bid and ask, and the 24-hour ticker.

The account response identified an Agentic Spot account with trading permission. It contained zero nonzero balances and zero open orders. No order tool was invoked. No transaction, fill, receipt, or funded rebalance is claimed.

The live `spot.newOrder` schema was inspected without invoking it. Sharewell's exact binding accepts its flat `symbol`, `side`, `type`, `timeInForce`, `quantity`, `price`, and `newClientOrderId` fields. Decimal strings are converted to native JSON numbers only when the conversion round-trips exactly; lossy values fail with `LOSSY_NATIVE_NUMBER`.

The Codex marketplace smoke test used an isolated `CODEX_HOME`, added the local
repository marketplace, listed `sharewell@sharewell`, and installed it into the
isolated cache. The source entry points at the repository root, so the plugin is
not duplicated under a second directory.

## Local behavior

The test suite covers normalization of the observed Agentic account shape, portfolio valuation, stale and malformed evidence, concentration, target validation, route search, exact step and tick rounding, minimum and maximum filters, PRICE_RANGE feasibility, fee allowances, proposal approval, persistent client order IDs, duplicate dispatch prevention, partial fills, expiry, tampering, balance reconciliation, packaging, and installation from an unrelated directory.

PRICE_RANGE validation is a pre-dispatch feasibility check. Binance recalculates the reference when an order enters its taker phase, so a locally accepted order can still expire with `EXECUTION_RULE_PRICE_RANGE_EXCEEDED`.

The SQLite journal preserves proposal, approval, dispatch, receipt, fill, and balance evidence. An unresolved submission is queried by its persistent client order ID and is never blindly submitted again.

The journal also persists explicitly gated portfolio snapshots, generic
`evaluation_runs`, evaluator parameters and input hashes. Historical Market
Performance is a registry evaluator with runtime windows and metrics over
supplied validated price history only. Binance Agentic MCP Kline ingestion is
not implemented or verified. Verified execution outcomes may produce auditable
route-learning observations when a fresh initial quote touch is available, but
learning cannot bypass policy, approval or execution safety.

## Validation commands

Run from the plugin root:

```powershell
python -B -m unittest discover -s tests -q
python -B <plugin-validator> .
python -B <skill-validator> skills/sharewell
```

The OpenAI validators need PyYAML in their validation environment. Sharewell itself has no third-party runtime dependencies.

The release-candidate source completed 82 tests. The production-source
cleanliness check, reproducible ZIP check, self-contained install smoke test
and cwd-independent launcher test are part of that suite. No separate plugin
or canonical skill validator executable is present in this checkout.

## Limits

- No funded live order, partial fill, cancellation, or final balance reconciliation was possible with the empty Agentic account.
- Claude Code and Cursor executables were absent locally, so their native plugin loading was not run. Their adapters share the tested skill bundle.
- The planner selects the first locally valid loop-free route by hop count. It does not optimize liquidity or fees across every possible route.
- Fee allowances are conservative inputs. A live workflow must fetch the current account commission before approval and reconcile actual commissions afterward.
- The local skill and journal cannot protect a user from a malicious host that ignores the protocol.

No server, watcher, worker, order, transfer, or withdrawal was started for verification.

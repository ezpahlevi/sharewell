# Binance MCP integration

Use the official endpoint:

```text
https://agent.binance.com/mcp/agentic
```

Authentication is OAuth managed by the AI host. Sharewell never accepts or stores an API key, OAuth token, cookie, or client secret. Binance creates or selects a dedicated Agentic sub-account during authorization. The main account can be exposed read-only when the user grants that scope. External withdrawals are unavailable through this MCP.

## Codex connection

```powershell
codex mcp add binance-mcp-server --url https://agent.binance.com/mcp/agentic --oauth-client-id codex
```

Complete the Binance authorization page, then restart or reload the Codex MCP runtime. `codex mcp get binance-mcp-server --json` should show the exact endpoint. An authenticated runtime should expose `tool_search` and `tool_execute` when Binance uses META tool mode.

## Native tools verified on 2026-09-07

The authenticated Binance Agentic catalog exposed these required Spot tools:

| Purpose | Native tool |
| --- | --- |
| Account and balances | `spot.getAccount` |
| Open orders | `spot.getOpenOrders` |
| Symbol metadata | `spot.exchangeInfo` |
| Account and symbol filters | `spot.myFilters` |
| Execution rules | `spot.executionRules` |
| Reference price | `spot.referencePrice` |
| Reference-price method | `spot.referencePriceCalculation` |
| Best bid and ask | `spot.tickerBookTicker` |
| 24-hour ticker | `spot.ticker24hr` |
| Account commission | `spot.accountCommission` |
| New Spot order | `spot.newOrder` |
| Order lookup | `spot.getOrder` |
| Account fills | `spot.myTrades` |

Use `tool_search` with categories `account`, `general`, `market`, and `trade`. When a required tool is hidden, invoke `tool_execute` with its exact `toolName` and schema-matching `arguments`.

The observed `spot.getAccount` response supplies `uid`, `accountType`, `canTrade`, `balances`, and `permissions`. Normalize account identity from `/uid` and permission from `/canTrade`. Sharewell sets account kind to `AGENTIC` from the authenticated Agentic endpoint and wallet to `SPOT` from the Spot operation. It converts the numeric UID to a string before hashing or journaling.

The observed `spot.newOrder` schema uses flat fields. Bind `symbol`, `side`, `type`, `timeInForce`, `quantity`, `price`, and `newClientOrderId` to their same-named root fields. Sharewell supports only LIMIT IOC. Binance still presents its own confirmation before placement.

## PRICE_RANGE

`spot.executionRules` returns per-symbol PRICE_RANGE multipliers. `spot.referencePrice` returns the corresponding price and engine timestamp. Binance enforces this range when an order enters its taker phase and recalculates the reference at that moment.

Sharewell rejects a BUY limit below the observed lower bid boundary because no allowed execution is reachable. It rejects a SELL limit above the observed upper ask boundary for the same reason. Other limits can still expire if Binance recalculates the reference or encounters out-of-range liquidity. Record `expiryReason`; `EXECUTION_RULE_PRICE_RANGE_EXCEEDED` is a terminal expiry, not a successful trade.

If no PRICE_RANGE rule exists, no reference exists, the reference is null, or a directional multiplier is absent, Binance does not enforce that missing part. The host must preserve this evidence instead of inventing a reference.

## DNS troubleshooting

If `agent.binance.com` resolves to an ISP block page, compare the active resolver with a direct query to a public resolver. Change DNS only on the active network interface and retain the previous values for rollback. Re-run DNS resolution, TCP 443, OAuth metadata discovery, and an authenticated read-only call before changing Sharewell code.

The 2026-09-07 local validation found MyRepublic DNS mapping the endpoint to `block.myrepublic.co.id`. Switching the active Ethernet interface to Cloudflare DNS restored the official CloudFront address, OAuth metadata, catalog discovery, and read-only account calls.

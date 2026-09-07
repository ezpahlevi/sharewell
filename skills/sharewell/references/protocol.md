# Host protocol

All amounts and identifiers originating as Binance decimal values stay strings;
never pass through binary floats. Timestamps are integer Unix milliseconds.
Every snapshot must be fresh within 60 seconds. A host tool-call reference is a
non-secret identifier, not a credential or a made-up receipt.

## CLI input objects

| Operation | Required request fields |
| --- | --- |
| normalize | `source`, `numeraire`, `captures` as described below; no journal required |
| analyze | `snapshot` |
| propose | `snapshot`, `targets` (asset to percent string), `fee_allowance_bps`, `slippage_bps`; optional `ttl_ms` up to 300000 |
| approve | `proposal_hash`, exact `account` object, `approval_ref` from user message |
| dispatch | `proposal_hash`, fresh `snapshot`, authenticated native `catalog`, reviewed `binding` |
| record | `proposal_hash`, integer `index`, `receipt` |
| verify | `proposal_hash`, fresh `snapshot` |
| stop | `proposal_hash`, fresh `snapshot` |
| status | `proposal_hash` |
| policy-get | `account` |
| policy-set | `account`, `asset`, `policy`, `source_reference` |
| preference-get | `account`; optional `key` |
| preference-set | `account`, `key`, `value`, `source_reference` |
| snapshot | `snapshot`, `reason`, `live:true` |
| history | `account`; optional `limit` |
| memory-summary | `account` |

Output is `{ "ok": true, "result": ... }` on exit 0. Errors produce `ok:false`
and exit 1. The CLI does not invoke Binance. The host performs native MCP calls.
Snapshot history is auditable memory, not current Binance truth. Refresh live
evidence for every current analysis or execution decision.

## Normalize captured MCP results

Use `normalize` to convert captured native responses into the validated snapshot
format. Supply the official `source` endpoint, user-selected `numeraire`, and a
`captures` object with `account`, `balances`, `symbols`, `quotes`, `open_orders`.
Each capture contains `observed_at`, a real `evidence` call reference,
`complete:true` only after exhausting pagination, `pages` holding the native MCP
result envelopes, and `path` selecting the payload using JSON Pointer. Empty
path selects the whole payload; `/balances` selects its balances field. For a
capture containing multiple pages, use the earliest actual observation time.

Map account fields `id` and `can_trade` with a `fields` object of JSON pointers
into the selected `spot.getAccount` payload. For the verified native response,
use `/uid` and `/canTrade`. The provider converts the UID to a string and derives
`kind:AGENTIC` from the authenticated Agentic endpoint and `wallet:SPOT` from the
Spot account operation. Other captures may use standard
Binance row field names or explicit `fields` mappings per row. Optional captures
are `exchange_filters`, `asset_filters`, `execution_rules`,
`account_permissions` and `filter_references`. Row captures must select arrays,
including empty arrays; account/filter-reference captures select one object.

Both `structuredContent` and single JSON text-block envelopes are supported.
Raw text numeric decimals retain their exact decimal text. Already-rounded
structured floating-point amounts, duplicate keys, API errors, missing fields,
stale observations and incomplete pages are rejected. Normalization does not
make untrusted or invented evidence authentic.

## Native dispatch binding

The authenticated catalog verified these Spot tools on 2026-09-07:
`spot.getAccount`, `spot.getOpenOrders`, `spot.exchangeInfo`, `spot.myFilters`,
`spot.executionRules`, `spot.referencePrice`, `spot.referencePriceCalculation`,
`spot.tickerBookTicker`, `spot.ticker24hr`, `spot.accountCommission`,
`spot.newOrder`, `spot.getOrder`, and `spot.myTrades`.

Capture `catalog` from the connected official endpoint, with `source`,
`observed_at`, and its actual `tools` list. Each selected tool must retain its
real `name`, `description`, `inputSchema` and annotations. Catalog observations
expire after five minutes. Never substitute the synthetic schemas from tests.

The verified placement tool is `spot.newOrder`; rediscover it rather than assuming
the catalog is unchanged. The `binding` object has
`operation:"SPOT_LIMIT_ORDER"`, `tool` equal to the actual placement tool name,
and `fields` mapping each approved action field to
its native argument JSON pointer. The required action fields are `symbol`,
`side`, `type`, `timeInForce`, `quantity`, `price`, `newClientOrderId`. For a flat
schema, for example, the quantity pointer is `/quantity`; if the actual schema
nests it under `order`, it is `/order/quantity`. Read the tool description to
confirm semantics, not just compatible types. If the native schema requires an
explicit account identifier, set `account_field` to its argument pointer; the
provider supplies the approved account's ID. No arbitrary extra arguments or
credentials are accepted. Missing capabilities must be reported, not bypassed.

`dispatch` validates the exact action against the discovered schema before
persisting a dispatch marker. Its successful result contains `native_call` with
`tool` and `arguments`. The host invokes that exact native call once and follows
Binance's confirmation flow. Under Binance META tool mode, pass the target tool
and arguments through `tool_execute`. Do not rebuild or alter its arguments. An error
before marker creation allows correcting the mapping; an ambiguous outcome
after marker creation requires lookup by client ID, never a new submission.

The native schema requires JSON numbers for price and quantity. Sharewell keeps
the approved values as decimal strings, converts them only in `native_call`, and
rejects conversion unless the resulting JSON number round-trips to the exact
decimal. The schema checker rejects unsupported constraints and lossy numeric
conversion. Passing proves only that the supplied schema matches the arguments;
it does not prove Binance accepted the order.

## Snapshot

- `version`: integer 1.
- `source`: exact official Agentic MCP endpoint.
- `observed_at`: earliest observation time among collected balance/account data;
  do not refresh the timestamp merely by rewriting a file.
- `account`: `{id, kind, wallet, can_trade}`. ID is stable and non-secret; kind
  is `AGENTIC` or `MAIN_READ_ONLY`; wallet is `SPOT`; permission is Boolean.
- `numeraire`: the user's valuation asset, with no assumed stablecoin peg.
- `balances`: all `{asset, free, locked}` rows. `balances_complete:true` only
  after exhausting pagination.
- `symbols`: exchangeInfo symbol objects including `symbol`, `baseAsset`,
  `quoteAsset`, `status`, `isSpotTradingAllowed`, `orderTypes`, and `filters`.
- `quotes`: `{symbol, bidPrice, askPrice, observed_at}` rows covering pricing
  and proposed conversion routes. Preserve each quote's observation time.
- `open_orders`: complete Spot order rows including `symbol`, `side`, `origQty`.
  Set `open_orders_complete:true` only after exhausting pagination.
- `exchange_filters`: actual exchange-wide filters, if present.
- `asset_filters`: actual account `myFilters` results, including `MAX_ASSET`.
  An empty list means the account query returned no asset filters; do not assume
  absence without querying. Base-asset caps apply to quantity and quote-asset
  caps to order notional. The planner splits orders to respect these caps.
- `execution_rules`: `spot.executionRules` symbol rows. Capture PRICE_RANGE
  together with `spot.referencePrice`; Binance recalculates the range when the
  order enters its taker phase, so local validation cannot guarantee execution.
- `account_permissions`: actual account permission strings. Required when symbol
  `permissionSets` is nonempty. Every group must have at least one granted
  permission; a symbol being generally Spot-enabled is insufficient.
- `filter_references`: map of symbol to filter type to `{basis, price,
  observed_at}`. Basis is `REFERENCE_PRICE`, `WEIGHTED_AVERAGE` or `LAST_PRICE`.
  For the latter two, include matching `avgPriceMins` and
  `reference_price_absent:true` only after confirming no Binance reference price.
- `evidence`: nonempty list of actual host call references.

When timestamps differ, refresh data rather than forging a common timestamp.
Collect all relevant metadata; disconnected assets remain explicitly unpriced.

## Normalized receipt

Use authoritative order lookup and account trades, not a placement ACK alone.
Fields: `source`, exact `account`, `observed_at`, `evidence`, string `orderId`,
`clientOrderId`, `symbol`, `side`, `type`, `timeInForce`, `price`, `origQty`,
`executedQty`, `cummulativeQuoteQty`, `status`, `fills_complete:true`, `fills`.
The spelling `cummulativeQuoteQty` follows the Binance order field.

Each fill contains string `tradeId`, matching string `orderId`, matching `symbol`,
`qty`, `quoteQty`, `commission`, and `commissionAsset`. Exhaust trade pagination,
filter to the exact account/order/symbol, and retain each actual trade ID. The
journal checks aggregate quantities, quote totals and commissions against the
final balance change. Do not synthesize one fill from an order aggregate.

## Recovery

`status` returns persisted client IDs. Query these after any ambiguous outcome.
`stop` only closes a plan after all submissions are terminal and balances
reconcile. It does not cancel a Binance order. An unresolved submission must
remain unresolved until authoritative evidence permits reconciliation.

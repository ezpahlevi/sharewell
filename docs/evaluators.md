# Evaluators

Sharewell separates evidence, evaluation, learning, recommendation, proposal,
approval and execution. Evaluators are deterministic modules registered through
`core.evaluation`; the portfolio and rebalance engines do not contain
evaluator-specific branches.

Every evaluator declares an ID, version, scope, required inputs, default
parameters, parameter validation and an evaluation function. The framework
normalizes status, metrics, evidence references, optional score, warnings and
observations. Supported statuses are `PASS`, `FAIL`, `PARTIAL` and
`UNAVAILABLE`.

Profiles are declarative lists of registered evaluators with parameters and
optional weights. The framework can run a single evaluator or a profile. A
future fork can register another evaluator without changing portfolio,
rebalance or journal dispatch logic.

`evaluation_runs` stores the evaluator contract, parameters, input hash, raw
inputs, result status, metrics, evidence, score, warnings and observations in
the same SQLite journal. A proposal that uses evaluation-derived learning must
carry the relevant evaluator provenance in its immutable learning context.

The built-in Historical Market Performance evaluator accepts `price_history`
and runtime `windows_days`, `metrics` and `benchmark` parameters. Its defaults
are evaluator configuration, not Sharewell invariants. It evaluates only
supplied validated price history. The optional `PEERS` benchmark preserves the
original peer-average behavior; a named asset benchmark requires that asset's
history in the supplied inputs, and `PORTFOLIO` requires supplied
`benchmark_history` plus `benchmark_evidence`. Missing benchmark coverage is
`PARTIAL` or `UNAVAILABLE`, never a fabricated zero. It does not predict prices
or place orders.

The Binance provider accepts native Spot `spot.klines` captures from the
official Agentic MCP endpoint and preserves their host evidence reference.
`historical-inputs` normalizes the native rows, uses daily candle closes, and
builds provider-independent `price_history` for the requested assets and
numeraire. Historical day windows use UTC-aligned Binance Spot `1d` candles;
the host must send `timeZone:"0"`, and the normalized capture preserves
`time_zone:"0"`. `startTime` and `endTime` remain Unix milliseconds in UTC.
Custom Kline timezone evaluation is unsupported. The evaluator accepts supplied validated price history; Binance
Agentic MCP Kline ingestion is now implemented and live-read verified for the
native tool, but no background historical collection is performed.

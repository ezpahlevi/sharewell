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
and runtime `windows_days` and `metrics` parameters. Its defaults are
evaluator configuration, not Sharewell invariants. It evaluates only supplied
validated price history. Binance Agentic MCP Kline ingestion is not implemented
or verified, so Sharewell does not claim live historical Binance evaluation. It
does not predict prices or place orders.

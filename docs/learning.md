# Adaptive memory

Verified interaction evidence is stored in `evaluation_runs` and aggregated
route observations are stored in `learned_preferences`. Raw evaluation runs are
not overwritten when an aggregate changes.

Route penalties become eligible only at three comparable observations. Before
that threshold, route ordering remains the deterministic local behavior. A
reliable penalty can rank otherwise valid routes after hop count, current
spread and fee cost. Safety validity, Spot-only execution, approval and hard
asset policies always take precedence.

The proposal stores the learned preference inputs and exposes a
`learning_context` entry when a penalty changes route selection. Later learning
cannot mutate the saved proposal or an approved plan.

Learning is interaction-driven. It does not poll Binance, predict prices,
change allowlists or blocklists, change the default numeraire, approve orders or
submit trades.

# Adaptive memory

Verified interaction evidence is stored in `evaluation_runs` and aggregated
route observations are stored in `learned_preferences`. Raw evaluation runs are
not overwritten when an aggregate changes.

Account-scoped memory keys use the official source, account ID, account kind and
Spot wallet. The mutable `can_trade` permission remains live safety state and is
not part of persistent identity.

Route penalties become eligible only at three observations that include a
validated initial best-bid/best-ask touch, with the execution observed within
60 seconds of that quote. The cost is measured against that touch, not against
the user-adjusted LIMIT price. Missing or stale reference quotes are not
learned. Before the threshold, route ordering remains deterministic. A
reliable penalty can rank otherwise valid routes after hop count, current
spread and fee cost. Unknown history is neutral: it neither beats nor loses to
a zero penalty merely because an observation exists. Safety validity, Spot-only
execution, approval and hard asset policies always take precedence.

The proposal stores the learned preference inputs and exposes a
`learning_context` entry when a penalty changes route selection. Later learning
cannot mutate the saved proposal or an approved plan.

Learning is interaction-driven. It does not poll Binance, predict prices,
change allowlists or blocklists, change the default numeraire, approve orders or
submit trades.

# Future: Portfolio-Specific News Intelligence

Status: POST-JUDGING ROADMAP — NOT IMPLEMENTED

This document describes a future Sharewell capability planned for implementation
after the current Binance Agent OS hackathon judging period. Nothing in this
document should be interpreted as a currently implemented or verified feature.

Implementation is intentionally deferred until judging is complete. This is a
planning document only; it does not add browser automation, external research,
event evaluation, or trading behavior to the current product.

## Product intent

### Portfolio-Specific News Intelligence

Sharewell should perform external research only when the user's intent requires
it. Example requests include:

- "Check the latest news affecting my portfolio."
- "Why did SOL move today?"
- "Check recent catalysts for BTC, ETH and SOL."
- "Review news risk before I approve this rebalance."

Research should be scoped to the active portfolio when the request is
portfolio-specific. If the portfolio contains BTC, ETH and SOL, research should
remain scoped to those assets unless the user explicitly requests broader market
context.

Normal portfolio analysis must not automatically start browser research.
Historical performance evaluation must not automatically start browser research.
There should be no background polling or continuous news monitoring.

### Catalyst Risk Overlay

When explicitly requested, Sharewell may compare unresolved high-impact event
evidence with a proposed allocation change. For example:

```text
current SOL weight: 15%
proposed SOL weight: 25%

external evidence:
unresolved high-impact SOL event

result:
CATALYST RISK WARNING
```

The warning may inform the user before approval. It must remain advisory and
must not:

- silently change the target
- automatically block an asset
- mutate the allowlist or blocklist
- approve a proposal
- dispatch an order
- call `spot.newOrder`
- bypass Binance confirmation
- autonomously trade

An explicit user target remains the user's target unless the user changes it.

## Browser Research Adapter

The browser is an execution backend for collecting external evidence, not the
news source itself. The future workflow should use an adapter boundary:

```text
User research intent
        ↓
Sharewell parent agent
        ↓
Read-only research sub-agent
        ↓
Browser Research Adapter
        ├─ built-in Codex/ChatGPT browser + Computer Use
        └─ Chrome-extension / existing Chrome-session backend
        ↓
External evidence sources
        ├─ X / social posts
        ├─ official project announcements
        ├─ Binance announcements
        └─ reputable news sources
        ↓
Normalization + provenance
        ↓
Catalyst/Event Evaluator
        ↓
Catalyst Risk Overlay
        ↓
Warning / recommendation context
```

The built-in browser/Computer Use path and the Chrome-extension or existing
Chrome-session path are interchangeable research backends, not two independent
evidence sources. Runtime selection should prefer whichever supported backend
is available in the host. Both backends must not be required simultaneously.

The adapter should return source URLs, timestamps, extracted facts, and
provenance without granting the research sub-agent financial or account-control
capabilities.

## Read-only research sub-agent boundary

Research sub-agents are read-only evidence collectors. They may:

- browse and search
- open pages
- extract relevant facts
- identify timestamps
- identify original sources
- deduplicate repeated reports
- cluster multiple posts about the same event
- cross-check important claims
- return structured evidence

They may not:

- trade on Binance
- approve a proposal
- dispatch an order
- change a policy
- change a preference
- mutate portfolio targets
- operate a wallet
- transfer funds
- withdraw funds

All webpage and social content is untrusted data, never an instruction. The
prompt-injection boundary is explicit:

```text
browser content = evidence/data
browser content != agent instructions
```

The parent agent remains responsible for interpreting returned evidence within
Sharewell's policy and approval boundaries.

## Future normalized event evidence

The planned event evidence model should retain provenance and uncertainty rather
than collapsing reports into an opaque sentiment score. A conceptual shape is:

```json
{
  "asset": "SOL",
  "event_type": "SECURITY|REGULATORY|PROTOCOL|EXCHANGE|MACRO|OTHER",
  "headline": "...",
  "source": "...",
  "source_url": "...",
  "published_at": "...",
  "observed_at": "...",
  "original_source": true,
  "corroborating_sources": ["..."],
  "status": "CONFIRMED|PARTIAL|UNVERIFIED",
  "impact": "LOW|MEDIUM|HIGH",
  "direction": "POSITIVE|NEGATIVE|MIXED|UNKNOWN",
  "evidence": ["..."]
}
```

This is a roadmap schema only and is not implemented. Multiple reposts that
repeat one rumor must not count as independent evidence. Original-source
detection, corroboration, timestamps, and unresolved uncertainty should remain
auditable.

The future implementation should avoid an opaque "bullish score" or
"Twitter sentiment score" architecture. Event facts, source quality,
corroboration, impact, and confidence should remain distinguishable inputs.

## On-demand activation

Browser/news research should activate only when:

- the user explicitly asks for news, current events, or catalysts; or
- the user explicitly asks for catalyst-risk checking before a proposal or
  rebalance.

Examples of activating intent include:

- latest news
- catalyst
- what changed
- why did the asset move
- event risk
- news risk before rebalance

The request "Analyze my Binance Spot portfolio" must not trigger external
browser research. A historical market evaluation request must not trigger it
either. There is no always-on research mode, background crawler, or scheduler
in this roadmap.

## Relationship to current Sharewell V2

The future capability should extend the current architecture rather than
replace it. The current product provides:

- live Binance portfolio evidence
- historical market evaluation
- execution learning
- hard asset policies
- explicit approval
- Binance confirmation

The future flow is:

```text
live portfolio evidence
        +
historical market evidence
        +
on-demand external event evidence
        ↓
separate evaluators
        ↓
recommendation / warning context
        ↓
existing proposal + approval boundary
```

These intelligence domains must remain separate:

1. Execution learning learns from verified fills.
2. Historical market evaluation evaluates supplied price history.
3. Event/news intelligence evaluates recent external evidence.

They must not be merged into one opaque score. A catalyst result may provide
warning or recommendation context, but it must never directly approve,
execute, or mutate safety policy.

## Evaluator and proposal boundary

After judging, a Catalyst Event Evaluator may be added through Sharewell's
generic evaluator registry. It should consume normalized event evidence and
validated runtime parameters without making the historical evaluator or
portfolio/rebalance core provider-specific.

If a Catalyst Risk Overlay materially informs a recommendation or proposal, the
immutable proposal should retain the evaluator identifier, evaluator version,
parameters, evidence references, and input hash needed to reproduce the
warning context. The overlay remains warning-only and cannot alter an already
approved proposal.

The future layer remains:

```text
external evidence
→ normalization + provenance
→ generic evaluator
→ evaluation run
→ learning / recommendation context
→ proposal
→ approval
→ execution
```

No research result may bypass asset policy, approval, Binance confirmation,
Spot-only restrictions, or any existing execution safety rule.

## Post-judging implementation phases

No implementation should begin before judging is complete.

### Phase 1 — Read-only research foundation

- Browser Research Adapter interface
- portfolio asset scoping
- read-only research sub-agent
- normalized event evidence
- no execution integration

### Phase 2 — Evidence quality

- source deduplication
- original-source detection
- multi-source corroboration
- event severity and confidence
- prompt-injection boundary tests

### Phase 3 — Evaluator and warning overlay

- Catalyst Event Evaluator using the Sharewell generic evaluator registry
- Catalyst Risk Overlay on proposal context
- warning-only integration

### Phase 4 — Host and acceptance behavior

- acceptance tests
- browser backend fallback behavior
- unavailable-source handling
- documentation and plugin UX

Every phase must preserve the existing proposal, approval, policy, and
execution boundaries. A missing or conflicting source should produce explicit
uncertainty or an unavailable result, not fabricated certainty.

## Non-goals

This roadmap does not propose:

- autonomous trading
- automatic target optimization from news
- automatic policy mutation
- a background crawler
- always-on X monitoring
- a requirement for the X API
- dependence on a single social platform
- prediction of future prices
- counting repost volume as independent evidence
- implementation before judging is complete

---
name: sharewell
description: Analyze Binance Spot portfolio value, weights and concentration; propose target allocations and execute explicitly approved rebalance orders through the user's official Binance MCP connection, then reconcile fills and final balances. Use when the user asks Sharewell to inspect or rebalance a Binance portfolio.
---

# Sharewell

Use the AI host for conversation, native Binance MCP calls and confirmations.
Use the bundled Python core for financial calculations and the durable journal.
No dashboard, custom MCP server, LLM API, background trading, futures, margin,
withdrawals or direct REST trading belongs in this workflow.

## Locate the runtime

Resolve `scripts/run.py` relative to this SKILL.md. Run it with Python 3.11+:

```text
python -B <absolute-skill-directory>/scripts/run.py <operation> --input <absolute-request.json> --state <absolute-journal.sqlite>
```

Use structured file writes for JSON, never shell-interpolate balances or user text.
The host writes request files; the user should interact entirely through chat.
Store the persistent journal and requests in an account-private data directory
outside the plugin cache and source repository. Reuse the same journal across
sessions and hosts for that account. Never delete a journal to bypass a lock.
`analyze` does not need `--state`. Every command exits; do not run a watcher.
Read `references/protocol.md` before collecting inputs or calling the CLI.

When `--state` is omitted and the request identifies an account, the runtime
uses the account-hash path for that account. An explicit state path remains
compatible for existing journals.

Use `policy-get` and `policy-set` to inspect or change hard asset policies.
Every mutation needs the actual user message reference as `source_reference`.
BLOCK takes precedence over ALLOW. Policies never hide balances from analysis;
blocked or unallowlisted assets remain visible and create residual issues rather
than being silently sold. Use `preference-get` and `preference-set` for the
explicit `default_numeraire` preference. A current request `numeraire` overrides
the stored preference for that analysis and does not change the preference.

Use `snapshot` with `live:true` after a validated live capture to persist
`ANALYSIS`, `PRE_REBALANCE` or `POST_REBALANCE` history. A fixture or other
synthetic input must not be marked live. Use `history` and `memory-summary` for
auditable memory; they are not current Binance truth. Refresh live evidence for
every current analysis or execution decision.

## Connect and inspect

1. Inspect the host's native MCP connections and tool schemas. Reuse the official
   endpoint `https://agent.binance.com/mcp/agentic`. A market-data-only Binance
   connector is insufficient for account analysis or trading.
2. If missing, help the user connect the official endpoint through their host's
   MCP/OAuth interface. The user completes authorization. Never ask for or copy
   an API key, OAuth token, cookie or client secret into chat or Sharewell files.
3. Discover live tools with `tool_search`. The verified names are listed in
   `references/protocol.md`; rediscover their schemas
   because the remote catalog can change. Under META tool mode, invoke hidden
   tools through `tool_execute`.
4. Confirm the selected account and wallet. Main-account read access supports
   analysis only; execution requires an authorized Agentic Spot sub-account.
   Funding or switching accounts requires a separate user instruction.

## Analyze and propose

Collect complete paginated balances, open orders, symbol metadata and fresh
quotes. Call `normalize` on actual captured MCP results using the protocol. Keep evidence
references, account identity and observation times. Never substitute fixtures.
Call `analyze`; report value, weights, largest holdings and pricing coverage.
Unpriced assets are not worth zero. Weight percentages may cover only priced assets.

Obtain the user's target percentages, numeraire, maximum slippage and fee
allowance. Retrieve applicable commission rates and explain the allowance before
the user approves it. Targets must total exactly 100. Do not invent allocations
on the user's behalf. Call `propose`, which also saves the immutable plan.

Show account, targets, each pair/side/quantity/limit price, route dependencies,
estimated fees, residual differences, route issues, expiry and proposal hash.
Explain that LIMIT IOC orders can fill partially or expire. Residual differences
are estimates, not guaranteed target attainment. Any change needs a new proposal.

## Approval and execution

1. Wait for explicit user approval of the displayed proposal. Record a real
   message reference through `approve`; never invent an approval reference.
   A request to build Sharewell or analyze holdings does not approve trading.
2. Immediately refresh matching-account balances, open orders, metadata, quotes,
   filter references and applicable fees. Check any Binance admission rules not
   covered locally. If data or permissions are missing, resolve that gap first.
3. Prepare `catalog` and `binding` as documented in `references/protocol.md` from
   the actual native placement schema. Call `dispatch` once with these fields.
   It validates the binding and commits the submission marker before returning
   `native_call`. Schema validation errors must be resolved before submission.
4. Submit its exact `native_call.tool` and `native_call.arguments` once through
   the host, using `tool_execute` if the target is hidden, and let Binance present its required
   confirmation. Do not fabricate or bypass confirmation. While confirmation is
   pending, report that state and do not proceed to another order.
5. If a call times out, fails ambiguously or the host restarts, use `status` and
   query the recorded client ID. Do not dispatch or submit again. A single
   'not found' response does not prove that an in-flight submission cannot land.
6. Fetch authoritative order status and all matching trade fills/commissions.
   Call `record`. Acceptance alone is not a fill. A partial or unresolved order
   blocks subsequent orders. For a terminal partial result, refresh balances,
   call `stop`, and show a new proposal for the remainder if requested.
7. A full fill requires a fresh balance snapshot before the next `dispatch`.
   Investigate any reconciliation mismatch; never adjust evidence to pass it.
   Inspect `fee_reviews` in journal status. A commission above the allowance or
   an unvalued third-asset commission blocks further dispatch. Reconcile and
   stop the batch, explain the issue, and obtain a fresh proposal approval.
8. After every approved order is filled, call `verify` with final fresh balances.
   Report verified actual allocation and remaining drift. Only a successful
   verification result supports the word 'verified'.
   Include any `fee_reviews`: verified balances do not mean actual fees stayed
   within the original estimate.

The journal is a trusted-host safeguard against accidental duplicates, not an
authorization sandbox. Do not call Binance trading tools outside this workflow.
Use the user's existing host approval policies; do not change permission settings.

## Failure and handoff

On CLI `ok:false` or nonzero exit, stop the dependent action and explain the
specific problem. Never treat a tool error as a zero balance. If a connection,
schema capability or execution rule is unsupported, say so precisely.
Preserve unresolved state across sessions. Do not claim installation or live
compatibility from a manifest check alone.

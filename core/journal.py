import json
import sqlite3
from contextlib import contextmanager
from decimal import Decimal
from fractions import Fraction

from .filters import validate_limit
from .evaluation import run_evaluator, run_profile
from .policies import account_key, normalize
from .portfolio import analyze, target_differences
from .rebalance import propose
from .schemas import (ENDPOINT, ZERO, asset, canonical, decimal, digest, fresh, integer,
                      now_ms, require, validate_snapshot)


SNAPSHOT_REASONS = {"ANALYSIS", "PRE_REBALANCE", "POST_REBALANCE"}


def reference(value: object) -> str:
    require(isinstance(value, str) and 0 < len(value) <= 200, "INVALID_EVIDENCE")
    return value


def fee_reviews(plan: dict, orders) -> list[dict]:
    reviews = []
    allowance = Fraction(decimal(plan["fee_allowance_bps"])) / 10_000
    for order in orders:
        if order["receipt"] is None:
            continue
        receipt = json.loads(order["receipt"])
        planned = plan["orders"][order["idx"]]
        base = planned["destination_asset"] if planned["side"] == "BUY" else planned["source_asset"]
        quote = planned["source_asset"] if planned["side"] == "BUY" else planned["destination_asset"]
        for fill in receipt["fills"]:
            commission = Fraction(decimal(fill["commission"]))
            if commission == 0:
                continue
            denominator = (fill["qty"] if fill["commissionAsset"] == base else
                           fill["quoteQty"] if fill["commissionAsset"] == quote else None)
            if denominator is None:
                reason = "THIRD_ASSET_FEE"
            elif commission <= Fraction(decimal(denominator)) * allowance:
                continue
            else:
                reason = "FEE_ALLOWANCE_EXCEEDED"
            reviews.append({"index": order["idx"], "tradeId": fill["tradeId"],
                            "commission": fill["commission"], "asset": fill["commissionAsset"], "reason": reason})
    return reviews


class Journal:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS proposals (
                hash TEXT PRIMARY KEY, account TEXT NOT NULL, proposal TEXT NOT NULL,
                snapshot TEXT NOT NULL, state TEXT NOT NULL, approval TEXT);
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_account ON proposals(account)
                WHERE state = 'APPROVED';
            CREATE TABLE IF NOT EXISTS orders (
                proposal TEXT NOT NULL REFERENCES proposals(hash), idx INTEGER NOT NULL,
                client_id TEXT NOT NULL UNIQUE, dispatched_at INTEGER NOT NULL,
                state TEXT NOT NULL, receipt TEXT, PRIMARY KEY(proposal, idx));
            CREATE TABLE IF NOT EXISTS asset_policies (
                account TEXT NOT NULL, asset TEXT NOT NULL, policy TEXT NOT NULL,
                created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL,
                source_reference TEXT NOT NULL, PRIMARY KEY(account, asset));
            CREATE TABLE IF NOT EXISTS user_preferences (
                account TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL,
                updated_at INTEGER NOT NULL, source_reference TEXT NOT NULL,
                PRIMARY KEY(account, key));
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                snapshot_hash TEXT PRIMARY KEY, account TEXT NOT NULL, observed_at INTEGER NOT NULL,
                numeraire TEXT NOT NULL, reason TEXT NOT NULL, snapshot TEXT NOT NULL,
                portfolio TEXT NOT NULL, portfolio_value TEXT, weights TEXT NOT NULL,
                concentration TEXT NOT NULL, coverage TEXT NOT NULL, evidence TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS evaluation_runs (
                run_id TEXT PRIMARY KEY, account TEXT NOT NULL, evaluator_id TEXT NOT NULL,
                evaluator_version INTEGER NOT NULL, scope TEXT NOT NULL, parameters TEXT NOT NULL,
                input_hash TEXT NOT NULL, inputs TEXT NOT NULL, status TEXT NOT NULL,
                metrics TEXT NOT NULL, evidence TEXT NOT NULL, score TEXT,
                warnings TEXT NOT NULL, observations TEXT NOT NULL, created_at INTEGER NOT NULL);
        """)

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _row(self, proposal_hash: str):
        row = self.db.execute("SELECT * FROM proposals WHERE hash=?", (proposal_hash,)).fetchone()
        require(row is not None, "UNKNOWN_PROPOSAL")
        return row

    def _policy_map(self, account: dict) -> dict[str, str]:
        key = account_key(account)
        rows = self.db.execute("SELECT asset, policy FROM asset_policies WHERE account=? ORDER BY asset", (key,)).fetchall()
        return normalize({row["asset"]: row["policy"] for row in rows})

    def policy_get(self, account: dict) -> dict:
        key = account_key(account)
        rows = self.db.execute("SELECT asset, policy, created_at, updated_at, source_reference FROM asset_policies WHERE account=? ORDER BY asset", (key,)).fetchall()
        return {"account": account, "policies": [dict(row) for row in rows]}

    def policy_set(self, account: dict, name: str, policy: str, source_reference: str, *, now=None) -> dict:
        now = now_ms() if now is None else now
        account_ref = account_key(account)
        asset(name)
        require(policy in {"ALLOW", "BLOCK", "REMOVE"}, "INVALID_POLICY")
        reference(source_reference)
        with self.transaction():
            if policy == "REMOVE":
                self.db.execute("DELETE FROM asset_policies " + "WHERE account=? AND asset=?", (account_ref, name))
            else:
                existing = self.db.execute("SELECT created_at FROM asset_policies WHERE account=? AND asset=?",
                                           (account_ref, name)).fetchone()
                created = existing["created_at"] if existing else now
                self.db.execute("INSERT OR REPLACE INTO asset_policies VALUES (?, ?, ?, ?, ?, ?)",
                                (account_ref, name, policy, created, now, source_reference))
        return self.policy_get(account)

    def preference_get(self, account: dict, key: str | None = None) -> dict:
        account_ref = account_key(account)
        if key is None:
            rows = self.db.execute("SELECT key, value, updated_at, source_reference FROM user_preferences WHERE account=? ORDER BY key",
                                   (account_ref,)).fetchall()
        else:
            require(key == "default_numeraire", "INVALID_PREFERENCE")
            rows = self.db.execute("SELECT key, value, updated_at, source_reference FROM user_preferences WHERE account=? AND key=?",
                                   (account_ref, key)).fetchall()
        return {"account": account, "preferences": [dict(row) for row in rows]}

    def default_numeraire(self, account: dict):
        rows = self.preference_get(account, "default_numeraire")["preferences"]
        return rows[0]["value"] if rows else None

    def preference_set(self, account: dict, key: str, value: str, source_reference: str, *, now=None) -> dict:
        now = now_ms() if now is None else now
        account_ref = account_key(account)
        require(key == "default_numeraire", "INVALID_PREFERENCE")
        asset(value)
        reference(source_reference)
        with self.transaction():
            self.db.execute("INSERT OR REPLACE INTO user_preferences VALUES (?, ?, ?, ?, ?)",
                            (account_ref, key, value, now, source_reference))
        return self.preference_get(account, key)

    def save_snapshot(self, snapshot: dict, reason: str, *, live=False, now=None) -> dict:
        now = now_ms() if now is None else now
        require(type(live) is bool and live, "LIVE_SNAPSHOT_REQUIRED")
        require(reason in SNAPSHOT_REASONS, "INVALID_SNAPSHOT_REASON")
        validate_snapshot(snapshot, now)
        report = analyze(snapshot, now)
        snapshot_hash = digest({"reason": reason, "snapshot": snapshot})
        weights = {row["asset"]: row["weight_pct"] for row in report["assets"]}
        with self.transaction():
            self.db.execute("INSERT OR IGNORE INTO portfolio_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (snapshot_hash, canonical(snapshot["account"]), snapshot["observed_at"],
                             snapshot["numeraire"], reason, canonical(snapshot), canonical(report),
                             report["total_value"], canonical(weights), canonical(report["concentration"]),
                             report["coverage"], canonical(report["evidence"])))
        return self._snapshot_row(snapshot_hash)

    def _snapshot_row(self, snapshot_hash: str) -> dict:
        row = self.db.execute("SELECT * FROM portfolio_snapshots WHERE snapshot_hash=?", (snapshot_hash,)).fetchone()
        require(row is not None, "SNAPSHOT_NOT_FOUND")
        result = dict(row)
        for key in ("snapshot", "portfolio", "weights", "concentration", "evidence"):
            result[key] = json.loads(result[key])
        return result

    def history(self, account: dict, limit: int = 50) -> dict:
        account_ref = account_key(account)
        require(type(limit) is int and 0 < limit <= 1000, "INVALID_HISTORY_LIMIT")
        rows = self.db.execute("SELECT * FROM portfolio_snapshots WHERE account=? ORDER BY observed_at DESC, snapshot_hash DESC LIMIT ?",
                               (account_ref, limit)).fetchall()
        return {"account": account, "history": [self._snapshot_row(row["snapshot_hash"]) for row in rows],
                "current_truth": "LIVE_INPUT_REQUIRED"}

    def memory_summary(self, account: dict) -> dict:
        history = self.history(account, 1)["history"]
        return {"account": account, "policies": self.policy_get(account)["policies"],
                "preferences": self.preference_get(account)["preferences"],
                "latest_snapshot": history[0] if history else None,
                "current_truth": "LIVE_INPUT_REQUIRED"}

    def _save_evaluation(self, account: dict, result: dict, inputs: dict, created_at: int) -> dict:
        run_id = digest({"account": account, "evaluator_id": result["evaluator_id"],
                         "version": result["version"], "parameters": result["parameters"],
                         "input_hash": result["input_hash"]})
        self.db.execute("INSERT OR IGNORE INTO evaluation_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (run_id, account_key(account), result["evaluator_id"], result["version"],
                         result["scope"], canonical(result["parameters"]), result["input_hash"],
                         canonical(inputs), result["status"], canonical(result["metrics"]),
                         canonical(result["evidence"]), result["score"], canonical(result["warnings"]),
                         canonical(result["observations"]), created_at))
        return self.evaluation_row(run_id)

    def evaluation_row(self, run_id: str) -> dict:
        row = self.db.execute("SELECT * FROM evaluation_runs WHERE run_id=?", (run_id,)).fetchone()
        require(row is not None, "EVALUATION_NOT_FOUND")
        result = dict(row)
        for key in ("parameters", "inputs", "metrics", "evidence", "warnings", "observations"):
            result[key] = json.loads(result[key])
        return result

    def evaluate(self, account: dict, inputs: dict, *, evaluator_id: str | None = None,
                 parameters: dict | None = None, profile: str | None = None, now=None) -> dict:
        now = now_ms() if now is None else now
        require((evaluator_id is None) != (profile is None), "EVALUATION_SELECTOR_REQUIRED")
        if profile is not None:
            result = run_profile(profile, inputs, parameters)
            results = result["results"]
        else:
            result = run_evaluator(evaluator_id, inputs, parameters)
            results = [result]
        with self.transaction():
            runs = [self._save_evaluation(account, item, inputs, now) for item in results]
        return {"result": result, "runs": runs}

    def _validate_policy_lock(self, plan: dict, snapshot: dict) -> None:
        generated = propose(snapshot, plan["targets"],
                            fee_allowance_bps=plan["fee_allowance_bps"],
                            slippage_bps=plan["slippage_bps"], now=plan["created_at"],
                            ttl_ms=plan["expires_at"] - plan["created_at"],
                            policies=self._policy_map(plan["account"]))
        require(generated == plan, "POLICY_CHANGED")

    def save(self, proposal: dict, snapshot: dict) -> str:
        generated = propose(snapshot, proposal["targets"],
                            fee_allowance_bps=proposal["fee_allowance_bps"],
                            slippage_bps=proposal["slippage_bps"], now=proposal["created_at"],
                            ttl_ms=proposal["expires_at"] - proposal["created_at"],
                            policies=proposal.get("policy_context"))
        require(generated == proposal, "PROPOSAL_MISMATCH")
        with self.transaction():
            self.db.execute("INSERT OR IGNORE INTO proposals VALUES (?, ?, ?, ?, 'PROPOSED', NULL)",
                            (proposal["hash"], canonical(proposal["account"]), canonical(proposal), canonical(snapshot)))
        return proposal["hash"]

    def approve(self, proposal_hash: str, account: dict, approval_ref: str, *, now=None):
        now = now_ms() if now is None else now
        reference(approval_ref)
        with self.transaction():
            row = self._row(proposal_hash)
            plan = json.loads(row["proposal"])
            require(row["state"] == "PROPOSED", "INVALID_APPROVAL_STATE")
            require(plan["account"] == account, "APPROVAL_ACCOUNT_MISMATCH")
            self._validate_policy_lock(plan, json.loads(row["snapshot"]))
            require(plan["created_at"] <= now < plan["expires_at"], "PROPOSAL_EXPIRED")
            require(plan["execution_eligible"] and bool(plan["orders"]), "NO_EXECUTABLE_ORDERS")
            active = self.db.execute("SELECT hash FROM proposals WHERE account=? AND state='APPROVED'", (row["account"],)).fetchone()
            require(active is None, "ACCOUNT_LOCKED")
            self.db.execute("UPDATE proposals SET state='APPROVED', approval=? WHERE hash=?",
                            (canonical({"reference": approval_ref, "approved_at": now}), proposal_hash))

    def dispatch(self, proposal_hash: str, snapshot: dict, *, now=None, prepare=None) -> dict:
        now = now_ms() if now is None else now
        validate_snapshot(snapshot, now)
        with self.transaction():
            row = self._row(proposal_hash)
            plan = json.loads(row["proposal"])
            require(row["state"] == "APPROVED", "APPROVAL_REQUIRED")
            require(plan["created_at"] <= now < plan["expires_at"], "PROPOSAL_EXPIRED")
            require(snapshot["account"] == plan["account"], "ACCOUNT_CHANGED")
            self._validate_policy_lock(plan, json.loads(row["snapshot"]))
            previous = self.db.execute("SELECT * FROM orders WHERE proposal=? ORDER BY idx", (proposal_hash,)).fetchall()
            require(all(order["state"] == "FILLED" for order in previous),
                    "ORDER_UNRESOLVED")
            require(not fee_reviews(plan, previous),
                    "FEE_REVIEW_REQUIRED")
            index = len(previous)
            require(index < len(plan["orders"]), "ALL_ORDERS_DISPATCHED")
            require(snapshot["observed_at"] >= (previous[-1]["dispatched_at"] if previous else plan["created_at"]),
                    "STALE_POST_TRADE_BALANCE")
            self._reconcile(plan, json.loads(row["snapshot"]), previous, snapshot)
            order = plan["orders"][index]
            symbol = next((s for s in snapshot["symbols"] if s["symbol"] == order["symbol"]), None)
            require(symbol is not None, "SYMBOL_UNAVAILABLE")
            validate_limit(symbol, order["side"], decimal(order["quantity"]), decimal(order["price"]), snapshot, now)
            available = next((decimal(b["free"]) for b in snapshot["balances"] if b["asset"] == order["source_asset"]), ZERO)
            require(available >= decimal(order["source_reserve"]), "INSUFFICIENT_FREE_BALANCE")
            client_id = "sw" + proposal_hash[:24] + f"{index:04d}"
            action = {key: order[key] for key in ("symbol", "side", "type", "timeInForce", "quantity", "price")}
            action["newClientOrderId"] = client_id
            native_call = prepare(action, plan["account"], now) if prepare else None
            self.db.execute("INSERT INTO orders VALUES (?, ?, ?, ?, 'DISPATCHED', NULL)",
                            (proposal_hash, index, client_id, now))
        return {"account": plan["account"], "proposal_hash": proposal_hash, "index": index,
                "action": action, "native_call": native_call,
                "action_code": "SUBMIT_ONCE_THEN_QUERY"}

    def record(self, proposal_hash: str, index: int, receipt: dict, *, now=None):
        now = now_ms() if now is None else now
        integer(index, "index")
        fresh(receipt.get("observed_at"), now)
        reference(receipt.get("evidence"))
        require(receipt.get("source") == ENDPOINT, "INVALID_SOURCE")
        require(isinstance(receipt.get("orderId"), str) and bool(receipt["orderId"]), "INVALID_ORDER_ID")
        with self.transaction():
            row = self._row(proposal_hash)
            plan = json.loads(row["proposal"])
            sent = self.db.execute("SELECT * FROM orders WHERE proposal=? AND idx=?", (proposal_hash, index)).fetchone()
            require(sent is not None, "DISPATCH_NOT_FOUND")
            expected = plan["orders"][index]
            require(receipt.get("account") == plan["account"], "RECEIPT_ACCOUNT_MISMATCH")
            require(receipt.get("clientOrderId") == sent["client_id"], "CLIENT_ORDER_ID_MISMATCH")
            require(receipt["observed_at"] >= sent["dispatched_at"], "RECEIPT_BEFORE_DISPATCH")
            for key in ("symbol", "side", "type", "timeInForce"):
                require(receipt.get(key) == expected[key], "RECEIPT_FIELD_MISMATCH")
            require(decimal(receipt.get("origQty")) == decimal(expected["quantity"])
                    and decimal(receipt.get("price")) == decimal(expected["price"]), "RECEIPT_AMOUNT_MISMATCH")
            status = receipt.get("status")
            require(status in {"NEW", "PARTIALLY_FILLED", "FILLED", "CANCELED", "REJECTED", "EXPIRED", "EXPIRED_IN_MATCH", "PENDING_CANCEL"}, "INVALID_ORDER_STATUS")
            executed = decimal(receipt.get("executedQty"))
            quote = decimal(receipt.get("cummulativeQuoteQty"))
            require(executed <= decimal(expected["quantity"]), "EXECUTED_QTY_EXCEEDED")
            require(status != "FILLED" or executed == decimal(expected["quantity"]), "INCOMPLETE_FILLED_STATUS")
            require(receipt.get("fills_complete") is True and isinstance(receipt.get("fills"), list), "INCOMPLETE_FILLS")
            base_sum, quote_sum, seen = ZERO, ZERO, set()
            for fill in receipt["fills"]:
                require(fill.get("orderId") == receipt["orderId"] and fill.get("symbol") == expected["symbol"],
                        "FILL_ORDER_MISMATCH")
                trade_id = str(fill.get("tradeId"))
                require(trade_id not in seen and trade_id != "None", "INVALID_TRADE_ID")
                seen.add(trade_id)
                quantity, fill_quote = decimal(fill.get("qty")), decimal(fill.get("quoteQty"))
                require(quantity > ZERO and fill_quote > ZERO, "INVALID_FILL_AMOUNT")
                require(fill_quote <= quantity * decimal(expected["price"]) if expected["side"] == "BUY"
                        else fill_quote >= quantity * decimal(expected["price"]), "FILL_PRICE_VIOLATION")
                decimal(fill.get("commission"))
                asset(fill.get("commissionAsset"))
                base_sum += quantity
                quote_sum += fill_quote
            require(base_sum == executed and quote_sum == quote, "FILL_TOTAL_MISMATCH")
            if sent["receipt"]:
                old = json.loads(sent["receipt"])
                require(receipt["orderId"] == old["orderId"], "ORDER_ID_CHANGED")
                require(receipt["observed_at"] >= old["observed_at"] and executed >= decimal(old["executedQty"]), "RECEIPT_REGRESSED")
                new_fills = {str(fill["tradeId"]): fill for fill in receipt["fills"]}
                require(all(new_fills.get(str(fill["tradeId"])) == fill for fill in old["fills"]),
                        "FILL_HISTORY_CHANGED")
                if sent["state"] in {"FILLED", "CANCELED", "REJECTED", "EXPIRED", "EXPIRED_IN_MATCH"}:
                    require(status == sent["state"] and receipt["fills"] == old["fills"], "TERMINAL_RECEIPT_CHANGED")
            self.db.execute("UPDATE orders SET state=?, receipt=? WHERE proposal=? AND idx=?", (status, canonical(receipt), proposal_hash, index))

    def _reconcile(self, plan: dict, initial: dict, orders, snapshot: dict):
        expected = {b["asset"]: decimal(b["free"]) + decimal(b["locked"]) for b in initial["balances"]}
        symbols = {s["symbol"]: s for s in initial["symbols"]}
        for order in orders:
            require(order["receipt"] is not None, "MISSING_ORDER_RECEIPT")
            receipt = json.loads(order["receipt"])
            require(snapshot["observed_at"] >= receipt["observed_at"], "BALANCE_BEFORE_RECEIPT")
            symbol = symbols[receipt["symbol"]]
            sign = Decimal(1) if receipt["side"] == "BUY" else Decimal(-1)
            base, quote = symbol["baseAsset"], symbol["quoteAsset"]
            expected[base] = expected.get(base, ZERO) + sign * decimal(receipt["executedQty"])
            expected[quote] = expected.get(quote, ZERO) - sign * decimal(receipt["cummulativeQuoteQty"])
            for fill in receipt["fills"]:
                name = fill["commissionAsset"]
                expected[name] = expected.get(name, ZERO) - decimal(fill["commission"])
        actual = {b["asset"]: decimal(b["free"]) + decimal(b["locked"]) for b in snapshot["balances"]}
        require(all(expected.get(name, ZERO) == actual.get(name, ZERO) for name in set(expected) | set(actual)),
                "BALANCE_RECONCILIATION_FAILED")

    def verify(self, proposal_hash: str, snapshot: dict, *, now=None) -> dict:
        now = now_ms() if now is None else now
        report = analyze(snapshot, now)
        with self.transaction():
            row = self._row(proposal_hash)
            plan = json.loads(row["proposal"])
            require(row["state"] in {"APPROVED", "VERIFIED"}, "APPROVAL_REQUIRED")
            require(snapshot["account"] == plan["account"], "FINAL_ACCOUNT_MISMATCH")
            orders = self.db.execute("SELECT * FROM orders WHERE proposal=? ORDER BY idx", (proposal_hash,)).fetchall()
            require(len(orders) == len(plan["orders"]) and all(o["state"] == "FILLED" for o in orders), "EXECUTION_INCOMPLETE")
            initial = json.loads(row["snapshot"])
            self._reconcile(plan, initial, orders, snapshot)
            evaluation_inputs = {"proposal": plan, "orders": [{"idx": order["idx"], "state": order["state"],
                              "receipt": json.loads(order["receipt"])} for order in orders],
                                 "initial_snapshot": initial, "final_snapshot": snapshot}
            evaluation = run_profile("verification", evaluation_inputs)
            runs = [self._save_evaluation(plan["account"], item, evaluation_inputs, now)
                    for item in evaluation["results"]]
            result = {"status": "VERIFIED", "proposal_hash": proposal_hash, "portfolio": report,
                      "fee_reviews": fee_reviews(plan, orders),
                      "actual_target_differences": target_differences(report, plan["targets"]),
                      "evaluations": evaluation, "evaluation_runs": runs}
            self.db.execute("UPDATE proposals SET state='VERIFIED' WHERE hash=?", (proposal_hash,))
        return result

    def status(self, proposal_hash: str) -> dict:
        row = self._row(proposal_hash)
        orders = self.db.execute("SELECT * FROM orders WHERE proposal=? ORDER BY idx", (proposal_hash,)).fetchall()
        return {"state": row["state"], "orders": [{key: order[key] for key in ("idx", "client_id", "state", "dispatched_at")} for order in orders],
                "fee_reviews": fee_reviews(json.loads(row["proposal"]), orders)}

    def stop(self, proposal_hash: str, snapshot: dict, *, now=None) -> dict:
        now = now_ms() if now is None else now
        validate_snapshot(snapshot, now)
        with self.transaction():
            row = self._row(proposal_hash)
            plan = json.loads(row["proposal"])
            require(snapshot["account"] == plan["account"], "ACCOUNT_MISMATCH")
            require(row["state"] in {"PROPOSED", "APPROVED"}, "PROPOSAL_CLOSED")
            orders = self.db.execute("SELECT * FROM orders WHERE proposal=? ORDER BY idx", (proposal_hash,)).fetchall()
            require(all(o["state"] in {"FILLED", "CANCELED", "REJECTED", "EXPIRED", "EXPIRED_IN_MATCH"} for o in orders),
                    "ORDER_UNRESOLVED")
            self._reconcile(plan, json.loads(row["snapshot"]), orders, snapshot)
            self.db.execute("UPDATE proposals SET state='STOPPED' WHERE hash=?", (proposal_hash,))
        return {"status": "STOPPED", "executed_order_count": len(orders), "action_code": "NEW_PROPOSAL_REQUIRED"}

import json
import sqlite3
from contextlib import contextmanager
from decimal import Decimal
from fractions import Fraction

from .filters import validate_limit
from .portfolio import analyze, target_differences
from .rebalance import propose
from .schemas import (ENDPOINT, ZERO, asset, canonical, decimal, fresh, integer,
                      now_ms, require, validate_snapshot)


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

    def save(self, proposal: dict, snapshot: dict) -> str:
        generated = propose(snapshot, proposal["targets"],
                            fee_allowance_bps=proposal["fee_allowance_bps"],
                            slippage_bps=proposal["slippage_bps"], now=proposal["created_at"],
                            ttl_ms=proposal["expires_at"] - proposal["created_at"])
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
            self._reconcile(plan, json.loads(row["snapshot"]), orders, snapshot)
            result = {"status": "VERIFIED", "proposal_hash": proposal_hash, "portfolio": report,
                      "fee_reviews": fee_reviews(plan, orders),
                      "actual_target_differences": target_differences(report, plan["targets"])}
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

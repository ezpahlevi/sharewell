import tempfile
import unittest
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

from core.journal import Journal
from core.rebalance import propose
from core.schemas import ENDPOINT, SharewellError, text
from fixtures import NOW, snapshot


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = str(Path(self.temp.name) / "journal.sqlite")
        self.journal = Journal(self.path)
        self.data = snapshot()
        self.plan = propose(self.data, {"BTC": "75", "USDT": "25"},
                            fee_allowance_bps="10", slippage_bps="50", now=NOW)
        self.key = self.journal.save(self.plan, self.data)

    def tearDown(self):
        self.journal.close()
        self.temp.cleanup()

    def approve(self):
        self.journal.approve(self.key, self.data["account"], "synthetic-user-approval", now=NOW)

    def fill(self, action, *, quantity=None, status="FILLED"):
        quantity = Decimal(quantity or action["quantity"])
        quote = quantity * Decimal(action["price"])
        receipt = {"account": self.data["account"], "observed_at": NOW, "source": ENDPOINT, "orderId": "fixture-order-1",
                   "evidence": "synthetic-order-query", "clientOrderId": action["newClientOrderId"],
                   "symbol": action["symbol"], "side": action["side"], "type": action["type"],
                   "timeInForce": action["timeInForce"], "price": action["price"],
                   "origQty": action["quantity"], "executedQty": text(quantity),
                   "cummulativeQuoteQty": text(quote), "status": status, "fills_complete": True,
                   "fills": [{"tradeId": "fixture-1", "orderId": "fixture-order-1", "symbol": action["symbol"], "qty": text(quantity), "quoteQty": text(quote),
                              "commission": "0.0001", "commissionAsset": "BTC"}]}
        final = deepcopy(self.data)
        final["balances"][0]["free"] = text(Decimal("1") + quantity - Decimal("0.0001"))
        final["balances"][1]["free"] = text(Decimal("100") - quote)
        return receipt, final

    def complete_distinct_execution(self, index):
        current = deepcopy(self.data)
        current["observed_at"] = NOW + index
        for quote in current["quotes"]:
            quote["observed_at"] = current["observed_at"]
        plan = propose(current, {"BTC": "75", "USDT": "25"}, fee_allowance_bps="10",
                       slippage_bps="50", now=current["observed_at"])
        key = self.journal.save(plan, current)
        self.journal.approve(key, current["account"], "approval-" + str(index), now=current["observed_at"])
        issued = self.journal.dispatch(key, current, now=current["observed_at"])
        receipt, final = self.fill(issued["action"])
        receipt["observed_at"] = current["observed_at"]
        receipt["orderId"] = "fixture-order-" + str(index)
        receipt["fills"][0]["orderId"] = receipt["orderId"]
        receipt["fills"][0]["tradeId"] = "fixture-trade-" + str(index)
        final["observed_at"] = current["observed_at"]
        for quote in final["quotes"]:
            quote["observed_at"] = final["observed_at"]
        self.journal.record(key, 0, receipt, now=current["observed_at"])
        return self.journal.verify(key, final, now=current["observed_at"])

    def test_cannot_dispatch_without_approval(self):
        with self.assertRaisesRegex(SharewellError, "APPROVAL_REQUIRED"):
            self.journal.dispatch(self.key, self.data, now=NOW)

    def test_tampered_plan_cannot_be_saved(self):
        self.plan["orders"][0]["quantity"] = "999"
        with self.assertRaisesRegex(SharewellError, "PROPOSAL_MISMATCH"):
            self.journal.save(self.plan, self.data)

    def test_provider_validation_fails_before_dispatch_marker(self):
        self.approve()
        def reject(action, account, now):
            raise SharewellError("Unsupported native schema")
        with self.assertRaises(SharewellError):
            self.journal.dispatch(self.key, self.data, now=NOW, prepare=reject)
        self.assertEqual(self.journal.status(self.key)["orders"], [])

    def test_reopen_never_reissues_ambiguous_order(self):
        self.approve()
        issued = self.journal.dispatch(self.key, self.data, now=NOW)
        self.journal.close()
        self.journal = Journal(self.path)
        with self.assertRaisesRegex(SharewellError, "ORDER_UNRESOLVED"):
            self.journal.dispatch(self.key, self.data, now=NOW)
        self.assertEqual(self.journal.status(self.key)["orders"][0]["client_id"], issued["action"]["newClientOrderId"])
        with self.assertRaisesRegex(SharewellError, "ORDER_UNRESOLVED"):
            self.journal.stop(self.key, self.data, now=NOW)

    def test_full_fill_and_exact_balance_verification(self):
        self.approve()
        issued = self.journal.dispatch(self.key, self.data, now=NOW)
        receipt, final = self.fill(issued["action"])
        self.journal.record(self.key, 0, receipt, now=NOW)
        result = self.journal.verify(self.key, final, now=NOW)
        self.assertEqual(result["status"], "VERIFIED")
        self.assertTrue(result["actual_target_differences"])
        self.assertEqual(len(result["evaluation_runs"]), 2)
        self.assertEqual(result["learned_preferences"][0]["sample_count"], 1)
        order_metrics = result["evaluations"]["results"][0]["metrics"]["orders"][0]
        self.assertEqual(order_metrics["reference_price"], "101")
        self.assertEqual(order_metrics["slippage_basis"], "INITIAL_QUOTE_TOUCH")
        self.assertTrue(order_metrics["learning_eligible"])
        self.assertNotEqual(order_metrics["realized_slippage_bps"], "0")

    def test_verify_learning_is_idempotent_across_retries_and_restart(self):
        self.approve()
        issued = self.journal.dispatch(self.key, self.data, now=NOW)
        receipt, final = self.fill(issued["action"])
        self.journal.record(self.key, 0, receipt, now=NOW)
        for current_now in (NOW, NOW + 1, NOW + 2):
            result = self.journal.verify(self.key, final, now=current_now)
            self.assertEqual(result["learned_preferences"][0]["sample_count"], 1)
        self.assertEqual(self.journal.db.execute("SELECT COUNT(*) FROM learning_observations").fetchone()[0], 1)
        self.journal.close()
        self.journal = Journal(self.path)
        result = self.journal.verify(self.key, final, now=NOW + 3)
        self.assertEqual(result["learned_preferences"][0]["sample_count"], 1)
        readonly = {**self.data["account"], "can_trade": False}
        self.assertEqual(self.journal.learned_get(readonly)["preferences"][0]["sample_count"], 1)

    def test_three_distinct_executions_produce_three_observations(self):
        for index in (1, 2, 3):
            result = self.complete_distinct_execution(index)
            self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual(self.journal.learned_get(self.data["account"])["preferences"][0]["sample_count"], 3)
        self.assertEqual(self.journal.db.execute("SELECT COUNT(*) FROM learning_observations").fetchone()[0], 3)

    def test_commission_overrun_blocks_next_dispatch_and_is_reported(self):
        self.approve()
        issued = self.journal.dispatch(self.key, self.data, now=NOW)
        receipt, final = self.fill(issued["action"])
        receipt["fills"][0]["commission"] = "0.01"
        final["balances"][0]["free"] = text(Decimal(final["balances"][0]["free"]) - Decimal("0.0099"))
        self.journal.record(self.key, 0, receipt, now=NOW)
        with self.assertRaisesRegex(SharewellError, "FEE_REVIEW_REQUIRED"):
            self.journal.dispatch(self.key, final, now=NOW)
        self.assertEqual(len(self.journal.status(self.key)["fee_reviews"]), 1)
        result = self.journal.verify(self.key, final, now=NOW)
        self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual(result["fee_reviews"][0]["commission"], "0.01")

    def test_external_activity_cannot_be_reported_verified(self):
        self.approve()
        issued = self.journal.dispatch(self.key, self.data, now=NOW)
        receipt, final = self.fill(issued["action"])
        self.journal.record(self.key, 0, receipt, now=NOW)
        final["balances"][0]["free"] = "50"
        with self.assertRaisesRegex(SharewellError, "BALANCE_RECONCILIATION_FAILED"):
            self.journal.verify(self.key, final, now=NOW)

    def test_partial_terminal_fill_requires_new_proposal(self):
        self.approve()
        issued = self.journal.dispatch(self.key, self.data, now=NOW)
        receipt, final = self.fill(issued["action"], quantity="0.1", status="EXPIRED")
        self.journal.record(self.key, 0, receipt, now=NOW)
        with self.assertRaises(SharewellError):
            self.journal.verify(self.key, final, now=NOW)
        with self.assertRaises(SharewellError):
            self.journal.dispatch(self.key, final, now=NOW)
        self.assertEqual(self.journal.stop(self.key, final, now=NOW)["status"], "STOPPED")

    def test_receipt_cannot_change_order_or_duplicate_fills(self):
        self.approve()
        issued = self.journal.dispatch(self.key, self.data, now=NOW)
        receipt, _ = self.fill(issued["action"])
        for key, value in (("clientOrderId", "another"), ("side", "SELL"), ("origQty", "100"),
                           ("fills", receipt["fills"] * 2), ("fills_complete", False)):
            bad = deepcopy(receipt)
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(SharewellError):
                self.journal.record(self.key, 0, bad, now=NOW)

    def test_account_binding_expiry_and_single_active_proposal(self):
        with self.assertRaises(SharewellError):
            self.journal.approve(self.key, {**self.data["account"], "id": "other"}, "ref", now=NOW)
        with self.assertRaises(SharewellError):
            self.journal.approve(self.key, self.data["account"], "ref", now=self.plan["expires_at"])
        self.approve()
        second = propose(self.data, {"BTC": "80", "USDT": "20"}, fee_allowance_bps="10", slippage_bps="50", now=NOW)
        self.journal.save(second, self.data)
        with self.assertRaisesRegex(SharewellError, "ACCOUNT_LOCKED"):
            self.journal.approve(second["hash"], self.data["account"], "ref", now=NOW)


if __name__ == "__main__":
    unittest.main()

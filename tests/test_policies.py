import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from core.journal import Journal
from core.portfolio import analyze
from core.rebalance import propose
from core.schemas import SharewellError
from fixtures import NOW, snapshot


class PolicyTests(unittest.TestCase):
    def test_blocked_assets_remain_visible_and_cannot_trade(self):
        data = snapshot()
        report = analyze(data, NOW)
        plan = propose(data, {"BTC": "100"}, fee_allowance_bps="10", slippage_bps="50",
                       now=NOW, policies={"USDT": "BLOCK"})
        self.assertEqual([row["asset"] for row in report["assets"]], ["BTC", "USDT"])
        self.assertEqual(plan["orders"], [])
        self.assertEqual(plan["issues"][0]["reason"], "BLOCKED_ASSET")
        self.assertFalse(plan["execution_eligible"])

    def test_learning_cannot_bypass_blocked_route_asset(self):
        data = snapshot()
        data["symbols"].append({**data["symbols"][0], "symbol": "BTCBUSD", "quoteAsset": "BUSD"})
        data["quotes"].append({"symbol": "BTCBUSD", "bidPrice": "99", "askPrice": "101", "observed_at": NOW})
        learned = [{"key": "route_penalty:BTCUSDT", "value": {"penalty_bps": "-100"}, "sample_count": 9}]
        plan = propose(data, {"BTC": "0", "USDT": "100"}, fee_allowance_bps="10", slippage_bps="50",
                       now=NOW, policies={"USDT": "BLOCK"}, learned_preferences=learned)
        self.assertTrue(any(issue["reason"] == "BLOCKED_ASSET" for issue in plan["issues"]))
        self.assertFalse(plan["orders"])

    def test_allowlist_preserves_unlisted_holdings(self):
        data = snapshot()
        before = deepcopy(data)
        plan = propose(data, {"BTC": "100"}, fee_allowance_bps="10", slippage_bps="50",
                       now=NOW, policies={"BTC": "ALLOW"})
        self.assertEqual(data, before)
        self.assertEqual(plan["orders"], [])
        self.assertEqual(plan["residual_value_differences"]["USDT"], "-100")
        self.assertEqual(plan["issues"][0]["reason"], "ASSET_NOT_ALLOWED")

    def test_policies_and_default_numeraire_persist(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = Journal(str(Path(directory) / "state.sqlite"))
            account = snapshot()["account"]
            self.assertEqual(journal.policy_set(account, "BTC", "BLOCK", "message-1", now=NOW)["policies"][0]["policy"], "BLOCK")
            self.assertEqual(journal.preference_set(account, "default_numeraire", "BTC", "message-2", now=NOW)["preferences"][0]["value"], "BTC")
            journal.close()
            reopened = Journal(str(Path(directory) / "state.sqlite"))
            self.assertEqual(reopened.policy_get(account)["policies"][0]["asset"], "BTC")
            self.assertEqual(reopened.default_numeraire(account), "BTC")
            reopened.close()

    def test_policy_change_blocks_existing_proposal(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = Journal(str(Path(directory) / "state.sqlite"))
            data = snapshot()
            plan = propose(data, {"BTC": "75", "USDT": "25"}, fee_allowance_bps="10",
                           slippage_bps="50", now=NOW)
            journal.save(plan, data)
            journal.policy_set(data["account"], "USDT", "BLOCK", "message-3", now=NOW)
            with self.assertRaisesRegex(SharewellError, "POLICY_CHANGED"):
                journal.approve(plan["hash"], data["account"], "message-4", now=NOW)
            journal.close()

    def test_synthetic_snapshot_needs_explicit_live_gate_and_history_is_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = Journal(str(Path(directory) / "state.sqlite"))
            data = snapshot()
            with self.assertRaisesRegex(SharewellError, "LIVE_SNAPSHOT_REQUIRED"):
                journal.save_snapshot(data, "ANALYSIS", now=NOW)
            saved = journal.save_snapshot(data, "ANALYSIS", live=True, now=NOW)
            history = journal.history(data["account"], 1)
            self.assertEqual(history["history"][0]["snapshot_hash"], saved["snapshot_hash"])
            self.assertEqual(history["current_truth"], "LIVE_INPUT_REQUIRED")
            self.assertEqual(journal.memory_summary(data["account"])["latest_snapshot"]["reason"], "ANALYSIS")
            stale = deepcopy(data)
            with self.assertRaisesRegex(SharewellError, "STALE_EVIDENCE"):
                journal.save_snapshot(stale, "ANALYSIS", live=True, now=NOW + 60_001)
            journal.close()

    def test_new_tables_do_not_change_existing_journal_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "state.sqlite")
            journal = Journal(path)
            names = {row[0] for row in journal.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue({"proposals", "orders", "asset_policies", "user_preferences",
                             "portfolio_snapshots"} <= names)
            journal.close()


if __name__ == "__main__":
    unittest.main()

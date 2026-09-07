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


if __name__ == "__main__":
    unittest.main()

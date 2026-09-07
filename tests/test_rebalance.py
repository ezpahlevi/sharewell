import unittest
from copy import deepcopy
from decimal import Decimal

from core.rebalance import propose
from core.portfolio import Market
from core.schemas import SharewellError, digest
from fixtures import NOW, snapshot, symbol


class RebalanceTests(unittest.TestCase):
    def plan(self, data=None, targets=None, **options):
        return propose(data or snapshot(), targets or {"BTC": "75", "USDT": "25"},
                       fee_allowance_bps="10", slippage_bps="50", now=NOW, **options)

    def test_buy_is_bounded_and_hash_binds_targets(self):
        plan = self.plan()
        order = plan["orders"][0]
        self.assertEqual(order["side"], "BUY")
        self.assertLessEqual(Decimal(order["source_reserve"]), 50)
        self.assertLessEqual(Decimal(order["price"]), Decimal("101") * Decimal("1.005"))
        claimed = plan.pop("hash")
        self.assertEqual(claimed, digest(plan))
        plan["targets"]["BTC"] = "80"
        self.assertNotEqual(claimed, digest(plan))

    def test_sell_rounds_above_price_floor(self):
        order = self.plan(targets={"USDT": "100"})["orders"][0]
        self.assertEqual(order["side"], "SELL")
        self.assertGreaterEqual(Decimal(order["price"]), Decimal("99") * Decimal("0.995"))

    def test_locked_cannot_be_spent(self):
        data = snapshot()
        data["balances"][1].update(free="0", locked="100")
        plan = self.plan(data)
        self.assertEqual(plan["orders"], [])
        self.assertEqual(plan["residual_value_differences"]["BTC"], "50")

    def test_multihop_and_dependencies(self):
        data = snapshot()
        data["symbols"].append(symbol("ETH", "USDT"))
        data["quotes"].append({"symbol": "ETHUSDT", "bidPrice": "10", "askPrice": "10", "observed_at": NOW})
        plan = self.plan(data, {"ETH": "100"})
        self.assertGreaterEqual(len(plan["orders"]), 2)
        for index, order in enumerate(plan["orders"]):
            self.assertEqual(order["depends_on"], index - 1 if index else None)

    def test_failed_second_leg_discards_whole_route(self):
        data = snapshot()
        data["balances"] = data["balances"][:1]
        eth = symbol("ETH", "USDT")
        eth["filters"][-1]["minNotional"] = "100000"
        data["symbols"].append(eth)
        data["quotes"].append({"symbol": "ETHUSDT", "bidPrice": "10", "askPrice": "10", "observed_at": NOW})
        plan = self.plan(data, {"ETH": "100"})
        self.assertEqual(plan["orders"], [])
        self.assertTrue(plan["issues"])

    def test_no_mutation_and_read_only_account(self):
        data = snapshot()
        data["account"].update(kind="MAIN_READ_ONLY", can_trade=False)
        before = deepcopy(data)
        self.assertFalse(self.plan(data)["execution_eligible"])
        self.assertEqual(data, before)

    def test_unknown_target_and_lifetime_rejected(self):
        with self.assertRaises(SharewellError):
            self.plan(targets={"UNKNOWN": "100"})
        with self.assertRaises(SharewellError):
            self.plan(ttl_ms=300001)

    def test_maximum_quantity_splits_order_without_exceeding_budget(self):
        data = snapshot()
        data["symbols"][0]["filters"][1]["maxQty"] = "0.2"
        plan = self.plan(data)
        self.assertEqual(len(plan["orders"]), 3)
        self.assertTrue(all(Decimal(order["quantity"]) <= Decimal("0.2") for order in plan["orders"]))
        self.assertLessEqual(sum(Decimal(order["source_reserve"]) for order in plan["orders"]), 50)

    def test_account_asset_cap_is_used_for_order_splitting(self):
        data = snapshot()
        data["asset_filters"] = [{"filterType": "MAX_ASSET", "asset": "USDT", "limit": "20"}]
        plan = self.plan(data)
        self.assertGreater(len(plan["orders"]), 1)
        for order in plan["orders"]:
            self.assertLessEqual(Decimal(order["price"]) * Decimal(order["quantity"]), Decimal("20"))

    def test_alternate_route_when_direct_pair_fails_filters(self):
        data = snapshot()
        data["balances"] = data["balances"][:1]
        direct = symbol("BTC", "ETH")
        direct["filters"][-1]["minNotional"] = "100000"
        data["symbols"].extend([direct, symbol("ETH", "USDT")])
        data["quotes"].extend([
            {"symbol": "BTCETH", "bidPrice": "10", "askPrice": "10", "observed_at": NOW},
            {"symbol": "ETHUSDT", "bidPrice": "10", "askPrice": "10", "observed_at": NOW}])
        plan = self.plan(data, {"ETH": "100"})
        self.assertGreaterEqual(len(plan["orders"]), 2)
        self.assertEqual([order["symbol"] for order in plan["orders"][:2]], ["BTCUSDT", "ETHUSDT"])
        self.assertNotIn("BTCETH", [order["symbol"] for order in plan["orders"]])

    def test_route_learning_needs_three_observations_and_binds_context(self):
        data = snapshot()
        data["symbols"].extend([symbol("BTC", "BUSD"), symbol("ETH", "BUSD"), symbol("ETH", "USDT")])
        data["quotes"].extend([
            {"symbol": "BTCBUSD", "bidPrice": "99", "askPrice": "101", "observed_at": NOW},
            {"symbol": "ETHBUSD", "bidPrice": "9", "askPrice": "11", "observed_at": NOW},
            {"symbol": "ETHUSDT", "bidPrice": "9", "askPrice": "11", "observed_at": NOW}])
        routes = list(Market(data).routes("BTC", "ETH"))
        first, second = routes[0], routes[1]
        low_sample = [{"key": "route_penalty:" + edge["symbol"],
                       "value": {"penalty_bps": "100"}, "sample_count": 2} for edge in first]
        low_sample.extend({"key": "route_penalty:" + edge["symbol"],
                           "value": {"penalty_bps": "0"}, "sample_count": 2} for edge in second)
        plan = self.plan(data, {"ETH": "100"}, learned_preferences=low_sample)
        self.assertFalse(plan.get("learning_context"))
        reliable = [{"key": "route_penalty:" + edge["symbol"],
                     "value": {"penalty_bps": "100"}, "sample_count": 3} for edge in first]
        reliable.extend({"key": "route_penalty:" + edge["symbol"],
                         "value": {"penalty_bps": "0"}, "sample_count": 3} for edge in second)
        plan = self.plan(data, {"ETH": "100"}, learned_preferences=reliable)
        self.assertTrue(plan["learning_context"])
        self.assertEqual(plan["learning_context"][0]["route"], [edge["symbol"] for edge in second])


if __name__ == "__main__":
    unittest.main()

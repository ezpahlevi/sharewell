import unittest

from core.schemas import SharewellError, decimal, validate_snapshot
from core.portfolio import Market, analyze, target_differences
from fixtures import NOW, snapshot, symbol


class DecimalTests(unittest.TestCase):
    def test_reject_float_and_nonfinite(self):
        for value in (0.1, "NaN", "Infinity", "-1", True):
            with self.subTest(value=value), self.assertRaises(SharewellError):
                decimal(value)


class PortfolioTests(unittest.TestCase):
    def test_value_weights_and_concentration(self):
        report = analyze(snapshot(), NOW)
        self.assertEqual(report["total_value"], "200")
        self.assertEqual([row["weight_pct"] for row in report["assets"]], ["50", "50"])
        self.assertEqual(report["concentration"]["hhi"], "0.5")
        self.assertEqual(report["concentration"]["effective_asset_count"], "2")

    def test_inverse_pair_does_not_assume_stablecoin_peg(self):
        data = snapshot()
        data["numeraire"] = "BTC"
        self.assertEqual(analyze(data, NOW)["total_value"], "2")

    def test_multihop_repeating_decimal(self):
        data = snapshot()
        data["numeraire"] = "ETH"
        data["symbols"].append(symbol("ETH", "USDT"))
        data["quotes"].append({"symbol": "ETHUSDT", "bidPrice": "3", "askPrice": "3", "observed_at": NOW})
        report = analyze(data, NOW)
        self.assertEqual(report["coverage"], "COMPLETE")
        self.assertEqual(len(target_differences(report, {"ETH": "100"})), 3)

    def test_unpriced_is_explicit_and_blocks_targets(self):
        data = snapshot()
        data["balances"].append({"asset": "UNKNOWN", "free": "2", "locked": "0"})
        report = analyze(data, NOW)
        self.assertIsNone(report["total_value"])
        self.assertEqual(report["weight_basis"], "priced_assets_only")
        with self.assertRaises(SharewellError):
            target_differences(report, {"BTC": "100"})

    def test_locked_funds_count_in_value(self):
        data = snapshot()
        data["balances"][0].update(free="0.5", locked="0.5")
        self.assertEqual(analyze(data, NOW)["total_value"], "200")

    def test_exact_targets(self):
        report = analyze(snapshot(), NOW)
        differences = target_differences(report, {"BTC": "75", "USDT": "25"})
        self.assertEqual([row["difference"] for row in differences], ["50", "-50"])
        for targets in ({"BTC": "99.999"}, {"btc": "100"}, {}, {"BTC": 100}):
            with self.subTest(targets=targets), self.assertRaises(SharewellError):
                target_differences(report, targets)

    def test_stale_and_malformed_snapshots_fail(self):
        for key, value in (("version", True), ("account", []), ("balances", [None]),
                           ("symbols", [None]), ("quotes", [None]), ("observed_at", NOW - 60_001)):
            data = snapshot()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(SharewellError):
                validate_snapshot(data, NOW)

    def test_route_search_limit_is_explicit(self):
        data = snapshot()
        data["symbols"].append(symbol("ETH", "USDT"))
        data["quotes"].append({"symbol": "ETHUSDT", "bidPrice": "10", "askPrice": "10", "observed_at": NOW})
        with self.assertRaisesRegex(SharewellError, "ROUTE_SEARCH_LIMIT"):
            list(Market(data).routes("BTC", "ETH", search_limit=1))


if __name__ == "__main__":
    unittest.main()

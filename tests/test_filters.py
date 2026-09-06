import unittest
from decimal import Decimal, localcontext
from fractions import Fraction

from core.filters import multiple, validate_limit
from core.schemas import SharewellError
from fixtures import NOW, snapshot


class FilterTests(unittest.TestCase):
    def check(self, data, side="BUY", quantity="0.1", price="100"):
        validate_limit(data["symbols"][0], side, Decimal(quantity), Decimal(price), data, NOW)

    def test_non_decimal_step_and_rounding_direction(self):
        self.assertEqual(multiple(Decimal("1.08"), Decimal("0.05")), Decimal("1.05"))
        self.assertEqual(multiple(Decimal("1.08"), Decimal("0.05"), up=True), Decimal("1.10"))

    def test_rounding_does_not_cross_boundary_at_low_context_precision(self):
        value = Decimal("0.999999999999999999999999999999")
        with localcontext() as context:
            context.prec = 8
            self.assertEqual(multiple(value, Decimal("0.01")), Decimal("0.99"))
            self.assertEqual(multiple(value, Decimal("0.01"), up=True), Decimal("1.00"))

    def test_affordable_quantity_uses_exact_fraction_before_rounding(self):
        with localcontext() as context:
            context.prec = 8
            budget = Fraction(Decimal("0.999999999999999999999999999999"))
            self.assertEqual(multiple(budget / Fraction("3"), Decimal("0.0001")), Decimal("0.3333"))

    def test_large_result_coefficient_is_not_rounded(self):
        value = Decimal("123456789012345678901234567890.12")
        with localcontext() as context:
            context.prec = 8
            self.assertEqual(multiple(value, Decimal("0.01")), value)

    def test_valid_limit(self):
        self.check(snapshot())

    def test_account_permission_groups_use_and_of_or(self):
        data = snapshot()
        data["symbols"][0]["permissionSets"] = [["SPOT"], ["GROUP_A", "GROUP_B"]]
        with self.assertRaises(SharewellError):
            self.check(data)
        data["account_permissions"] = ["SPOT"]
        with self.assertRaises(SharewellError):
            self.check(data)
        data["account_permissions"].append("GROUP_B")
        self.check(data)

    def test_max_asset_applies_to_base_and_quote(self):
        for name, limit in (("BTC", "0.05"), ("USDT", "5")):
            data = snapshot()
            data["asset_filters"] = [{"filterType": "MAX_ASSET", "asset": name, "limit": limit}]
            with self.subTest(asset=name), self.assertRaisesRegex(SharewellError, "MAX_ASSET"):
                self.check(data)

    def test_tick_quantity_and_min_notional(self):
        for quantity, price in (("0.1001", "100"), ("0.1", "100.001"), ("0.01", "100")):
            with self.subTest(quantity=quantity, price=price), self.assertRaises(SharewellError):
                self.check(snapshot(), quantity=quantity, price=price)

    def test_inapplicable_market_filter_is_ignored(self):
        data = snapshot()
        data["symbols"][0]["filters"].append({"filterType": "MARKET_LOT_SIZE", "minQty": "1000"})
        self.check(data)

    def test_unknown_filter_does_not_silently_pass(self):
        data = snapshot()
        data["symbols"][0]["filters"].append({"filterType": "NEW_FILTER"})
        with self.assertRaisesRegex(SharewellError, "UNSUPPORTED_SYMBOL_FILTER"):
            self.check(data)

    def test_percentage_reference_is_required_and_fresh(self):
        data = snapshot()
        data["symbols"][0]["filters"].append({"filterType": "PERCENT_PRICE_BY_SIDE",
            "bidMultiplierUp": "1.1", "bidMultiplierDown": "0.9",
            "askMultiplierUp": "1.2", "askMultiplierDown": "0.8", "avgPriceMins": 5})
        with self.assertRaisesRegex(SharewellError, "MISSING_FILTER_REFERENCE"):
            self.check(data)
        reference = {"basis": "REFERENCE_PRICE", "price": "100", "observed_at": NOW}
        data["filter_references"] = {"BTCUSDT": {"PERCENT_PRICE_BY_SIDE": reference}}
        self.check(data)
        with self.assertRaises(SharewellError):
            self.check(data, price="111")
        self.check(data, side="SELL", price="111")
        reference["observed_at"] -= 60_001
        with self.assertRaises(SharewellError):
            self.check(data)

    def test_price_range_rejects_unreachable_limit(self):
        data = snapshot()
        data["execution_rules"] = [{"symbol": "BTCUSDT", "rules": [{
            "ruleType": "PRICE_RANGE", "bidLimitMultUp": "1.15", "bidLimitMultDown": "0.85",
            "askLimitMultUp": "1.15", "askLimitMultDown": "0.85"}]}]
        data["filter_references"] = {"BTCUSDT": {"PRICE_RANGE": {
            "basis": "REFERENCE_PRICE", "price": "100", "observed_at": NOW}}}
        self.check(data, side="BUY", price="90")
        self.check(data, side="SELL", price="110")
        with self.assertRaisesRegex(SharewellError, "PRICE_RANGE_UNREACHABLE"):
            self.check(data, side="BUY", price="80")
        with self.assertRaisesRegex(SharewellError, "PRICE_RANGE_UNREACHABLE"):
            self.check(data, side="SELL", price="120")

    def test_price_range_null_reference_is_not_enforced(self):
        data = snapshot()
        data["execution_rules"] = [{"symbol": "BTCUSDT", "rules": [{
            "ruleType": "PRICE_RANGE", "bidLimitMultDown": "0.85", "askLimitMultUp": "1.15"}]}]
        data["filter_references"] = {"BTCUSDT": {"PRICE_RANGE": {
            "basis": "REFERENCE_PRICE", "price": None, "observed_at": NOW}}}
        self.check(data, side="BUY", price="80")

    def test_position_includes_locked_and_open_buys(self):
        data = snapshot()
        data["symbols"][0]["filters"].append({"filterType": "MAX_POSITION", "maxPosition": "1.2"})
        self.check(data)
        data["balances"][0]["locked"] = "0.1"
        data["open_orders"] = [{"symbol": "BTCUSDT", "side": "BUY", "origQty": "0.1"}]
        with self.assertRaisesRegex(SharewellError, "MAX_POSITION"):
            self.check(data)
        self.check(data, side="SELL")


if __name__ == "__main__":
    unittest.main()

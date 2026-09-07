import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from core.evaluation import run_evaluator
from core.historical_data import build_price_history
from core.journal import Journal
from core.rebalance import propose
from core.schemas import ENDPOINT, SharewellError
from fixtures import NOW, snapshot
from providers.binance_mcp import normalize_kline_capture


DAY = 86_400_000
CAPTURED_AT = 100 * DAY


def native(rows, *, error=False):
    return {"isError": error, "content": [{"type": "text", "text": json.dumps(rows)}]}


def row(day, close, *, symbol="BTCUSDT", interval="1d"):
    value = str(close)
    return [day * DAY, value, value, value, value, "1.2300",
            (day + 1) * DAY - 1, "123.4500", 10, "0.5000", "50.0000", "0"]


def capture(rows, *, symbol="BTCUSDT", interval="1d", start=None, end=None, evidence="mcp-kline-1"):
    result = {"source": ENDPOINT, "tool": "spot.klines", "symbol": symbol, "interval": interval,
              "observed_at": CAPTURED_AT, "evidence": evidence, "result": native(rows)}
    if start is not None:
        result["requested_start"] = start
    if end is not None:
        result["requested_end"] = end
    return normalize_kline_capture(result, now=CAPTURED_AT)


class HistoricalProviderTests(unittest.TestCase):
    def test_valid_rows_are_sorted_and_decimal_text_is_preserved(self):
        result = capture([row(2, "123.45000000"), row(0, "100.00000000"), row(1, "110.00000000")])
        self.assertEqual([item["open_time"] for item in result["candles"]], [0, DAY, 2 * DAY])
        self.assertEqual(result["candles"][2]["close"], "123.45000000")
        self.assertEqual(result["candles"][2]["volume"], "1.2300")
        self.assertEqual(result["symbol"], "BTCUSDT")
        self.assertEqual(result["interval"], "1d")
        self.assertEqual(result["evidence"], "mcp-kline-1")

    def test_malformed_duplicate_and_error_rows_fail(self):
        cases = [
            [row(0, "100")[:-1]],
            [row(0, "1e2")],
            [row(0, "100"), row(0, "101")],
        ]
        for rows in cases:
            with self.subTest(rows=rows), self.assertRaises(SharewellError):
                capture(rows)
        request = {"source": ENDPOINT, "tool": "spot.klines", "symbol": "BTCUSDT", "interval": "1d",
                   "observed_at": CAPTURED_AT, "evidence": "mcp-kline-error", "result": native([], error=True)}
        with self.assertRaises(SharewellError):
            normalize_kline_capture(request, now=CAPTURED_AT)

    def test_requested_history_completeness_is_reported(self):
        result = capture([row(1, "100"), row(2, "101")], start=0, end=5 * DAY)
        self.assertFalse(result["complete"])

    def test_source_tool_symbol_and_interval_are_strict(self):
        for key, value in (("source", "https://example.com"), ("tool", "spot.uiKlines")):
            request = {"source": ENDPOINT, "tool": "spot.klines", "symbol": "BTCUSDT", "interval": "1d",
                       "observed_at": CAPTURED_AT, "evidence": "mcp-kline-strict", "result": native([row(0, "100")])}
            request[key] = value
            with self.subTest(key=key), self.assertRaises(SharewellError):
                normalize_kline_capture(request, now=CAPTURED_AT)


class HistoricalDataTests(unittest.TestCase):
    def test_direct_pair_builds_close_price_history(self):
        result = build_price_history([capture([row(0, "100.00"), row(1, "110.00")])],
                                     assets=["BTC"], numeraire="USDT", as_of=2 * DAY,
                                     windows_days=[1, 7])
        self.assertEqual(result["coverage"]["routes"], {"BTC": "DIRECT"})
        self.assertEqual([item["price"] for item in result["price_history"]], ["100.00", "110.00"])

    def test_inverse_pair_uses_exact_decimal_division(self):
        result = build_price_history([capture([row(0, "0.0100", symbol="USDTBTC"),
                                               row(1, "0.0125", symbol="USDTBTC")], symbol="USDTBTC")],
                                     assets=["BTC"], numeraire="USDT", as_of=2 * DAY,
                                     windows_days=[1])
        self.assertEqual(result["coverage"]["routes"], {"BTC": "INVERSE"})
        self.assertEqual([item["price"] for item in result["price_history"]], ["100", "80"])

    def test_missing_pair_is_unavailable_without_zero_values(self):
        result = build_price_history([], assets=["SOL"], numeraire="USDT", as_of=2 * DAY, windows_days=[30])
        self.assertEqual(result["price_history"], [])
        self.assertEqual(result["coverage"]["missing_assets"], ["SOL"])
        evaluation = run_evaluator("historical_market_performance", result)
        self.assertEqual(evaluation["status"], "UNAVAILABLE")
        self.assertEqual(evaluation["metrics"]["assets"]["SOL"]["windows"], {})

    def test_unknown_pair_does_not_assume_stablecoin_peg(self):
        with self.assertRaisesRegex(SharewellError, "UNEXPECTED_HISTORICAL_SYMBOL"):
            build_price_history([capture([row(0, "100")])], assets=["BTC"], numeraire="USD", as_of=DAY,
                                windows_days=[1])

    def test_incomplete_current_candle_is_not_used(self):
        result = build_price_history([capture([row(99, "99"), row(100, "100")])], assets=["BTC"],
                                     numeraire="USDT", as_of=101 * DAY, windows_days=[1])
        self.assertEqual([item["observed_at"] for item in result["price_history"]], [100 * DAY - 1])
        self.assertEqual(result["coverage"]["incomplete_assets"], ["BTC"])

    def test_identity_numeraire_is_not_a_stablecoin_conversion(self):
        result = build_price_history([capture([row(0, "100")])], assets=["BTC", "USDT"], numeraire="USDT",
                                     as_of=DAY, windows_days=[1])
        identity = [item for item in result["price_history"] if item["asset"] == "USDT"]
        self.assertEqual(identity, [{"asset": "USDT", "observed_at": DAY - 1, "price": "1"}])


class HistoricalEvaluatorTests(unittest.TestCase):
    def history(self, days=90):
        return {"source": ENDPOINT, "as_of": days * DAY, "requested_assets": ["BTC", "ETH"],
                "coverage": {"incomplete_assets": []}, "evidence": ["mcp-kline-history"],
                "price_history": [{"asset": asset_name, "observed_at": day * DAY,
                                   "price": str(100 + day if asset_name == "BTC" else 50 + day)}
                                  for asset_name in ("BTC", "ETH") for day in range(days + 1)]}

    def test_default_and_non_default_windows_are_runtime_parameters(self):
        default = run_evaluator("historical_market_performance", self.history(),
                                {"windows_days": [3, 7, 14, 30], "metrics": ["return"]})
        custom = run_evaluator("historical_market_performance", self.history(),
                               {"windows_days": [1, 7, 30, 90], "metrics": ["return"]})
        self.assertEqual(default["parameters"]["windows_days"], [3, 7, 14, 30])
        self.assertEqual(custom["parameters"]["windows_days"], [1, 7, 30, 90])
        self.assertEqual(custom["status"], "PASS")

    def test_insufficient_history_is_partial_or_unavailable_not_zero(self):
        inputs = self.history(30)
        inputs["price_history"] = [row for row in inputs["price_history"] if row["observed_at"] >= 20 * DAY]
        result = run_evaluator("historical_market_performance", inputs,
                              {"windows_days": [30], "metrics": ["return"]})
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["metrics"]["assets"]["BTC"]["windows"], {})

    def test_named_benchmark_requires_supplied_history(self):
        result = run_evaluator("historical_market_performance", self.history(30),
                              {"windows_days": [30], "metrics": ["return", "relative_strength"],
                               "benchmark": "BTC"})
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["metrics"]["assets"]["ETH"]["windows"]["30"]["relative_strength"], "0.3")
        missing = self.history(30)
        missing["requested_assets"] = ["ETH"]
        missing["price_history"] = [row for row in missing["price_history"] if row["asset"] == "ETH"]
        result = run_evaluator("historical_market_performance", missing,
                              {"windows_days": [30], "metrics": ["relative_strength"], "benchmark": "BTC"})
        self.assertEqual(result["status"], "PARTIAL")
        self.assertIn("MISSING_BENCHMARK_HISTORY", result["warnings"])

    def test_portfolio_benchmark_requires_evidence(self):
        inputs = self.history(30)
        inputs["benchmark_history"] = [{"observed_at": 0, "price": "100"},
                                        {"observed_at": 30 * DAY, "price": "110"}]
        inputs["benchmark_evidence"] = ["mcp-portfolio-benchmark"]
        result = run_evaluator("historical_market_performance", inputs,
                              {"windows_days": [30], "metrics": ["relative_strength"],
                               "benchmark": "PORTFOLIO"})
        self.assertEqual(result["status"], "PASS")
        self.assertIn("mcp-portfolio-benchmark", result["evidence"])

    def test_historical_evaluation_does_not_mutate_approved_proposal_or_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = Journal(str(Path(directory) / "state.sqlite"))
            data = snapshot()
            plan = propose(data, {"BTC": "75", "USDT": "25"}, fee_allowance_bps="10", slippage_bps="50", now=NOW)
            journal.save(plan, data)
            journal.approve(plan["hash"], data["account"], "synthetic-approval", now=NOW)
            journal.policy_set(data["account"], "SOL", "BLOCK", "synthetic-policy", now=NOW)
            before = tuple(journal.db.execute("SELECT proposal, snapshot, state FROM proposals WHERE hash=?",
                                              (plan["hash"],)).fetchone())
            journal.evaluate(data["account"], self.history(), evaluator_id="historical_market_performance",
                             parameters={"windows_days": [1], "metrics": ["return"]}, now=NOW)
            after = tuple(journal.db.execute("SELECT proposal, snapshot, state FROM proposals WHERE hash=?",
                                             (plan["hash"],)).fetchone())
            self.assertEqual(before, after)
            self.assertEqual(journal.policy_get(data["account"])["policies"][0]["asset"], "SOL")
            journal.close()


if __name__ == "__main__":
    unittest.main()

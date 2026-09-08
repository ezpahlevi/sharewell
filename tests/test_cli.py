import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from core.schemas import ENDPOINT, now_ms, text
from fixtures import snapshot

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "sharewell.py"


class CliTests(unittest.TestCase):
    def call(self, operation, request, directory, *, raw=False):
        path = Path(directory) / "request.json"
        path.write_text(request if raw else json.dumps(request), encoding="utf-8")
        result = subprocess.run([sys.executable, "-B", str(SCRIPT), operation, "--input", str(path),
                                 "--state", str(Path(directory) / "state.sqlite")],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.stderr, "")
        return result.returncode, json.loads(result.stdout)

    def live_fixture(self):
        data = snapshot()
        data["observed_at"] = now_ms()
        for quote in data["quotes"]:
            quote["observed_at"] = data["observed_at"]
        return data

    def test_analyze_and_persist_proposal_across_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            data = self.live_fixture()
            code, result = self.call("analyze", {"snapshot": data}, directory)
            self.assertEqual(code, 0)
            self.assertEqual(result["result"]["total_value"], "200")
            code, result = self.call("propose", {"snapshot": data, "targets": {"BTC": "75", "USDT": "25"},
                                     "fee_allowance_bps": "10", "slippage_bps": "50"}, directory)
            self.assertEqual(code, 0)
            key = result["result"]["hash"]
            code, result = self.call("status", {"proposal_hash": key}, directory)
            self.assertEqual(code, 0)
            self.assertEqual(result["result"]["state"], "PROPOSED")

    def test_malformed_duplicate_and_stale_inputs_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            for request in ('{"snapshot":{},"snapshot":{}}', '{', '[]', json.dumps({"snapshot": snapshot()})):
                code, result = self.call("analyze", request, directory, raw=True)
                self.assertEqual(code, 1)
                self.assertFalse(result["ok"])

    def test_default_numeraire_is_used_without_changing_explicit_override(self):
        with tempfile.TemporaryDirectory() as directory:
            data = self.live_fixture()
            code, result = self.call("preference-set", {"account": data["account"],
                                     "key": "default_numeraire", "value": "BTC",
                                     "source_reference": "synthetic-preference"}, directory)
            self.assertEqual(code, 0, result)
            code, result = self.call("analyze", {"snapshot": data}, directory)
            self.assertEqual(code, 0, result)
            self.assertEqual(result["result"]["numeraire"], "BTC")
            self.assertEqual(result["result"]["total_value"], "2")
            code, result = self.call("analyze", {"snapshot": data, "numeraire": "USDT"}, directory)
            self.assertEqual(code, 0, result)
            self.assertEqual(result["result"]["numeraire"], "USDT")
            self.assertEqual(result["result"]["total_value"], "200")

    def test_historical_inputs_normalizes_native_spot_klines(self):
        with tempfile.TemporaryDirectory() as directory:
            day = 86_400_000
            request = {"captures": [{"source": ENDPOINT, "tool": "spot.klines", "symbol": "BTCUSDT",
                                      "interval": "1d", "timeZone": "0", "observed_at": now_ms(),
                                      "evidence": "synthetic-kline-cli", "result": {
                                          "isError": False, "content": [{"type": "text", "text": json.dumps([
                                              [0, "100.00", "100.00", "100.00", "100.00", "1.00", day - 1,
                                               "100.00", 1, "0.50", "50.00", "0"],
                                              [day, "110.00", "110.00", "110.00", "110.00", "1.00", 2 * day - 1,
                                               "110.00", 1, "0.50", "55.00", "0"]])}]} }],
                       "assets": ["BTC"], "numeraire": "USDT", "as_of": 2 * day, "windows_days": [1]}
            code, result = self.call("historical-inputs", request, directory)
            self.assertEqual(code, 0, result)
            self.assertEqual(result["result"]["price_history"][1]["price"], "110.00")
            self.assertEqual(result["result"]["coverage"]["routes"]["BTC"], "DIRECT")
            code, evaluation = self.call("evaluate", {"account": snapshot()["account"],
                                                        "inputs": result["result"],
                                                        "evaluator_id": "historical_market_performance",
                                                        "parameters": {"windows_days": [1], "metrics": ["return"]}},
                                         directory)
            self.assertEqual(code, 0, evaluation)
            self.assertEqual(evaluation["result"]["result"]["status"], "PASS")
            self.assertEqual(evaluation["result"]["runs"][0]["evaluator_id"], "historical_market_performance")

    def test_chat_workflow_protocol_through_separate_cli_processes(self):
        """Synthetic host contract test, not a Binance integration test."""
        with tempfile.TemporaryDirectory() as directory:
            data = self.live_fixture()
            code, result = self.call("propose", {"snapshot": data, "targets": {"BTC": "75", "USDT": "25"},
                                     "fee_allowance_bps": "10", "slippage_bps": "50"}, directory)
            self.assertEqual(code, 0)
            key = result["result"]["hash"]
            code, result = self.call("approve", {"proposal_hash": key, "account": data["account"],
                                                "approval_ref": "synthetic-user-message"}, directory)
            self.assertEqual(code, 0)
            fields = ["symbol", "side", "type", "timeInForce", "quantity", "price", "newClientOrderId"]
            catalog = {"source": ENDPOINT, "observed_at": now_ms(), "tools": [{
                "name": "synthetic_placement", "description": "Synthetic Spot placement for this test only.",
                "inputSchema": {"type": "object", "properties": {f: {"type": "string"} for f in fields},
                                "required": fields, "additionalProperties": False}}]}
            binding = {"operation": "SPOT_LIMIT_ORDER", "tool": "synthetic_placement",
                       "fields": {f: "/" + f for f in fields}}
            data = self.live_fixture()
            request = {"proposal_hash": key, "snapshot": data, "catalog": catalog, "binding": binding}
            code, result = self.call("dispatch", request, directory)
            self.assertEqual(code, 0, result)
            action = result["result"]["native_call"]["arguments"]
            code, duplicate = self.call("dispatch", request, directory)
            self.assertEqual(code, 1)
            self.assertFalse(duplicate["ok"])
            quantity = Decimal(action["quantity"])
            quote = quantity * Decimal(action["price"])
            receipt = {"source": ENDPOINT, "account": data["account"], "observed_at": now_ms(),
                "evidence": "synthetic-binance-query", "orderId": "fixture-order", "clientOrderId": action["newClientOrderId"],
                **{k: action[k] for k in ("symbol", "side", "type", "timeInForce", "price")},
                "origQty": action["quantity"], "executedQty": text(quantity), "cummulativeQuoteQty": text(quote),
                "status": "FILLED", "fills_complete": True, "fills": [{"tradeId": "fixture-trade", "orderId": "fixture-order",
                "symbol": action["symbol"], "qty": text(quantity), "quoteQty": text(quote),
                "commission": "0.0001", "commissionAsset": "BTC"}]}
            code, result = self.call("record", {"proposal_hash": key, "index": 0, "receipt": receipt}, directory)
            self.assertEqual(code, 0, result)
            final = self.live_fixture()
            final["balances"][0]["free"] = text(Decimal("1") + quantity - Decimal("0.0001"))
            final["balances"][1]["free"] = text(Decimal("100") - quote)
            code, result = self.call("verify", {"proposal_hash": key, "snapshot": final}, directory)
            self.assertEqual(code, 0, result)
            self.assertEqual(result["result"]["status"], "VERIFIED")


if __name__ == "__main__":
    unittest.main()

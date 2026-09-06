import unittest
from copy import deepcopy

from core.schemas import ENDPOINT, SharewellError
from providers.binance_mcp import bind_order, normalize_snapshot, unwrap, validate_arguments
from fixtures import NOW, snapshot


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.action = {"symbol": "BTCUSDT", "side": "BUY", "type": "LIMIT", "timeInForce": "IOC",
                       "quantity": "0.1", "price": "100", "newClientOrderId": "synthetic-client"}
        self.catalog = {"source": ENDPOINT, "observed_at": NOW, "tools": [{
            "name": "synthetic_place_tool", "description": "Synthetic Spot placement schema for tests only.",
            "inputSchema": {"type": "object", "additionalProperties": False,
                "properties": {key: {"type": "string"} for key in self.action}, "required": list(self.action)}}]}
        self.binding = {"operation": "SPOT_LIMIT_ORDER", "tool": "synthetic_place_tool",
                        "fields": {key: "/" + key for key in self.action}}

    def bind(self):
        return bind_order(self.action, snapshot()["account"], self.catalog, self.binding, now=NOW)

    def test_exact_decimal_strings_and_tool_name_preserved(self):
        result = self.bind()
        self.assertEqual(result["arguments"], self.action)
        self.assertEqual(result["tool"], "synthetic_place_tool")

    def test_nested_native_schema_and_account_parameter(self):
        schema = self.catalog["tools"][0]["inputSchema"]
        self.catalog["tools"][0]["inputSchema"] = {"type": "object", "properties": {
            "order": schema, "accountId": {"type": "string"}}, "required": ["order", "accountId"]}
        self.binding["fields"] = {key: "/order/" + key for key in self.action}
        self.binding["account_field"] = "/accountId"
        self.assertEqual(self.bind()["arguments"]["order"], self.action)

    def test_missing_mapping_and_unknown_tool_fail(self):
        self.binding["fields"].pop("price")
        with self.assertRaises(SharewellError):
            self.bind()
        self.binding["tool"] = "invented"
        with self.assertRaises(SharewellError):
            self.bind()

    def test_wrong_endpoint_stale_catalog_and_read_only_tool(self):
        original = deepcopy(self.catalog)
        for key, value in (("source", "https://example.com"), ("observed_at", NOW - 300001)):
            self.catalog = {**original, key: value}
            with self.assertRaises(SharewellError):
                self.bind()
        self.catalog = original
        self.catalog["tools"][0]["annotations"] = {"readOnlyHint": True}
        with self.assertRaises(SharewellError):
            self.bind()

    def test_native_number_schema_uses_exact_round_trip(self):
        properties = self.catalog["tools"][0]["inputSchema"]["properties"]
        properties["quantity"] = {"type": "number", "format": "float", "example": 1}
        properties["price"] = {"type": "number", "format": "float", "maximum": 1000}
        result = self.bind()
        self.assertEqual(result["arguments"]["quantity"], 0.1)
        self.assertEqual(result["arguments"]["price"], 100)

    def test_lossy_native_number_is_rejected(self):
        self.catalog["tools"][0]["inputSchema"]["properties"]["quantity"] = {"type": "number"}
        self.action["quantity"] = "0.123456789012345678"
        with self.assertRaisesRegex(SharewellError, "LOSSY_NATIVE_NUMBER"):
            self.bind()

    def test_error_envelope_never_becomes_data(self):
        with self.assertRaises(SharewellError):
            unwrap({"isError": True, "structuredContent": {"balances": []}})
        self.assertEqual(unwrap({"structuredContent": {"balances": []}}), {"balances": []})
        self.assertEqual(unwrap({"content": [{"type": "text", "text": '{"price":"1.2"}'}]}), {"price": "1.2"})

    def test_exact_json_decimal_text_is_preserved(self):
        result = unwrap({"content": [{"type": "text", "text": '{"price":0.12345678901234567890123456789}'}]})
        self.assertEqual(result["price"], "0.12345678901234567890123456789")

    def test_duplicate_keys_nonfinite_and_nested_errors_rejected(self):
        for payload in ('{"price":"1","price":"2"}', '{"price":NaN}',
                        '{"code":-2010,"msg":"rejected"}', '{"data":{"success":false}}'):
            with self.subTest(payload=payload), self.assertRaises(SharewellError):
                unwrap({"content": [{"type": "text", "text": payload}]})
        with self.assertRaises(SharewellError):
            unwrap({"structuredContent": {"price": 0.1}})

    def test_malformed_envelope_and_pointer_rejected(self):
        with self.assertRaises(SharewellError):
            unwrap({"content": [None]})
        self.binding["fields"]["quantity"] = "/bad~2escape"
        with self.assertRaises(SharewellError):
            self.bind()

    def test_unsupported_constraints_and_enum_fail(self):
        with self.assertRaises(SharewellError):
            validate_arguments("BUY", {"type": "string", "enum": ["SELL"]})
        with self.assertRaises(SharewellError):
            validate_arguments("BUY", {"not": {"const": "BUY"}})


class NormalizationTests(unittest.TestCase):
    def capture(self):
        data = snapshot()
        captures = {}
        for name in ("account", "balances", "symbols", "quotes", "open_orders"):
            captures[name] = {"observed_at": NOW, "evidence": "synthetic-" + name,
                              "complete": True, "path": "/data",
                              "pages": [{"structuredContent": {"data": data[name]}}]}
        captures["account"]["fields"] = {"id": "/id", "can_trade": "/can_trade"}
        return {"source": ENDPOINT, "numeraire": "USDT", "captures": captures}

    def test_standard_shapes_and_explicit_wrapper_mapping(self):
        request = self.capture()
        result = normalize_snapshot(request, now=NOW)
        self.assertEqual(result["balances"], snapshot()["balances"])
        self.assertEqual(result["account"], snapshot()["account"])
        self.assertEqual(len(result["evidence"]), 5)

    def test_paginated_balances_preserve_every_asset(self):
        request = self.capture()
        balances = request["captures"]["balances"]
        balances["pages"] = [{"structuredContent": {"data": [row]}} for row in snapshot()["balances"]]
        self.assertEqual(len(normalize_snapshot(request, now=NOW)["balances"]), 2)
        balances["complete"] = False
        with self.assertRaises(SharewellError):
            normalize_snapshot(request, now=NOW)

    def test_missing_mapping_and_duplicate_asset_fail(self):
        request = self.capture()
        request["captures"]["account"]["fields"]["id"] = "/missing"
        with self.assertRaises(SharewellError):
            normalize_snapshot(request, now=NOW)
        request = self.capture()
        request["captures"]["balances"]["pages"] *= 2
        with self.assertRaises(SharewellError):
            normalize_snapshot(request, now=NOW)

    def test_observation_age_not_reset_by_normalization(self):
        request = self.capture()
        request["captures"]["balances"]["observed_at"] = NOW - 100
        self.assertEqual(normalize_snapshot(request, now=NOW)["observed_at"], NOW - 100)
        request["captures"]["balances"]["observed_at"] = NOW - 60001
        with self.assertRaises(SharewellError):
            normalize_snapshot(request, now=NOW)

    def test_native_agentic_account_shape(self):
        request = self.capture()
        request["captures"]["account"]["pages"] = [{"structuredContent": {
            "data": {"uid": 123, "accountType": "SPOT", "canTrade": True}}}]
        request["captures"]["account"]["fields"] = {"id": "/uid", "can_trade": "/canTrade"}
        result = normalize_snapshot(request, now=NOW)
        self.assertEqual(result["account"], {
            "id": "123", "kind": "AGENTIC", "wallet": "SPOT", "can_trade": True})


if __name__ == "__main__":
    unittest.main()

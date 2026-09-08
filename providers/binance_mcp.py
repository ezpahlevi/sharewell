import json
import math
import re
from copy import deepcopy
from decimal import Decimal

from core.schemas import ENDPOINT, SharewellError, asset, canonical, decimal, fresh, integer, require, validate_snapshot


KLINE_INTERVALS = {"1s", "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h",
                   "1d", "3d", "1w", "1M"}
KLINE_FIELDS = ("open_time", "open", "high", "low", "close", "volume", "close_time", "quote_volume",
                "trades", "taker_buy_volume", "taker_buy_quote_volume", "ignore")


def _unique_pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "DUP_JSON_KEY")
        result[key] = value
    return result


def _reject_constant(value):
    raise SharewellError("NONFINITE_JSON")


def _check_payload(value, depth=0):
    require(depth <= 50, "MCP_DEPTH")
    require(type(value) is not float, "FLOAT_RESULT")
    if isinstance(value, dict):
        require("error" not in value and value.get("success") is not False,
                "MCP_PAYLOAD_ERROR")
        if "code" in value:
            code = value["code"]
            require(not (type(code) is int and code < 0), "BINANCE_API_ERROR")
        for item in value.values():
            _check_payload(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _check_payload(item, depth + 1)


def unwrap(result: dict):
    require(isinstance(result, dict), "INVALID_MCP_RESULT")
    require(result.get("isError") is not True and "error" not in result,
            "MCP_RESULT_ERROR")
    if "structuredContent" in result:
        payload = deepcopy(result["structuredContent"])
    else:
        content = result.get("content")
        require(isinstance(content, list) and len(content) == 1 and isinstance(content[0], dict)
                and content[0].get("type") == "text" and isinstance(content[0].get("text"), str),
                "INVALID_CONTENT")
        try:
            payload = json.loads(content[0]["text"], parse_float=str,
                                 parse_constant=_reject_constant, object_pairs_hook=_unique_pairs)
        except json.JSONDecodeError as exc:
            raise SharewellError("INVALID_JSON_TEXT") from exc
    _check_payload(payload)
    return payload


def _parts(pointer: str) -> list[str]:
    require(isinstance(pointer, str) and pointer.startswith("/") and pointer != "/",
            "INVALID_POINTER")
    require(re.search(r"~(?![01])", pointer) is None, "INVALID_POINTER_ESCAPE")
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer[1:].split("/")]
    require(all(parts), "EMPTY_POINTER_PART")
    return parts


def select(payload, pointer: str):
    if pointer == "":
        return payload
    for part in _parts(pointer):
        if isinstance(payload, dict):
            require(part in payload, "MISSING_FIELD")
            payload = payload[part]
        elif isinstance(payload, list):
            require(part.isdigit() and (part == "0" or not part.startswith("0"))
                    and int(part) < len(payload), "INVALID_ARRAY_INDEX")
            payload = payload[int(part)]
        else:
            raise SharewellError("POINTER_SCALAR")
    return payload


def normalize_kline_capture(capture: dict, *, now: int) -> dict:
    require(isinstance(capture, dict), "INVALID_KLINE_CAPTURE")
    require(capture.get("source") == ENDPOINT, "INVALID_SOURCE")
    require(capture.get("tool") == "spot.klines", "INVALID_KLINE_TOOL")
    symbol = asset(capture.get("symbol"))
    interval = capture.get("interval")
    require(interval in KLINE_INTERVALS, "INVALID_KLINE_INTERVAL")
    if interval == "1d":
        require(capture.get("timeZone") == "0", "UNSUPPORTED_HISTORICAL_TIMEZONE")
    evidence = capture.get("evidence")
    require(isinstance(evidence, str) and 0 < len(evidence) <= 200, "INVALID_EVIDENCE")
    observed_at = capture.get("observed_at")
    fresh(observed_at, now)
    payload = unwrap(capture.get("result"))
    require(isinstance(payload, list), "INVALID_KLINE_PAYLOAD")
    candles = []
    seen = set()
    for row in payload:
        require(isinstance(row, list) and len(row) == len(KLINE_FIELDS), "INVALID_KLINE_ROW")
        open_time = integer(row[0], "open_time")
        close_time = integer(row[6], "close_time")
        require(close_time >= open_time, "INVALID_KLINE_TIME")
        values = {field: row[index] for index, field in enumerate(KLINE_FIELDS)}
        for field in ("open", "high", "low", "close", "volume", "quote_volume"):
            decimal(values[field])
        integer(values["trades"], "kline_trades")
        decimal(values["taker_buy_volume"])
        decimal(values["taker_buy_quote_volume"])
        require(isinstance(values["ignore"], str), "INVALID_KLINE_ROW")
        opening = decimal(values["open"])
        high = decimal(values["high"])
        low = decimal(values["low"])
        closing = decimal(values["close"])
        require(0 < low <= opening <= high and low <= closing <= high, "INVALID_KLINE_RANGE")
        require(open_time not in seen, "DUPLICATE_KLINE_TIME")
        seen.add(open_time)
        candles.append({"symbol": symbol, "interval": interval, "open_time": open_time,
                        "close_time": close_time, "open": values["open"], "high": values["high"],
                        "low": values["low"], "close": values["close"], "volume": values["volume"],
                        "quote_volume": values["quote_volume"]})
    candles.sort(key=lambda item: item["open_time"])
    requested_start = capture.get("requested_start")
    requested_end = capture.get("requested_end")
    if requested_start is not None:
        integer(requested_start, "requested_start")
    if requested_end is not None:
        integer(requested_end, "requested_end")
    require(requested_start is None or requested_end is None or requested_start <= requested_end,
            "INVALID_KLINE_RANGE")
    complete = bool(candles) and candles[-1]["close_time"] <= observed_at
    if requested_start is not None:
        complete = complete and bool(candles) and candles[0]["open_time"] <= requested_start
    if requested_end is not None:
        complete = complete and bool(candles) and candles[-1]["close_time"] >= requested_end
    result = {"source": ENDPOINT, "tool": capture["tool"], "symbol": symbol, "interval": interval,
              "observed_at": observed_at, "evidence": evidence, "candles": candles,
              "complete": complete}
    if interval == "1d":
        result["time_zone"] = "0"
    if requested_start is not None:
        result["requested_start"] = requested_start
    if requested_end is not None:
        result["requested_end"] = requested_end
    return result


def normalize_snapshot(request: dict, *, now: int) -> dict:
    require(isinstance(request, dict) and request.get("source") == ENDPOINT,
            "INVALID_SOURCE")
    captures = request.get("captures")
    require(isinstance(captures, dict), "MISSING_CAPTURES")
    evidence, times = [], []

    def read(name, *, paged=False):
        capture = captures.get(name)
        require(isinstance(capture, dict), "MISSING_CAPTURE")
        require(isinstance(capture.get("evidence"), str) and 0 < len(capture["evidence"]) <= 200,
                "INVALID_EVIDENCE")
        fresh(capture.get("observed_at"), now)
        evidence.append(capture["evidence"])
        times.append(capture["observed_at"])
        pages = capture.get("pages")
        require(isinstance(pages, list) and bool(pages), "MISSING_PAGES")
        require(capture.get("complete") is True, "INCOMPLETE_CAPTURE")
        if not paged:
            require(len(pages) == 1, "MULTIPLE_SINGLE_PAGES")
        rows = []
        for page in pages:
            value = select(unwrap(page), capture.get("path", ""))
            if paged:
                require(isinstance(value, list), "EXPECTED_ARRAY")
                rows.extend(value)
            else:
                return value, capture
        return rows, capture

    def rows(name, required, *, extras=False):
        values, capture = read(name, paged=True)
        fields = capture.get("fields")
        if fields is None:
            return deepcopy(values)
        require(isinstance(fields, dict) and set(required) <= set(fields), "MISSING_FIELD_MAP")
        output = []
        for value in values:
            require(isinstance(value, dict), "EXPECTED_OBJECT_ROW")
            row = deepcopy(value) if extras else {}
            for key, path in fields.items():
                row[key] = select(value, path)
            output.append(row)
        return output

    account_value, capture = read("account")
    fields = capture.get("fields")
    require(isinstance(fields, dict) and set(fields) == {"id", "can_trade"}, "INVALID_ACCOUNT_MAP")
    account_id = select(account_value, fields["id"])
    require(type(account_id) in {int, str} and str(account_id), "INVALID_ACCOUNT_ID")
    account = {"id": str(account_id), "kind": "AGENTIC", "wallet": "SPOT",
               "can_trade": select(account_value, fields["can_trade"])}
    balances = rows("balances", {"asset", "free", "locked"})
    symbols = rows("symbols", {"symbol", "baseAsset", "quoteAsset", "filters"}, extras=True)
    quotes = rows("quotes", {"symbol", "bidPrice", "askPrice"})
    for quote in quotes:
        quote["observed_at"] = captures["quotes"]["observed_at"]
    orders = rows("open_orders", {"symbol", "side", "origQty"}, extras=True)
    result = {"version": 1, "source": ENDPOINT, "observed_at": min(times), "account": account,
              "numeraire": request.get("numeraire"), "balances": balances, "balances_complete": True,
              "symbols": symbols, "quotes": quotes, "open_orders": orders,
              "open_orders_complete": True, "evidence": evidence}
    if "exchange_filters" in captures:
        result["exchange_filters"] = rows("exchange_filters", {"filterType"}, extras=True)
    if "asset_filters" in captures:
        result["asset_filters"] = rows("asset_filters", {"filterType", "asset", "limit"}, extras=True)
    if "execution_rules" in captures:
        result["execution_rules"] = rows("execution_rules", {"symbol", "rules"}, extras=True)
    if "account_permissions" in captures:
        result["account_permissions"], _ = read("account_permissions")
    if "filter_references" in captures:
        result["filter_references"], _ = read("filter_references")
    result["observed_at"] = min(times)
    return validate_snapshot(result, now)


def validate_arguments(value, schema: dict, root: dict | None = None, depth=0):
    require(isinstance(schema, dict) and depth <= 20, "INVALID_TOOL_SCHEMA")
    root = schema if root is None else root
    annotations = {"title", "description", "default", "example", "examples", "$schema", "$id", "$defs",
                   "definitions", "deprecated", "format"}
    supported = {"type", "properties", "required", "additionalProperties", "enum", "const", "items",
                 "minItems", "maxItems", "minLength", "maxLength", "pattern", "anyOf", "oneOf", "$ref",
                 "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"}
    require(set(schema) <= annotations | supported, "UNSUPPORTED_TOOL_SCHEMA")
    if "$ref" in schema:
        ref = schema["$ref"]
        require(isinstance(ref, str) and ref.startswith("#/"), "INVALID_SCHEMA_REF")
        target = root
        for part in _parts(ref[1:]):
            require(isinstance(target, dict) and part in target, "UNRESOLVED_SCHEMA_REF")
            target = target[part]
        validate_arguments(value, target, root, depth + 1)
    for combiner in ("anyOf", "oneOf"):
        if combiner in schema:
            successes = 0
            for candidate in schema[combiner]:
                try:
                    validate_arguments(value, candidate, root, depth + 1)
                    successes += 1
                except SharewellError:
                    pass
            require(successes == 1 if combiner == "oneOf" else successes >= 1, "SCHEMA_ALTERNATIVE")
    if "enum" in schema:
        require(any(canonical(value) == canonical(item) for item in schema["enum"]), "SCHEMA_ENUM")
    if "const" in schema:
        require(canonical(value) == canonical(schema["const"]), "SCHEMA_CONST")
    types = {"object": isinstance(value, dict), "array": isinstance(value, list),
             "string": isinstance(value, str), "integer": type(value) is int,
             "number": type(value) in {int, float} and math.isfinite(value),
             "boolean": type(value) is bool, "null": value is None}
    if "type" in schema:
        accepted = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        require(any(types.get(kind, False) for kind in accepted), "SCHEMA_TYPE")
    if isinstance(value, dict):
        require(set(schema.get("required", [])) <= set(value), "SCHEMA_REQUIRED")
        properties = schema.get("properties", {})
        extra = schema.get("additionalProperties", True)
        for key, item in value.items():
            if key in properties:
                validate_arguments(item, properties[key], root, depth + 1)
            elif isinstance(extra, dict):
                validate_arguments(item, extra, root, depth + 1)
            else:
                require(extra is True, "SCHEMA_EXTRA_FIELD")
    if isinstance(value, str):
        require(schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", len(value)), "SCHEMA_STRING_LENGTH")
        if "pattern" in schema:
            require(re.search(schema["pattern"], value) is not None, "SCHEMA_PATTERN")
    if isinstance(value, list):
        require(schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", len(value)), "SCHEMA_ARRAY_LENGTH")
        for item in value:
            if "items" in schema:
                validate_arguments(item, schema["items"], root, depth + 1)
    if type(value) in {int, float}:
        number = Decimal(str(value))
        require("minimum" not in schema or number >= Decimal(str(schema["minimum"])), "SCHEMA_MINIMUM")
        require("maximum" not in schema or number <= Decimal(str(schema["maximum"])), "SCHEMA_MAXIMUM")
        require("exclusiveMinimum" not in schema or number > Decimal(str(schema["exclusiveMinimum"])), "SCHEMA_EXCLUSIVE_MIN")
        require("exclusiveMaximum" not in schema or number < Decimal(str(schema["exclusiveMaximum"])), "SCHEMA_EXCLUSIVE_MAX")
        require("multipleOf" not in schema or number % Decimal(str(schema["multipleOf"])) == 0, "SCHEMA_MULTIPLE")


def native_arguments(value, schema: dict):
    if schema.get("type") == "number" and isinstance(value, str):
        exact = decimal(value)
        if exact == exact.to_integral_value():
            return int(exact)
        converted = float(value)
        require(math.isfinite(converted) and Decimal(str(converted)) == exact, "LOSSY_NATIVE_NUMBER")
        return converted
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        return {key: native_arguments(item, properties.get(key, {})) for key, item in value.items()}
    if isinstance(value, list) and "items" in schema:
        return [native_arguments(item, schema["items"]) for item in value]
    return value


def bind_order(action: dict, account: dict, catalog: dict, binding: dict, *, now: int) -> dict:
    require(all(isinstance(value, dict) for value in (action, account, catalog, binding)),
            "INVALID_BIND_INPUT")
    require(catalog.get("source") == ENDPOINT, "INVALID_SOURCE")
    fresh(catalog.get("observed_at"), now, max_age=300_000)
    require(binding.get("operation") == "SPOT_LIMIT_ORDER", "INVALID_BIND_OPERATION")
    tools = catalog.get("tools")
    require(isinstance(tools, list) and all(isinstance(tool, dict) for tool in tools),
            "INVALID_TOOL_CATALOG")
    matches = [tool for tool in tools if tool.get("name") == binding.get("tool")]
    require(len(matches) == 1, "PLACEMENT_TOOL_NOT_UNIQUE")
    tool = matches[0]
    require(isinstance(tool.get("name"), str) and bool(tool["name"]), "MISSING_TOOL_NAME")
    require(isinstance(tool.get("annotations", {}), dict), "INVALID_TOOL_ANNOTATIONS")
    require(tool.get("annotations", {}).get("readOnlyHint") is not True, "READ_ONLY_TOOL")
    require(bool(tool.get("description")), "MISSING_TOOL_DESCRIPTION")
    require(set(action) == {"symbol", "side", "type", "timeInForce", "quantity", "price", "newClientOrderId"},
            "INVALID_ACTION_FIELDS")
    require(action["type"] == "LIMIT" and action["timeInForce"] == "IOC", "INVALID_ORDER_MODE")
    fields = binding.get("fields")
    require(isinstance(fields, dict) and set(action) == set(fields), "INVALID_BIND_FIELDS")
    values = [(fields[key], value) for key, value in action.items()]
    if "account_field" in binding:
        values.append((binding["account_field"], account["id"]))
    arguments = {}
    for pointer, value in values:
        parts = _parts(pointer)
        cursor = arguments
        for part in parts[:-1]:
            cursor = cursor.setdefault(part, {})
            require(isinstance(cursor, dict), "OVERLAPPING_BIND")
        require(parts[-1] not in cursor, "DUPLICATE_BIND")
        cursor[parts[-1]] = value
    arguments = native_arguments(arguments, tool.get("inputSchema"))
    validate_arguments(arguments, tool.get("inputSchema"))
    return {"tool": tool["name"], "arguments": arguments, "source": ENDPOINT,
            "account": deepcopy(account), "confirmation": "BINANCE_CONFIRMATION_REQUIRED"}

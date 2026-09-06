from __future__ import annotations

import hashlib
import json
import re
import time
from decimal import Decimal, InvalidOperation, getcontext

getcontext().prec = 80
ENDPOINT = "https://agent.binance.com/mcp/agentic"
ZERO = Decimal(0)
ONE = Decimal(1)


class SharewellError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SharewellError(message)


def decimal(value: object) -> Decimal:
    require(isinstance(value, str), "INVALID_DECIMAL_TYPE")
    require(len(value) <= 100 and re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value) is not None,
            "INVALID_DECIMAL_TEXT")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise SharewellError("INVALID_DECIMAL") from exc
    require(result.is_finite() and result >= ZERO, "INVALID_DECIMAL_RANGE")
    require(len(result.as_tuple().digits) <= 60, "DECIMAL_PRECISION")
    return result


def text(value: Decimal) -> str:
    result = format(value, "f")
    return result.rstrip("0").rstrip(".") if "." in result else result


def asset(value: object) -> str:
    require(isinstance(value, str) and re.fullmatch(r"[A-Z0-9]{1,32}", value) is not None,
            "INVALID_ASSET")
    return value


def integer(value: object, label: str) -> int:
    require(type(value) is int and value >= 0, "INVALID_" + label.upper())
    return value


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def fresh(timestamp: object, now: int, max_age: int = 60_000) -> None:
    timestamp = integer(timestamp, "observed_at")
    require(0 <= now - timestamp <= max_age, "STALE_EVIDENCE")


def validate_snapshot(data: dict, now: int | None = None) -> dict:
    require(isinstance(data, dict) and type(data.get("version")) is int
            and data["version"] == 1, "INVALID_SNAPSHOT_VERSION")
    now = now_ms() if now is None else now
    require(data.get("source") == ENDPOINT, "INVALID_SOURCE")
    fresh(data.get("observed_at"), now)
    account = data.get("account", {})
    require(isinstance(account, dict), "INVALID_ACCOUNT")
    require(isinstance(account.get("id"), str) and 0 < len(account["id"]) <= 128,
            "INVALID_ACCOUNT_ID")
    require(account.get("kind") in ("AGENTIC", "MAIN_READ_ONLY"), "INVALID_ACCOUNT_KIND")
    require(account.get("wallet") == "SPOT", "INVALID_WALLET")
    require(type(account.get("can_trade")) is bool, "INVALID_TRADE_PERMISSION")
    asset(data.get("numeraire"))
    balances = data.get("balances")
    require(isinstance(balances, list), "INVALID_BALANCES")
    require(data.get("balances_complete") is True, "INCOMPLETE_BALANCES")
    seen = set()
    for row in balances:
        require(isinstance(row, dict), "INVALID_BALANCE")
        name = asset(row.get("asset"))
        require(name not in seen, "DUP_BALANCE_ASSET")
        seen.add(name)
        decimal(row.get("free"))
        decimal(row.get("locked"))
    require(isinstance(data.get("symbols"), list), "INVALID_SYMBOLS")
    seen = set()
    for row in data["symbols"]:
        require(isinstance(row, dict), "INVALID_SYMBOL")
        symbol = asset(row.get("symbol"))
        require(symbol not in seen, "DUP_SYMBOL")
        seen.add(symbol)
        require(asset(row.get("baseAsset")) != asset(row.get("quoteAsset")), "SELF_PAIR")
        require(isinstance(row.get("filters"), list), "INVALID_SYMBOL_FILTERS")
    require(isinstance(data.get("quotes"), list), "INVALID_QUOTES")
    seen = set()
    for row in data["quotes"]:
        require(isinstance(row, dict), "INVALID_QUOTE")
        symbol = asset(row.get("symbol"))
        require(symbol not in seen, "DUP_QUOTE")
        seen.add(symbol)
        bid, ask = decimal(row.get("bidPrice")), decimal(row.get("askPrice"))
        require(ZERO < bid <= ask, "INVALID_QUOTE_RANGE")
        fresh(row.get("observed_at"), now)
    require(isinstance(data.get("open_orders"), list) and data.get("open_orders_complete") is True,
            "INCOMPLETE_OPEN_ORDERS")
    require(isinstance(data.get("evidence"), list) and bool(data["evidence"]),
            "MISSING_EVIDENCE")
    for ref in data["evidence"]:
        require(isinstance(ref, str) and 0 < len(ref) <= 200, "INVALID_EVIDENCE")
    execution_rules = data.get("execution_rules", [])
    require(isinstance(execution_rules, list), "INVALID_EXECUTION_RULES")
    seen = set()
    for row in execution_rules:
        require(isinstance(row, dict), "INVALID_EXECUTION_RULES")
        symbol = asset(row.get("symbol"))
        require(symbol not in seen, "DUP_EXECUTION_RULES")
        seen.add(symbol)
        rules = row.get("rules")
        require(isinstance(rules, list), "INVALID_EXECUTION_RULES")
        for rule in rules:
            require(isinstance(rule, dict) and rule.get("ruleType") == "PRICE_RANGE",
                    "UNSUPPORTED_EXECUTION_RULE")
            for key in ("bidLimitMultUp", "bidLimitMultDown", "askLimitMultUp", "askLimitMultDown"):
                if key in rule:
                    decimal(rule[key])
    return data

from decimal import Decimal
from fractions import Fraction

from .schemas import ZERO, decimal, fresh, integer, require


def multiple(value: Decimal | Fraction, step: Decimal, *, up: bool = False) -> Decimal:
    require(value >= ZERO and step >= ZERO, "NEGATIVE_ROUNDING")
    if step == ZERO:
        require(isinstance(value, Decimal), "MISSING_QUANTITY_STEP")
        return value
    ratio = Fraction(value) / Fraction(step)
    units, remainder = divmod(ratio.numerator, ratio.denominator)
    if up and remainder:
        units += 1
    _, digits, exponent = step.as_tuple()
    coefficient = int("".join(str(digit) for digit in digits)) * units
    return Decimal((0, tuple(int(digit) for digit in str(coefficient)), exponent))


def filter_map(symbol: dict) -> dict[str, dict]:
    result = {}
    for row in symbol["filters"]:
        require(isinstance(row, dict) and isinstance(row.get("filterType"), str),
                "INVALID_SYMBOL_FILTER")
        require(row["filterType"] not in result, "DUP_SYMBOL_FILTER")
        result[row["filterType"]] = row
    require("PRICE_FILTER" in result and "LOT_SIZE" in result,
            "MISSING_CORE_FILTERS")
    return result


def validate_execution_rules(symbol: dict, side: str, price: Decimal,
                             snapshot: dict, now: int) -> None:
    matches = [row for row in snapshot.get("execution_rules", [])
               if row.get("symbol") == symbol["symbol"]]
    require(len(matches) <= 1, "DUP_EXECUTION_RULES")
    if not matches:
        return
    rules = matches[0].get("rules")
    require(isinstance(rules, list), "INVALID_EXECUTION_RULES")
    for rule in rules:
        require(isinstance(rule, dict) and rule.get("ruleType") == "PRICE_RANGE",
                "UNSUPPORTED_EXECUTION_RULE")
        reference = snapshot.get("filter_references", {}).get(symbol["symbol"], {}).get("PRICE_RANGE")
        require(isinstance(reference, dict), "MISSING_PRICE_RANGE_REF")
        fresh(reference.get("observed_at"), now)
        if reference.get("price") is None:
            continue
        require(reference.get("basis") == "REFERENCE_PRICE", "INVALID_PRICE_RANGE_REF")
        basis = decimal(reference["price"])
        require(basis > ZERO, "INVALID_PRICE_RANGE_REF")
        if side == "BUY" and "bidLimitMultDown" in rule:
            require(price >= basis * decimal(rule["bidLimitMultDown"]), "PRICE_RANGE_UNREACHABLE")
        if side == "SELL" and "askLimitMultUp" in rule:
            require(price <= basis * decimal(rule["askLimitMultUp"]), "PRICE_RANGE_UNREACHABLE")


def validate_limit(symbol: dict, side: str, quantity: Decimal, price: Decimal,
                   snapshot: dict, now: int) -> None:
    require(side in ("BUY", "SELL"), "INVALID_ORDER_SIDE")
    require(symbol.get("status") == "TRADING"
            and symbol.get("isSpotTradingAllowed") is True
            and "LIMIT" in symbol.get("orderTypes", []), "SYMBOL_NOT_TRADABLE")
    require(quantity > ZERO and price > ZERO, "INVALID_ORDER_AMOUNT")
    permissions = symbol.get("permissionSets", [])
    require(isinstance(permissions, list), "INVALID_PERMISSION_SETS")
    if permissions:
        granted = snapshot.get("account_permissions")
        require(isinstance(granted, list) and all(isinstance(value, str) for value in granted),
                "MISSING_ACCOUNT_PERMISSIONS")
        for alternatives in permissions:
            require(isinstance(alternatives, list) and bool(alternatives)
                    and all(isinstance(value, str) for value in alternatives), "INVALID_PERMISSION_GROUP")
            require(bool(set(alternatives) & set(granted)), "MISSING_SYMBOL_PERMISSION")
    for rule in snapshot.get("asset_filters", []):
        require(isinstance(rule, dict) and rule.get("filterType") == "MAX_ASSET", "INVALID_ASSET_FILTER")
        if rule.get("asset") == symbol["baseAsset"]:
            require(quantity <= decimal(rule.get("limit")), "MAX_ASSET_BASE")
        elif rule.get("asset") == symbol["quoteAsset"]:
            require(quantity * price <= decimal(rule.get("limit")), "MAX_ASSET_QUOTE")
    filters = filter_map(symbol)
    inactive = {"MARKET_LOT_SIZE", "ICEBERG_PARTS", "MAX_NUM_ALGO_ORDERS",
                "MAX_NUM_ICEBERG_ORDERS", "TRAILING_DELTA", "MAX_NUM_ORDER_AMENDS",
                "MAX_NUM_ORDER_LISTS"}
    for kind, rule in filters.items():
        if kind in inactive:
            continue
        if kind in ("PRICE_FILTER", "LOT_SIZE"):
            value = price if kind == "PRICE_FILTER" else quantity
            low, high, step = (("minPrice", "maxPrice", "tickSize")
                               if kind == "PRICE_FILTER" else ("minQty", "maxQty", "stepSize"))
            minimum, maximum, increment = (decimal(rule.get(key)) for key in (low, high, step))
            if kind == "PRICE_FILTER":
                require((minimum == ZERO or value >= minimum)
                        and (maximum == ZERO or value <= maximum)
                        and (increment == ZERO or value % increment == ZERO), "PRICE_FILTER")
            else:
                require(minimum <= value <= maximum and increment > ZERO
                        and value % increment == ZERO, "LOT_SIZE")
        elif kind in ("MIN_NOTIONAL", "NOTIONAL"):
            require(price * quantity >= decimal(rule.get("minNotional")), "MIN_NOTIONAL")
            if kind == "NOTIONAL":
                require(price * quantity <= decimal(rule.get("maxNotional")), "MAX_NOTIONAL")
        elif kind in ("PERCENT_PRICE", "PERCENT_PRICE_BY_SIDE"):
            references = snapshot.get("filter_references", {}).get(symbol["symbol"], {})
            reference = references.get(kind)
            require(isinstance(reference, dict), "MISSING_FILTER_REFERENCE")
            fresh(reference.get("observed_at"), now)
            require(reference.get("basis") in ("REFERENCE_PRICE", "WEIGHTED_AVERAGE", "LAST_PRICE"),
                    "INVALID_REFERENCE_BASIS")
            if reference["basis"] != "REFERENCE_PRICE":
                minutes = integer(rule.get("avgPriceMins"), "avgPriceMins")
                require(reference.get("avgPriceMins") == minutes,
                        "INVALID_AVG_WINDOW")
                require(reference["basis"] == ("LAST_PRICE" if minutes == 0 else "WEIGHTED_AVERAGE"),
                        "INVALID_PRICE_BASIS")
                require(reference.get("reference_price_absent") is True,
                        "UNVERIFIED_PRICE_FALLBACK")
            base = decimal(reference.get("price"))
            require(base > ZERO, "INVALID_FILTER_REFERENCE")
            prefix = "" if kind == "PERCENT_PRICE" else ("bid" if side == "BUY" else "ask")
            down = "multiplierDown" if not prefix else prefix + "MultiplierDown"
            up = "multiplierUp" if not prefix else prefix + "MultiplierUp"
            require(base * decimal(rule.get(down)) <= price <= base * decimal(rule.get(up)),
                    "PERCENT_PRICE")
        elif kind == "MAX_NUM_ORDERS":
            count = sum(row["symbol"] == symbol["symbol"] for row in snapshot["open_orders"])
            require(count < integer(rule.get("maxNumOrders"), "maxNumOrders"), "MAX_NUM_ORDERS")
        elif kind == "MAX_POSITION":
            if side == "BUY":
                held = sum((decimal(row["free"]) + decimal(row["locked"])
                            for row in snapshot["balances"] if row["asset"] == symbol["baseAsset"]), ZERO)
                same_base = {row["symbol"] for row in snapshot["symbols"]
                             if row["baseAsset"] == symbol["baseAsset"]}
                pending = sum((decimal(row["origQty"]) for row in snapshot["open_orders"]
                               if row["symbol"] in same_base and row["side"] == "BUY"), ZERO)
                require(held + pending + quantity <= decimal(rule.get("maxPosition")), "MAX_POSITION")
        else:
            require(False, "UNSUPPORTED_SYMBOL_FILTER")
    for rule in snapshot.get("exchange_filters", []):
        kind = rule.get("filterType")
        if kind == "EXCHANGE_MAX_NUM_ORDERS":
            require(len(snapshot["open_orders"]) < integer(rule.get("maxNumOrders"), "maxNumOrders"),
                    "EXCHANGE_MAX_NUM_ORDERS")
        else:
            require(kind in {"EXCHANGE_MAX_NUM_ALGO_ORDERS", "EXCHANGE_MAX_NUM_ICEBERG_ORDERS",
                             "EXCHANGE_MAX_NUM_ORDER_LISTS"},
                    "UNSUPPORTED_EXCHANGE_FILTER")
    validate_execution_rules(symbol, side, price, snapshot, now)

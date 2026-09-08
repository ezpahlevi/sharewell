from decimal import Decimal, InvalidOperation

from .schemas import SharewellError, digest, require, text


MIN_ROUTE_OBSERVATIONS = 3
COMPARABLE_BASIS = "INITIAL_QUOTE_TOUCH"


def signed_decimal(value):
    require(isinstance(value, (str, Decimal)), "INVALID_LEARNED_VALUE")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise SharewellError("INVALID_LEARNED_VALUE") from exc
    require(result.is_finite() and len(result.as_tuple().digits) <= 80, "INVALID_LEARNED_VALUE")
    return result


def route_name(route) -> str:
    symbols = [edge["symbol"] if isinstance(edge, dict) else edge for edge in route]
    require(all(isinstance(symbol, str) and symbol for symbol in symbols), "INVALID_ROUTE")
    return "|".join(symbols)


def _rows(preferences):
    if preferences is None:
        return []
    if isinstance(preferences, dict):
        return [{"key": key, **value} for key, value in preferences.items()]
    require(isinstance(preferences, list), "INVALID_LEARNED_PREFERENCES")
    return preferences


def _route_preferences(preferences):
    result = {}
    for row in _rows(preferences):
        require(isinstance(row, dict), "INVALID_LEARNED_PREFERENCE")
        key = row.get("key")
        if not isinstance(key, str) or not key.startswith("route_penalty:"):
            continue
        count = row.get("sample_count", 0)
        value = row.get("value", {})
        if isinstance(value, str):
            value = {"penalty_bps": value}
        require(isinstance(value, dict), "INVALID_LEARNED_PREFERENCE")
        if type(count) is int and count >= MIN_ROUTE_OBSERVATIONS and isinstance(value.get("penalty_bps"), str):
            result[key] = {"penalty_bps": signed_decimal(value["penalty_bps"]), "sample_count": count}
    return result


def route_penalty(route, preferences):
    rows = _route_preferences(preferences)
    penalties = []
    keys = []
    for edge in route:
        key = "route_penalty:" + route_name([edge])
        if key in rows:
            penalties.append(rows[key])
            keys.append(key)
    if not penalties:
        return None
    return {"penalty_bps": sum((row["penalty_bps"] for row in penalties), Decimal(0)),
            "observations": sum(row["sample_count"] for row in penalties), "keys": keys}


def active_preferences(preferences):
    rows = _rows(preferences)
    return [row for row in rows if isinstance(row, dict) and row.get("key", "").startswith("route_penalty:")
            and type(row.get("sample_count")) is int and row["sample_count"] >= MIN_ROUTE_OBSERVATIONS]


def observations_from_evaluation(proposal: dict, evaluation: dict) -> list[dict]:
    results = evaluation.get("results", [evaluation]) if isinstance(evaluation, dict) else []
    execution = next((result for result in results if result.get("evaluator_id") == "execution_quality"), None)
    if not execution or execution.get("status") not in {"PASS", "PARTIAL"}:
        return []
    observations = []
    for row in execution.get("metrics", {}).get("orders", []):
        slippage = row.get("realized_slippage_bps")
        if (slippage is None or row.get("learning_eligible") is not True or
                row.get("slippage_basis") != COMPARABLE_BASIS):
            continue
        index = row.get("index")
        require(type(index) is int and 0 <= index < len(proposal["orders"]), "INVALID_LEARNING_INPUT")
        symbol = proposal["orders"][index]["symbol"]
        identity = {"proposal_hash": proposal["hash"], "index": index,
                    "client_order_id": row.get("client_order_id"),
                    "order_id": row.get("order_id"), "trade_ids": row.get("trade_ids")}
        require(isinstance(identity["client_order_id"], str) and identity["client_order_id"],
                "INVALID_LEARNING_INPUT")
        require(isinstance(identity["order_id"], str) and identity["order_id"], "INVALID_LEARNING_INPUT")
        require(isinstance(identity["trade_ids"], list) and
                all(isinstance(item, str) and item for item in identity["trade_ids"]),
                "INVALID_LEARNING_INPUT")
        observations.append({"observation_id": digest(identity), "key": "route_penalty:" + symbol,
                             "value": signed_decimal(slippage),
                             "evaluator_id": execution["evaluator_id"], "version": execution["version"],
                             "parameters": execution["parameters"], "input_hash": execution["input_hash"],
                             "evidence": execution["evidence"]})
    return observations


def aggregate(old_value: dict | None, old_count: int, observation: dict) -> tuple[dict, int, int]:
    old_penalty = Decimal(old_value.get("penalty_bps", "0")) if old_value else Decimal(0)
    count = old_count + 1
    penalty = (old_penalty * old_count + observation["value"]) / count
    value = {"penalty_bps": text(penalty), "evaluator_id": observation["evaluator_id"],
             "version": observation["version"], "parameters": observation["parameters"],
             "input_hash": observation["input_hash"], "evidence": observation["evidence"]}
    return value, count, len(observation["evidence"])

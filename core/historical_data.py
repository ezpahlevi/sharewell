from collections import defaultdict
from decimal import Decimal

from .schemas import ONE, asset, decimal, integer, require, text


DAY_MS = 86_400_000


def _request(assets, numeraire, as_of, windows_days):
    require(isinstance(assets, list) and bool(assets), "INVALID_HISTORICAL_ASSETS")
    names = [asset(value) for value in assets]
    require(len(set(names)) == len(names), "DUPLICATE_HISTORICAL_ASSET")
    numeraire = asset(numeraire)
    integer(as_of, "as_of")
    require(isinstance(windows_days, list) and bool(windows_days) and
            all(type(value) is int and value > 0 for value in windows_days) and
            len(set(windows_days)) == len(windows_days), "INVALID_HISTORICAL_WINDOWS")
    return sorted(names), numeraire, as_of, sorted(windows_days)


def _capture(capture):
    require(isinstance(capture, dict), "INVALID_NORMALIZED_KLINE")
    source = capture.get("source")
    require(isinstance(source, str) and 0 < len(source) <= 200, "INVALID_HISTORICAL_SOURCE")
    symbol = asset(capture.get("symbol"))
    require(capture.get("interval") == "1d", "UNSUPPORTED_HISTORICAL_INTERVAL")
    evidence = capture.get("evidence")
    if isinstance(evidence, str):
        evidence = [evidence]
    require(isinstance(evidence, list) and bool(evidence) and
            all(isinstance(item, str) and 0 < len(item) <= 200 for item in evidence),
            "INVALID_EVIDENCE")
    observed_at = integer(capture.get("observed_at"), "observed_at")
    candles = capture.get("candles")
    require(isinstance(candles, list), "INVALID_NORMALIZED_KLINE")
    require(type(capture.get("complete")) is bool, "INVALID_KLINE_COMPLETENESS")
    requested_start = capture.get("requested_start")
    requested_end = capture.get("requested_end")
    if requested_start is not None:
        integer(requested_start, "requested_start")
    if requested_end is not None:
        integer(requested_end, "requested_end")
    require(requested_start is None or requested_end is None or requested_start <= requested_end,
            "INVALID_KLINE_RANGE")
    return (source, symbol, list(dict.fromkeys(evidence)), candles, capture["complete"], observed_at,
            requested_start, requested_end)


def _points(capture, as_of):
    source, symbol, evidence, candles, complete, observed_at, requested_start, requested_end = _capture(capture)
    result = []
    seen = set()
    for candle in candles:
        require(isinstance(candle, dict), "INVALID_NORMALIZED_CANDLE")
        require(candle.get("symbol") == symbol and candle.get("interval") == "1d",
                "MIXED_KLINE_METADATA")
        open_time = integer(candle.get("open_time"), "open_time")
        close_time = integer(candle.get("close_time"), "close_time")
        require(close_time >= open_time, "INVALID_KLINE_TIME")
        require(open_time not in seen, "DUPLICATE_KLINE_TIME")
        seen.add(open_time)
        price = candle.get("close")
        require(isinstance(price, str) and decimal(price) > 0, "INVALID_KLINE_CLOSE")
        if close_time <= min(as_of, observed_at):
            result.append((close_time, price))
    result.sort()
    incomplete = False
    if requested_start is not None:
        incomplete = not result or result[0][0] > requested_start
    if requested_end is not None:
        incomplete = incomplete or not result or result[-1][0] < requested_end
    return {"source": source, "symbol": symbol, "evidence": evidence, "points": result,
            "complete": complete, "incomplete": incomplete}


def build_price_history(captures: list[dict], *, assets: list[str], numeraire: str,
                        as_of: int, windows_days: list[int]) -> dict:
    names, numeraire, as_of, windows_days = _request(assets, numeraire, as_of, windows_days)
    require(isinstance(captures, list), "INVALID_HISTORICAL_CAPTURES")
    expected = {name: {name + numeraire, numeraire + name} for name in names if name != numeraire}
    parsed = []
    seen_symbols = set()
    for capture in captures:
        item = _points(capture, as_of)
        require(item["symbol"] in {symbol for values in expected.values() for symbol in values},
                "UNEXPECTED_HISTORICAL_SYMBOL")
        require(item["symbol"] not in seen_symbols, "DUPLICATE_HISTORICAL_PAIR")
        seen_symbols.add(item["symbol"])
        parsed.append(item)
    by_asset = defaultdict(list)
    routes = {}
    incomplete = set()
    evidence = []
    timelines = []
    for name in names:
        if name == numeraire:
            routes[name] = "IDENTITY"
            continue
        direct = name + numeraire
        inverse = numeraire + name
        matches = [item for item in parsed if item["symbol"] in (direct, inverse)]
        if not matches:
            routes[name] = "UNAVAILABLE"
            continue
        item = matches[0]
        route = "DIRECT" if item["symbol"] == direct else "INVERSE"
        routes[name] = route
        if item["incomplete"]:
            incomplete.add(name)
        evidence.extend(item["evidence"])
        timelines.extend(observed_at for observed_at, _ in item["points"])
        for observed_at, price in item["points"]:
            value = price if route == "DIRECT" else text(ONE / decimal(price))
            by_asset[name].append({"asset": name, "observed_at": observed_at, "price": value})
    if numeraire in names:
        for observed_at in sorted(set(timelines)):
            by_asset[numeraire].append({"asset": numeraire, "observed_at": observed_at, "price": "1"})
    for name in by_asset:
        by_asset[name].sort(key=lambda row: row["observed_at"])
    available = sorted(name for name in names if by_asset.get(name))
    missing = sorted(set(names) - set(available))
    return {"source": next((item["source"] for item in parsed), None), "as_of": as_of,
            "numeraire": numeraire, "requested_assets": names, "windows_days": windows_days,
            "price_history": [row for name in sorted(by_asset) for row in by_asset[name]],
            "evidence": list(dict.fromkeys(evidence)),
            "coverage": {"requested_assets": names, "available_assets": available,
                         "missing_assets": missing, "incomplete_assets": sorted(incomplete),
                         "routes": routes, "required_start": as_of - max(windows_days) * DAY_MS}}

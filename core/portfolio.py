from collections import deque
from decimal import Decimal

from .schemas import ONE, ZERO, SharewellError, asset, decimal, require, text, validate_snapshot


def spot_symbol(row: dict) -> bool:
    return row.get("status") == "TRADING" and row.get("isSpotTradingAllowed") is True


class Market:
    def __init__(self, snapshot: dict, blocked_assets=None):
        self.blocked_assets = set(blocked_assets or ())
        self.symbols = {row["symbol"]: row for row in snapshot["symbols"] if spot_symbol(row)}
        self.quotes = {row["symbol"]: row for row in snapshot["quotes"]}
        self.edges: dict[str, list[dict]] = {}
        for name, symbol in sorted(self.symbols.items()):
            if name not in self.quotes:
                continue
            bid = decimal(self.quotes[name]["bidPrice"])
            ask = decimal(self.quotes[name]["askPrice"])
            mid = (bid + ask) / 2
            for source, dest, side, rate, midrate in (
                (symbol["baseAsset"], symbol["quoteAsset"], "SELL", bid, mid),
                (symbol["quoteAsset"], symbol["baseAsset"], "BUY", ONE / ask, ONE / mid),
            ):
                if source in self.blocked_assets or dest in self.blocked_assets:
                    continue
                self.edges.setdefault(source, []).append({"symbol": name, "source": source,
                    "dest": dest, "side": side, "rate": rate, "midrate": midrate})

    def path(self, source: str, dest: str, executable: bool = False) -> list[dict]:
        queue = deque([(source, [])])
        seen = {source}
        while queue:
            current, route = queue.popleft()
            if current == dest:
                return route
            for edge in self.edges.get(current, []):
                symbol = self.symbols[edge["symbol"]]
                if executable and "LIMIT" not in symbol.get("orderTypes", []):
                    continue
                if edge["dest"] not in seen:
                    seen.add(edge["dest"])
                    queue.append((edge["dest"], route + [edge]))
        raise SharewellError("NO_EXECUTABLE_ROUTE" if executable else "NO_PRICING_ROUTE")

    def rate(self, source: str, dest: str) -> Decimal:
        value = ONE
        for edge in self.path(source, dest):
            value *= edge["midrate"]
        return value

    def routes(self, source: str, dest: str, *, search_limit: int = 4096):
        queue = deque([(source, [], frozenset({source}))])
        expanded = 0
        while queue:
            current, route, seen = queue.popleft()
            if current == dest:
                yield route
                continue
            expanded += 1
            require(expanded <= search_limit, "ROUTE_SEARCH_LIMIT")
            for edge in self.edges.get(current, []):
                if edge["dest"] in seen or "LIMIT" not in self.symbols[edge["symbol"]].get("orderTypes", []):
                    continue
                require(len(queue) < search_limit, "ROUTE_QUEUE_LIMIT")
                queue.append((edge["dest"], route + [edge], seen | {edge["dest"]}))


def analyze(snapshot: dict, now: int | None = None) -> dict:
    validate_snapshot(snapshot, now)
    market = Market(snapshot)
    rows, unpriced, total = [], [], ZERO
    for balance in sorted(snapshot["balances"], key=lambda row: row["asset"]):
        amount = decimal(balance["free"]) + decimal(balance["locked"])
        if amount == ZERO:
            continue
        try:
            route = market.path(balance["asset"], snapshot["numeraire"])
            value = amount * market.rate(balance["asset"], snapshot["numeraire"])
        except SharewellError:
            unpriced.append({"asset": balance["asset"], "quantity": text(amount)})
            continue
        total += value
        rows.append({**balance, "quantity": text(amount), "value": text(value),
                     "pricing_path": [edge["symbol"] for edge in route]})
    hhi = ZERO
    for row in rows:
        weight = Decimal(row["value"]) / total if total else ZERO
        row["weight_pct"] = text(weight * 100)
        hhi += weight * weight
    rows.sort(key=lambda row: Decimal(row["value"]), reverse=True)
    return {"account": snapshot["account"], "observed_at": snapshot["observed_at"],
            "numeraire": snapshot["numeraire"], "valuation": "bid_ask_midpoint_estimate",
            "coverage": "PARTIAL" if unpriced else "COMPLETE", "priced_value": text(total),
            "weight_basis": "priced_assets_only" if unpriced else "entire_portfolio",
            "total_value": None if unpriced else text(total), "assets": rows,
            "unpriced": unpriced, "concentration": {"hhi": text(hhi),
            "largest_weight_pct": rows[0]["weight_pct"] if rows else "0",
            "effective_asset_count": text(ONE / hhi) if hhi else "0"},
            "evidence": snapshot["evidence"]}


def target_differences(report: dict, targets: dict[str, str]) -> list[dict]:
    require(report["coverage"] == "COMPLETE", "INCOMPLETE_PRICING")
    require(isinstance(targets, dict), "INVALID_TARGETS")
    for name in targets:
        asset(name)
    require(bool(targets) and sum((decimal(x) for x in targets.values()), ZERO) == 100,
            "INVALID_TARGET_TOTAL")
    total = Decimal(report["total_value"])
    require(total > ZERO, "EMPTY_PORTFOLIO")
    current = {row["asset"]: Decimal(row["value"]) for row in report["assets"]}
    return [{"asset": name, "current_value": text(current.get(name, ZERO)),
             "target_pct": targets.get(name, "0"),
             "target_value": text(total * decimal(targets.get(name, "0")) / 100),
             "difference": text(total * decimal(targets.get(name, "0")) / 100 - current.get(name, ZERO))}
            for name in sorted(set(current) | set(targets))]

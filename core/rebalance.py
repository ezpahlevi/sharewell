from copy import deepcopy
from decimal import Decimal
from fractions import Fraction

from .filters import filter_map, multiple, validate_limit
from .portfolio import Market, analyze, target_differences
from .schemas import ONE, ZERO, SharewellError, decimal, digest, integer, now_ms, require, text


def _leg(edge: dict, budget: Decimal, market: Market, state: dict,
         fee: Decimal, slippage: Decimal, now: int) -> dict:
    symbol = market.symbols[edge["symbol"]]
    filters = filter_map(symbol)
    quote = market.quotes[edge["symbol"]]
    buying = edge["side"] == "BUY"
    tick = decimal(filters["PRICE_FILTER"]["tickSize"])
    raw_price = (decimal(quote["askPrice"]) * (ONE + slippage) if buying
                 else decimal(quote["bidPrice"]) * (ONE - slippage))
    price = multiple(raw_price, tick, up=not buying)
    require(price > ZERO, "INVALID_LIMIT_PRICE")
    quantity = Fraction(budget) / (1 + Fraction(fee)) / (Fraction(price) if buying else 1)
    quantity = min(quantity, Fraction(decimal(filters["LOT_SIZE"]["maxQty"])))
    if "NOTIONAL" in filters:
        quantity = min(quantity, Fraction(decimal(filters["NOTIONAL"]["maxNotional"])) / Fraction(price))
    for rule in state.get("asset_filters", []):
        require(rule.get("filterType") == "MAX_ASSET", "INVALID_ASSET_FILTER")
        if rule.get("asset") == symbol["baseAsset"]:
            quantity = min(quantity, Fraction(decimal(rule["limit"])))
        elif rule.get("asset") == symbol["quoteAsset"]:
            quantity = min(quantity, Fraction(decimal(rule["limit"])) / Fraction(price))
    quantity = multiple(quantity, decimal(filters["LOT_SIZE"]["stepSize"]))
    validate_limit(symbol, edge["side"], quantity, price, state, now)
    spend = quantity * (price if buying else ONE) * (ONE + fee)
    received = quantity * (ONE if buying else price) * (ONE - fee)
    require(spend <= budget, "ORDER_EXCEEDS_BUDGET")
    return {"symbol": edge["symbol"], "side": edge["side"], "type": "LIMIT",
            "timeInForce": "IOC", "quantity": text(quantity), "price": text(price),
            "source_asset": edge["source"], "destination_asset": edge["dest"],
            "source_reserve": text(spend), "minimum_net_receive_estimate": text(received)}


def _route(route: list[dict], budget: Decimal, market: Market, state: dict,
           fee: Decimal, slippage: Decimal, now: int):
    trial = deepcopy(state)
    balances = {row["asset"]: row for row in trial["balances"]}
    legs = []
    for edge in route:
        leg = _leg(edge, budget, market, trial, fee, slippage, now)
        legs.append(leg)
        for name in (edge["source"], edge["dest"]):
            if name not in balances:
                balances[name] = {"asset": name, "free": "0", "locked": "0"}
                trial["balances"].append(balances[name])
        origin, destination = balances[edge["source"]], balances[edge["dest"]]
        origin["free"] = text(Decimal(origin["free"]) - Decimal(leg["source_reserve"]))
        require(Decimal(origin["free"]) >= ZERO, "ROUTE_EXCEEDS_BALANCE")
        budget = Decimal(leg["minimum_net_receive_estimate"])
        destination["free"] = text(Decimal(destination["free"]) + budget)
    return legs, trial, balances


def propose(snapshot: dict, targets: dict[str, str], *, fee_allowance_bps: str,
            slippage_bps: str, now: int | None = None, ttl_ms: int = 120_000) -> dict:
    now = now_ms() if now is None else now
    report = analyze(snapshot, now)
    differences = target_differences(report, targets)
    fee = decimal(fee_allowance_bps) / 10_000
    slippage = decimal(slippage_bps) / 10_000
    require(ZERO <= fee < ONE and ZERO <= slippage < ONE, "INVALID_BPS")
    require(0 < integer(ttl_ms, "ttl_ms") <= 300_000, "INVALID_TTL")
    market = Market(snapshot)
    for name, percent in targets.items():
        if decimal(percent):
            market.path(name, snapshot["numeraire"])
    state = deepcopy(snapshot)
    balances = {row["asset"]: row for row in state["balances"]}
    current = {row["asset"]: Decimal(row["current_value"]) for row in differences}
    desired = {row["asset"]: Decimal(row["target_value"]) for row in differences}
    prices = {name: market.rate(name, snapshot["numeraire"])
              for name in current if current[name] or desired[name]}
    orders, issues = [], []
    donors = sorted(name for name in current if current[name] > desired[name])
    recipients = sorted(name for name in current if current[name] < desired[name])
    for source in donors:
        for dest in recipients:
            while True:
                surplus = max(ZERO, current[source] - desired[source])
                shortfall = max(ZERO, desired[dest] - current[dest])
                available = Decimal(balances.get(source, {}).get("free", "0"))
                budget = min(available, surplus / prices[source], shortfall / prices[source])
                if budget == ZERO:
                    break
                require(len(orders) < 256, "PROPOSAL_LEG_LIMIT")
                selected = None
                reason = "NO_EXECUTABLE_ROUTE"
                try:
                    for route in market.routes(source, dest):
                        try:
                            selected = _route(route, budget, market, state, fee, slippage, now)
                            break
                        except SharewellError as exc:
                            reason = str(exc)
                except SharewellError as exc:
                    reason = str(exc)
                if selected is None:
                    issues.append({"source": source, "destination": dest, "reason": reason})
                    break
                legs, state, balances = selected
                require(bool(legs) and len(orders) + len(legs) <= 256, "PROPOSAL_LEG_LIMIT")
                for leg in legs:
                    name = leg["source_asset"]
                    current[name] = current.get(name, ZERO) - Decimal(leg["source_reserve"]) * market.rate(name, snapshot["numeraire"])
                    name = leg["destination_asset"]
                    current[name] = current.get(name, ZERO) + Decimal(leg["minimum_net_receive_estimate"]) * market.rate(name, snapshot["numeraire"])
                    leg["index"] = len(orders)
                    leg["depends_on"] = len(orders) - 1 if orders else None
                    orders.append(leg)
    proposal = {"version": 1, "account": deepcopy(snapshot["account"]),
                "created_at": now, "expires_at": now + ttl_ms, "numeraire": snapshot["numeraire"],
                "snapshot_hash": digest(snapshot), "targets": deepcopy(targets),
                "fee_allowance_bps": fee_allowance_bps, "slippage_bps": slippage_bps,
                "initial": report, "differences": differences, "orders": orders, "issues": issues,
                "projection_basis": "LIMIT_FEE_RESERVE",
                "residual_value_differences": {name: text(desired.get(name, ZERO) - current[name])
                                                for name in sorted(current)},
                "execution_eligible": snapshot["account"]["kind"] == "AGENTIC"
                                      and snapshot["account"]["can_trade"],
                "evidence": list(snapshot["evidence"])}
    proposal["hash"] = digest(proposal)
    return proposal

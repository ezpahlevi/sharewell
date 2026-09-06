"""Synthetic inputs for tests only; these are not Binance account evidence."""

from core.schemas import ENDPOINT

NOW = 1_000_000


def symbol(base="BTC", quote="USDT"):
    return {"symbol": base + quote, "baseAsset": base, "quoteAsset": quote,
            "status": "TRADING", "isSpotTradingAllowed": True, "orderTypes": ["LIMIT"],
            "filters": [
                {"filterType": "PRICE_FILTER", "minPrice": "0.01", "maxPrice": "1000000", "tickSize": "0.01"},
                {"filterType": "LOT_SIZE", "minQty": "0.001", "maxQty": "10000", "stepSize": "0.001"},
                {"filterType": "MIN_NOTIONAL", "minNotional": "5"}]}


def snapshot():
    return {"version": 1, "source": ENDPOINT, "observed_at": NOW,
            "account": {"id": "synthetic-test-account", "kind": "AGENTIC", "wallet": "SPOT", "can_trade": True},
            "numeraire": "USDT", "balances_complete": True,
            "balances": [{"asset": "BTC", "free": "1", "locked": "0"},
                         {"asset": "USDT", "free": "100", "locked": "0"}],
            "symbols": [symbol()], "quotes": [{"symbol": "BTCUSDT", "bidPrice": "99", "askPrice": "101", "observed_at": NOW}],
            "open_orders": [], "open_orders_complete": True, "evidence": ["synthetic-fixture"]}

from collections import defaultdict
from decimal import Decimal

from core.schemas import asset, decimal, integer, require, text


METRICS = {"return", "volatility", "max_drawdown", "relative_strength"}


def _points(inputs):
    rows = inputs["price_history"]
    require(isinstance(rows, list), "INVALID_PRICE_HISTORY")
    grouped = defaultdict(list)
    for row in rows:
        require(isinstance(row, dict), "INVALID_PRICE_HISTORY")
        name = asset(row.get("asset"))
        observed_at = integer(row.get("observed_at"), "observed_at")
        price = decimal(row.get("price"))
        require(price > 0, "INVALID_PRICE_HISTORY")
        grouped[name].append((observed_at, price))
    for values in grouped.values():
        values.sort()
    return grouped


def _window(points, start, end):
    before_start = [point for point in points if point[0] <= start]
    before_end = [point for point in points if point[0] <= end]
    if not before_start or not before_end or before_end[-1][0] <= before_start[-1][0]:
        return None
    return before_start[-1], before_end[-1], [point for point in points if start <= point[0] <= end]


def _base_metrics(window):
    first, last, points = window
    values = [first[1]] + [point[1] for point in points if point[0] > first[0]]
    returns = [values[index] / values[index - 1] - 1 for index in range(1, len(values))]
    result = {"return": last[1] / first[1] - 1}
    if returns:
        mean = sum(returns, Decimal(0)) / len(returns)
        result["volatility"] = (sum(((value - mean) ** 2 for value in returns), Decimal(0)) /
                                 len(returns)).sqrt()
    peak = values[0]
    drawdown = Decimal(0)
    for value in values:
        peak = max(peak, value)
        drawdown = min(drawdown, value / peak - 1)
    result["max_drawdown"] = drawdown
    return result


class HistoricalMarketEvaluator:
    evaluator_id = "historical_market_performance"
    version = 1
    scope = "MARKET"
    required_inputs = ("price_history", "evidence")

    def default_parameters(self):
        return {"windows_days": [3, 7, 14, 30],
                "metrics": ["return", "volatility", "max_drawdown", "relative_strength"]}

    def validate_parameters(self, parameters):
        require(set(parameters) <= {"windows_days", "metrics"}, "INVALID_EVALUATION_PARAMETERS")
        windows = parameters.get("windows_days", self.default_parameters()["windows_days"])
        metrics = parameters.get("metrics", self.default_parameters()["metrics"])
        require(isinstance(windows, list) and all(type(value) is int and value > 0 for value in windows),
                "INVALID_EVALUATION_PARAMETERS")
        require(isinstance(metrics, list) and all(value in METRICS for value in metrics),
                "INVALID_EVALUATION_PARAMETERS")
        require(bool(windows) and bool(metrics) and len(set(windows)) == len(windows)
                and len(set(metrics)) == len(metrics), "INVALID_EVALUATION_PARAMETERS")
        return {"windows_days": sorted(windows), "metrics": sorted(metrics)}

    def evaluate(self, inputs, parameters):
        grouped = _points(inputs)
        as_of = inputs.get("as_of", max((point[0] for rows in grouped.values() for point in rows), default=0))
        integer(as_of, "as_of")
        returns = {}
        output = {}
        missing = False
        for name, points in sorted(grouped.items()):
            windows = {}
            for days in parameters["windows_days"]:
                window = _window(points, as_of - days * 86_400_000, as_of)
                if window is None:
                    missing = True
                    continue
                values = _base_metrics(window)
                returns.setdefault(days, {})[name] = values["return"]
                windows[str(days)] = values
            output[name] = {"windows": windows}
        for name in output:
            for days in parameters["windows_days"]:
                if str(days) not in output[name]["windows"]:
                    continue
                if "relative_strength" in parameters["metrics"]:
                    peers = [value for peer, values in returns.get(days, {}).items() if peer != name
                             for value in [values]]
                    if peers:
                        output[name]["windows"][str(days)]["relative_strength"] = (
                            returns[days][name] - sum(peers, Decimal(0)) / len(peers))
                    else:
                        missing = True
        for values in output.values():
            for window in values["windows"].values():
                for key in list(window):
                    if key not in parameters["metrics"]:
                        del window[key]
                    else:
                        window[key] = text(window[key])
        status = "UNAVAILABLE" if not output else "PARTIAL" if missing else "PASS"
        warnings = ["INSUFFICIENT_HISTORY"] if missing else []
        return {"status": status, "metrics": {"as_of": as_of, "assets": output},
                "evidence": inputs["evidence"], "score": None, "warnings": warnings,
                "observations": ["ASSET_COUNT:" + str(len(output))]}


evaluator = HistoricalMarketEvaluator()

from collections import defaultdict
from decimal import Decimal
import re

from core.schemas import asset, decimal, integer, require, text


METRICS = {"return", "volatility", "max_drawdown", "relative_strength"}


def _points(inputs):
    rows = inputs["price_history"]
    require(isinstance(rows, list), "INVALID_PRICE_HISTORY")
    grouped = defaultdict(list)
    seen = defaultdict(set)
    for row in rows:
        require(isinstance(row, dict), "INVALID_PRICE_HISTORY")
        name = asset(row.get("asset"))
        observed_at = integer(row.get("observed_at"), "observed_at")
        price = decimal(row.get("price"))
        require(price > 0, "INVALID_PRICE_HISTORY")
        require(observed_at not in seen[name], "DUPLICATE_PRICE_HISTORY")
        seen[name].add(observed_at)
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
    if len(returns) >= 2:
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


def _benchmark_history(inputs):
    rows = inputs.get("benchmark_history")
    evidence = inputs.get("benchmark_evidence")
    if rows is None or evidence is None:
        return None
    require(isinstance(rows, list) and isinstance(evidence, list),
            "INVALID_BENCHMARK_HISTORY")
    if not rows or not evidence:
        return None
    require(all(isinstance(item, str) and 0 < len(item) <= 200 for item in evidence),
            "INVALID_BENCHMARK_HISTORY")
    points = []
    seen = set()
    for row in rows:
        require(isinstance(row, dict), "INVALID_BENCHMARK_HISTORY")
        observed_at = integer(row.get("observed_at"), "benchmark_observed_at")
        require(observed_at not in seen, "DUPLICATE_BENCHMARK_HISTORY")
        seen.add(observed_at)
        price = decimal(row.get("price"))
        require(price > 0, "INVALID_BENCHMARK_HISTORY")
        points.append((observed_at, price))
    points.sort()
    return points


class HistoricalMarketEvaluator:
    evaluator_id = "historical_market_performance"
    version = 2
    scope = "MARKET"
    required_inputs = ("price_history", "evidence")

    def default_parameters(self):
        return {"windows_days": [3, 7, 14, 30],
                "metrics": ["return", "volatility", "max_drawdown", "relative_strength"],
                "benchmark": "PEERS"}

    def validate_parameters(self, parameters):
        require(set(parameters) <= {"windows_days", "metrics", "benchmark"}, "INVALID_EVALUATION_PARAMETERS")
        windows = parameters.get("windows_days", self.default_parameters()["windows_days"])
        metrics = parameters.get("metrics", self.default_parameters()["metrics"])
        benchmark = parameters.get("benchmark", self.default_parameters()["benchmark"])
        require(isinstance(windows, list) and all(type(value) is int and value > 0 for value in windows),
                "INVALID_EVALUATION_PARAMETERS")
        require(isinstance(metrics, list) and all(value in METRICS for value in metrics),
                "INVALID_EVALUATION_PARAMETERS")
        require(bool(windows) and bool(metrics) and len(set(windows)) == len(windows)
                and len(set(metrics)) == len(metrics), "INVALID_EVALUATION_PARAMETERS")
        require(isinstance(benchmark, str) and
                (benchmark in {"PEERS", "PORTFOLIO"} or re.fullmatch(r"[A-Z0-9]{1,32}", benchmark)),
                "INVALID_EVALUATION_PARAMETERS")
        return {"windows_days": sorted(windows), "metrics": sorted(metrics), "benchmark": benchmark}

    def evaluate(self, inputs, parameters):
        grouped = _points(inputs)
        as_of = inputs.get("as_of", max((point[0] for rows in grouped.values() for point in rows), default=0))
        integer(as_of, "as_of")
        requested = inputs.get("requested_assets")
        if requested is None:
            names = sorted(grouped)
        else:
            require(isinstance(requested, list) and bool(requested), "INVALID_PRICE_HISTORY")
            names = [asset(value) for value in requested]
            require(len(set(names)) == len(names), "INVALID_PRICE_HISTORY")
            names.sort()
        coverage = inputs.get("coverage", {})
        require(isinstance(coverage, dict), "INVALID_PRICE_HISTORY")
        incomplete_assets = coverage.get("incomplete_assets", [])
        require(isinstance(incomplete_assets, list), "INVALID_PRICE_HISTORY")
        returns = {}
        output = {}
        missing = False
        available_windows = False
        for name in names:
            points = grouped.get(name, [])
            windows = {}
            for days in parameters["windows_days"]:
                window = _window(points, as_of - days * 86_400_000, as_of)
                if window is None:
                    missing = True
                    continue
                available_windows = True
                values = _base_metrics(window)
                if any(metric not in values for metric in parameters["metrics"] if metric != "relative_strength"):
                    missing = True
                returns.setdefault(days, {})[name] = values["return"]
                windows[str(days)] = values
            output[name] = {"windows": windows}
            if name in incomplete_assets:
                missing = True
        for name in output:
            for days in parameters["windows_days"]:
                if str(days) not in output[name]["windows"]:
                    continue
                if "relative_strength" in parameters["metrics"]:
                    reference = None
                    if parameters["benchmark"] == "PEERS":
                        peers = [value for peer, value in returns.get(days, {}).items() if peer != name]
                        if peers:
                            reference = sum(peers, Decimal(0)) / len(peers)
                    elif parameters["benchmark"] == "PORTFOLIO":
                        benchmark = _benchmark_history(inputs)
                        if benchmark is not None:
                            window = _window(benchmark, as_of - days * 86_400_000, as_of)
                            if window is not None:
                                reference = _base_metrics(window)["return"]
                    else:
                        benchmark = grouped.get(parameters["benchmark"], [])
                        window = _window(benchmark, as_of - days * 86_400_000, as_of)
                        if window is not None:
                            reference = _base_metrics(window)["return"]
                    if reference is not None:
                        output[name]["windows"][str(days)]["relative_strength"] = (
                            returns[days][name] - reference)
                    else:
                        missing = True
        for values in output.values():
            for window in values["windows"].values():
                for key in list(window):
                    if key not in parameters["metrics"]:
                        del window[key]
                    else:
                        window[key] = text(window[key])
        warnings = []
        if missing:
            warnings.append("INSUFFICIENT_HISTORY")
        if any(name not in grouped for name in names):
            warnings.append("MISSING_ASSET_HISTORY")
        if any(name in incomplete_assets for name in names):
            warnings.append("INCOMPLETE_KLINE_HISTORY")
        if "relative_strength" in parameters["metrics"] and parameters["benchmark"] != "PEERS":
            benchmark_available = parameters["benchmark"] == "PORTFOLIO" and _benchmark_history(inputs) is not None
            benchmark_available = benchmark_available or parameters["benchmark"] in grouped
            if not benchmark_available:
                warnings.append("MISSING_BENCHMARK_HISTORY")
        status = "UNAVAILABLE" if not available_windows else "PARTIAL" if missing else "PASS"
        evidence = list(inputs["evidence"])
        if parameters["benchmark"] == "PORTFOLIO":
            benchmark_evidence = inputs.get("benchmark_evidence", [])
            if isinstance(benchmark_evidence, list):
                evidence.extend(benchmark_evidence)
        return {"status": status, "metrics": {"as_of": as_of, "assets": output},
                "evidence": list(dict.fromkeys(evidence)), "score": None,
                "warnings": list(dict.fromkeys(warnings)),
                "observations": ["ASSET_COUNT:" + str(len(output))]}


evaluator = HistoricalMarketEvaluator()

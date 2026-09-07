from decimal import Decimal

from core.portfolio import analyze, target_differences
from core.schemas import SharewellError, decimal, require, text


def _evidence(inputs):
    refs = list(inputs["proposal"].get("evidence", []))
    for snapshot in (inputs["initial_snapshot"], inputs["final_snapshot"]):
        refs.extend(snapshot.get("evidence", []))
    for order in inputs["orders"]:
        receipt = order.get("receipt")
        if isinstance(receipt, dict):
            refs.append(receipt.get("evidence"))
    return [ref for ref in dict.fromkeys(refs) if isinstance(ref, str) and ref]


class ExecutionQualityEvaluator:
    evaluator_id = "execution_quality"
    version = 1
    scope = "EXECUTION"
    required_inputs = ("proposal", "orders", "initial_snapshot", "final_snapshot")

    def default_parameters(self):
        return {}

    def validate_parameters(self, parameters):
        require(not parameters, "INVALID_EVALUATION_PARAMETERS")
        return {}

    def evaluate(self, inputs, parameters):
        proposal = inputs["proposal"]
        orders = inputs["orders"]
        require(isinstance(proposal, dict) and isinstance(orders, list), "INVALID_EXECUTION_INPUT")
        final_report = analyze(inputs["final_snapshot"], inputs["final_snapshot"]["observed_at"])
        metrics = []
        commissions = {}
        timestamps = []
        all_filled = bool(orders)
        warnings = []
        for order in orders:
            index = order.get("idx")
            planned = proposal["orders"][index]
            receipt = order.get("receipt")
            require(isinstance(receipt, dict), "INCOMPLETE_EXECUTION_INPUT")
            status = receipt.get("status")
            all_filled = all_filled and status == "FILLED"
            executed = decimal(receipt["executedQty"])
            quote = decimal(receipt["cummulativeQuoteQty"])
            average = text(quote / executed) if executed else None
            slippage = None
            if average is not None:
                average_value = Decimal(average)
                limit = Decimal(planned["price"])
                slippage = text((average_value / limit - 1) * 10_000 if planned["side"] == "BUY"
                                else (limit / average_value - 1) * 10_000)
            for fill in receipt.get("fills", []):
                name = fill["commissionAsset"]
                commissions[name] = text(Decimal(commissions.get(name, "0")) + decimal(fill["commission"]))
                timestamps.append(receipt["observed_at"])
            metrics.append({"index": index, "fill_state": status,
                            "planned_limit_price": planned["price"],
                            "actual_average_fill_price": average,
                            "realized_slippage_bps": slippage,
                            "expected_fee_allowance_bps": proposal["fee_allowance_bps"],
                            "execution_timestamp": receipt["observed_at"]})
        try:
            drift = target_differences(final_report, proposal["targets"])
        except SharewellError:
            drift = None
            warnings.append("INCOMPLETE_FINAL_PRICING")
        fee_allowance = Decimal(proposal["fee_allowance_bps"])
        if any(Decimal(value) > 0 for value in commissions.values()):
            warnings.append("COMMISSION_RECORDED")
        status = "PASS" if all_filled else "PARTIAL" if orders else "FAIL"
        return {"status": status,
                "metrics": {"orders": metrics, "actual_commissions": commissions,
                             "residual_target_drift": drift, "final_allocation": {
                                 row["asset"]: row["weight_pct"] for row in final_report["assets"]},
                             "execution_timestamp": max(timestamps) if timestamps else None,
                             "fee_allowance_bps": text(fee_allowance)},
                "evidence": _evidence(inputs), "score": None,
                "warnings": list(dict.fromkeys(warnings)), "observations": []}


evaluator = ExecutionQualityEvaluator()

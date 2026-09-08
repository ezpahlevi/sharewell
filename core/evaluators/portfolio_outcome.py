from copy import deepcopy
from decimal import Decimal

from core.portfolio import analyze
from core.schemas import require, text


def _evidence(inputs):
    refs = []
    for snapshot in (inputs["initial_snapshot"], inputs["final_snapshot"]):
        refs.extend(snapshot.get("evidence", []))
    refs.extend(inputs["proposal"].get("evidence", []))
    return [ref for ref in dict.fromkeys(refs) if isinstance(ref, str) and ref]


def _hold_snapshot(initial, final):
    result = deepcopy(final)
    result["balances"] = deepcopy(initial["balances"])
    return result


class PortfolioOutcomeEvaluator:
    evaluator_id = "portfolio_outcome"
    version = 1
    scope = "PORTFOLIO"
    required_inputs = ("proposal", "initial_snapshot", "final_snapshot")

    def default_parameters(self):
        return {}

    def validate_parameters(self, parameters):
        require(not parameters, "INVALID_EVALUATION_PARAMETERS")
        return {}

    def evaluate(self, inputs, parameters):
        initial = inputs["initial_snapshot"]
        final = inputs["final_snapshot"]
        require(initial["numeraire"] == final["numeraire"], "NUMERAIRE_MISMATCH")
        actual = analyze(final, final["observed_at"])
        hold = analyze(_hold_snapshot(initial, final), final["observed_at"])
        actual_value = Decimal(actual["priced_value"])
        hold_value = Decimal(hold["priced_value"])
        difference = actual_value - hold_value
        complete = actual["coverage"] == "COMPLETE" and hold["coverage"] == "COMPLETE"
        warnings = [] if complete else ["INCOMPLETE_PRICING"]
        return {"status": "PASS" if complete else "PARTIAL",
                "metrics": {"actual_portfolio": {"coverage": actual["coverage"],
                                                    "priced_value": actual["priced_value"],
                                                    "assets": actual["assets"]},
                             "hold_baseline": {"coverage": hold["coverage"],
                                               "priced_value": hold["priced_value"],
                                               "assets": hold["assets"]},
                             "priced_value_difference": text(difference),
                             "numeraire": final["numeraire"]},
                "evidence": _evidence(inputs), "score": None,
                "warnings": warnings, "observations": []}


evaluator = PortfolioOutcomeEvaluator()

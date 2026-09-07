import tempfile
import unittest
from pathlib import Path

from core.evaluation import evaluator_registry, profile_registry, register_evaluator, run_evaluator, run_profile
from core.journal import Journal
from core.schemas import SharewellError
from fixtures import snapshot


class ContractEvaluator:
    evaluator_id = "test.contract"
    version = 1
    scope = "TEST"
    required_inputs = ("value", "evidence")

    def default_parameters(self):
        return {"factor": "2"}

    def validate_parameters(self, parameters):
        self.factor = parameters["factor"]
        return parameters

    def evaluate(self, inputs, parameters):
        return {"status": "PASS", "metrics": {"value": inputs["value"], "factor": parameters["factor"]},
            "evidence": inputs["evidence"], "score": None, "warnings": [], "observations": []}


TEST_EVALUATOR = ContractEvaluator()


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        register_evaluator(TEST_EVALUATOR)

    def test_registry_contract_and_custom_registration(self):
        result = run_evaluator("test.contract", {"value": "x", "evidence": ["synthetic-evidence"]})
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["input_hash"], run_evaluator("test.contract", {
            "value": "x", "evidence": ["synthetic-evidence"]})["input_hash"])
        self.assertIn("historical_market_performance", evaluator_registry())
        self.assertIn("balanced", profile_registry())

    def test_historical_evaluator_accepts_runtime_parameters(self):
        day = 86_400_000
        inputs = {"as_of": 3 * day, "evidence": ["synthetic-history"], "price_history": [
            {"asset": "BTC", "observed_at": 0, "price": "100"},
            {"asset": "BTC", "observed_at": day, "price": "110"},
            {"asset": "BTC", "observed_at": 3 * day, "price": "120"},
            {"asset": "ETH", "observed_at": 0, "price": "50"},
            {"asset": "ETH", "observed_at": day, "price": "55"},
            {"asset": "ETH", "observed_at": 3 * day, "price": "60"}]}
        result = run_evaluator("historical_market_performance", inputs,
                              {"windows_days": [3], "metrics": ["return", "relative_strength"]})
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["parameters"]["windows_days"], [3])
        self.assertEqual(result["metrics"]["assets"]["BTC"]["windows"]["3"]["return"], "0.2")

    def test_invalid_evaluator_parameters_are_rejected(self):
        with self.assertRaisesRegex(SharewellError, "INVALID_EVALUATION_PARAMETERS"):
            run_evaluator("historical_market_performance", {"price_history": [], "evidence": ["x"]},
                          {"windows_days": [0], "metrics": ["return"]})

    def test_evaluation_runs_persist_generic_results(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = Journal(str(Path(directory) / "state.sqlite"))
            account = snapshot()["account"]
            inputs = {"value": "x", "evidence": ["synthetic-evidence"]}
            result = journal.evaluate(account, inputs, evaluator_id="test.contract", now=1_000_000)
            self.assertEqual(result["runs"][0]["evaluator_id"], "test.contract")
            names = {row[0] for row in journal.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertIn("evaluation_runs", names)
            journal.close()

    def test_profiles_return_each_evaluator_result(self):
        inputs = {"price_history": [], "evidence": ["synthetic-history"]}
        result = run_profile("momentum", inputs, {"historical_market_performance": {
            "windows_days": [1], "metrics": ["return"]}})
        self.assertEqual(result["profile"], "momentum")
        self.assertEqual(len(result["results"]), 1)
        self.assertEqual(result["results"][0]["status"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()

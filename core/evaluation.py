from copy import deepcopy
from decimal import Decimal
import importlib
import re

from .schemas import SharewellError, canonical, digest, require, text


STATUSES = {"PASS", "FAIL", "PARTIAL", "UNAVAILABLE"}
_EVALUATORS = {}
_PROFILES = {}
_DISCOVERED = False


def _json_value(value):
    if isinstance(value, float):
        raise SharewellError("FLOAT_EVALUATION_VALUE")
    if isinstance(value, dict):
        require(all(isinstance(key, str) for key in value), "INVALID_EVALUATION_VALUE")
        for item in value.values():
            _json_value(item)
    elif isinstance(value, list):
        for item in value:
            _json_value(item)
    elif not isinstance(value, (str, int, bool)) and value is not None:
        raise SharewellError("INVALID_EVALUATION_VALUE")
    return value


def _contract(evaluator):
    identifier = getattr(evaluator, "evaluator_id", None)
    version = getattr(evaluator, "version", None)
    scope = getattr(evaluator, "scope", None)
    required = getattr(evaluator, "required_inputs", None)
    require(isinstance(identifier, str) and re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", identifier),
            "INVALID_EVALUATOR_ID")
    require(type(version) is int and version > 0, "INVALID_EVALUATOR_VERSION")
    require(isinstance(scope, str) and 0 < len(scope) <= 64, "INVALID_EVALUATOR_SCOPE")
    require(isinstance(required, (tuple, list)) and all(isinstance(item, str) and item for item in required),
            "INVALID_EVALUATOR_INPUTS")
    require(len(set(required)) == len(required), "DUPLICATE_EVALUATOR_INPUT")
    require(callable(getattr(evaluator, "validate_parameters", None)), "INVALID_EVALUATOR_CONTRACT")
    require(callable(getattr(evaluator, "evaluate", None)), "INVALID_EVALUATOR_CONTRACT")
    require(callable(getattr(evaluator, "default_parameters", None)), "INVALID_EVALUATOR_CONTRACT")
    return {"evaluator_id": identifier, "version": version, "scope": scope,
            "required_inputs": list(required)}


def register_evaluator(evaluator):
    contract = _contract(evaluator)
    current = _EVALUATORS.get(contract["evaluator_id"])
    require(current is None or current is evaluator, "DUPLICATE_EVALUATOR")
    _EVALUATORS[contract["evaluator_id"]] = evaluator
    return evaluator


def register_profile(name: str, selections: list[dict]):
    require(isinstance(name, str) and re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,63}", name), "INVALID_PROFILE")
    require(isinstance(selections, list) and bool(selections), "INVALID_PROFILE")
    checked = []
    for selection in selections:
        require(isinstance(selection, dict) and isinstance(selection.get("evaluator_id"), str), "INVALID_PROFILE")
        parameters = selection.get("parameters", {})
        weight = selection.get("weight", "1")
        require(isinstance(parameters, dict) and isinstance(weight, str), "INVALID_PROFILE")
        checked.append({"evaluator_id": selection["evaluator_id"], "parameters": deepcopy(parameters),
                        "weight": weight})
    require(name not in _PROFILES, "DUPLICATE_PROFILE")
    _PROFILES[name] = checked
    return name


def _discover():
    global _DISCOVERED
    if not _DISCOVERED:
        importlib.import_module("core.evaluators")
        _DISCOVERED = True


def evaluator_registry() -> dict:
    _discover()
    return dict(_EVALUATORS)


def profile_registry() -> dict:
    _discover()
    return deepcopy(_PROFILES)


def _references(value) -> list[str]:
    require(isinstance(value, list) and all(isinstance(item, str) and 0 < len(item) <= 200 for item in value),
            "INVALID_EVALUATION_EVIDENCE")
    return list(dict.fromkeys(value))


def _unavailable(contract: dict, parameters: dict, inputs: dict, error: str) -> dict:
    return {**contract, "parameters": parameters, "input_hash": digest(inputs), "status": "UNAVAILABLE",
            "metrics": {}, "evidence": _references(inputs.get("evidence", [])), "score": None,
            "warnings": [error], "observations": []}


def run_evaluator(identifier: str, inputs: dict, parameters: dict | None = None,
                  *, allow_unavailable: bool = False) -> dict:
    _discover()
    evaluator = _EVALUATORS.get(identifier)
    require(evaluator is not None, "UNKNOWN_EVALUATOR")
    contract = _contract(evaluator)
    require(isinstance(inputs, dict), "INVALID_EVALUATION_INPUT")
    missing = [name for name in contract["required_inputs"] if name not in inputs]
    if missing:
        if allow_unavailable:
            return _unavailable(contract, {}, inputs, "MISSING_EVALUATION_INPUT")
        raise SharewellError("MISSING_EVALUATION_INPUT")
    _json_value(inputs)
    supplied = deepcopy(parameters if parameters is not None else evaluator.default_parameters())
    require(isinstance(supplied, dict), "INVALID_EVALUATION_PARAMETERS")
    try:
        checked = evaluator.validate_parameters(supplied)
    except SharewellError:
        if not allow_unavailable:
            raise
        return _unavailable(contract, supplied, inputs, "INVALID_EVALUATION_PARAMETERS")
    require(isinstance(checked, dict), "INVALID_EVALUATION_PARAMETERS")
    raw = evaluator.evaluate(deepcopy(inputs), deepcopy(checked))
    require(isinstance(raw, dict), "INVALID_EVALUATION_RESULT")
    status = raw.get("status")
    require(status in STATUSES, "INVALID_EVALUATION_STATUS")
    metrics = raw.get("metrics", {})
    require(isinstance(metrics, dict), "INVALID_EVALUATION_METRICS")
    evidence = _references(raw.get("evidence", inputs.get("evidence", [])))
    warnings = raw.get("warnings", [])
    observations = raw.get("observations", [])
    require(isinstance(warnings, list) and all(isinstance(item, str) for item in warnings),
            "INVALID_EVALUATION_WARNINGS")
    require(isinstance(observations, list), "INVALID_EVALUATION_OBSERVATIONS")
    score = raw.get("score")
    require(score is None or isinstance(score, str), "INVALID_EVALUATION_SCORE")
    result = {**contract, "parameters": checked, "input_hash": digest(inputs), "status": status,
              "metrics": metrics, "evidence": evidence, "score": score,
              "warnings": warnings, "observations": observations}
    _json_value(result)
    return result


def run_profile(name: str, inputs: dict, parameters: dict | None = None) -> dict:
    _discover()
    selections = _PROFILES.get(name)
    require(selections is not None, "UNKNOWN_PROFILE")
    overrides = parameters or {}
    require(isinstance(overrides, dict), "INVALID_PROFILE_PARAMETERS")
    results = []
    weighted = []
    warnings = []
    for selection in selections:
        identifier = selection["evaluator_id"]
        selected = deepcopy(selection["parameters"])
        if identifier in overrides:
            require(isinstance(overrides[identifier], dict), "INVALID_PROFILE_PARAMETERS")
            selected.update(deepcopy(overrides[identifier]))
        result = run_evaluator(identifier, inputs, selected, allow_unavailable=True)
        results.append(result)
        if result["warnings"]:
            warnings.extend(result["warnings"])
        if result["score"] is not None:
            weighted.append((Decimal(result["score"]), Decimal(selection["weight"])))
    score = None
    if weighted and sum((weight for _, weight in weighted), Decimal(0)):
        score = text(sum((value * weight for value, weight in weighted), Decimal(0)) /
                     sum((weight for _, weight in weighted), Decimal(0)))
    statuses = {result["status"] for result in results}
    status = "FAIL" if "FAIL" in statuses else "PARTIAL" if statuses - {"PASS"} else "PASS"
    evidence = []
    for result in results:
        evidence.extend(result["evidence"])
    return {"profile": name, "status": status, "results": results, "score": score,
            "evidence": list(dict.fromkeys(evidence)), "warnings": list(dict.fromkeys(warnings))}

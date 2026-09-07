import argparse
from copy import deepcopy
import json
import os
import sqlite3
import sys
from decimal import DecimalException
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.journal import Journal
from core.portfolio import analyze
from core.rebalance import propose
from core.schemas import SharewellError, canonical, digest, now_ms, require
from providers.binance_mcp import bind_order, normalize_snapshot


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "DUP_JSON_KEY")
        result[key] = value
    return result


def account_from(request: dict):
    account = request.get("account")
    if account is None and isinstance(request.get("snapshot"), dict):
        account = request["snapshot"].get("account")
    return account


def default_state(account: dict) -> str:
    require(isinstance(account, dict), "MISSING_STATE")
    if os.name == "nt":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    target = root / "Sharewell" / "accounts" / digest(account) / "sharewell.sqlite3"
    target.parent.mkdir(parents=True, exist_ok=True)
    return str(target)


def state_path(state: str | None, request: dict) -> str:
    if state:
        return state
    return default_state(account_from(request))


def selected_snapshot(request: dict, journal: Journal | None = None) -> dict:
    snapshot = deepcopy(request["snapshot"])
    if "numeraire" in request:
        snapshot["numeraire"] = request["numeraire"]
    elif journal is not None:
        preference = journal.default_numeraire(snapshot["account"])
        if preference:
            snapshot["numeraire"] = preference
    return snapshot


def run(operation: str, request: dict, state: str | None):
    require(isinstance(request, dict), "INVALID_REQUEST")
    if operation == "normalize":
        return normalize_snapshot(request, now=now_ms())
    if operation == "analyze":
        account = account_from(request)
        journal = Journal(state_path(state, request)) if account else None
        try:
            return analyze(selected_snapshot(request, journal))
        finally:
            if journal:
                journal.close()
    journal = Journal(state_path(state, request))
    try:
        account = account_from(request)
        if operation == "policy-get":
            return journal.policy_get(account)
        if operation == "policy-set":
            return journal.policy_set(account, request["asset"], request["policy"], request["source_reference"])
        if operation == "preference-get":
            return journal.preference_get(account, request.get("key"))
        if operation == "preference-set":
            return journal.preference_set(account, request["key"], request["value"], request["source_reference"])
        if operation == "snapshot":
            return journal.save_snapshot(request["snapshot"], request["reason"], live=request.get("live", False))
        if operation == "history":
            return journal.history(account, request.get("limit", 50))
        if operation == "memory-summary":
            return journal.memory_summary(account)
        if operation == "propose":
            snapshot = selected_snapshot(request, journal)
            policies = journal.policy_get(snapshot["account"])["policies"]
            plan = propose(snapshot, request["targets"],
                           fee_allowance_bps=request["fee_allowance_bps"],
                           slippage_bps=request["slippage_bps"],
                           ttl_ms=request.get("ttl_ms", 120_000), policies=policies)
            journal.save(plan, snapshot)
            return plan
        key = request["proposal_hash"]
        if operation == "approve":
            journal.approve(key, request["account"], request["approval_ref"])
            return journal.status(key)
        if operation == "dispatch":
            catalog, binding = request["catalog"], request["binding"]
            return journal.dispatch(key, request["snapshot"], prepare=lambda action, account, now:
                                    bind_order(action, account, catalog, binding, now=now))
        if operation == "record":
            journal.record(key, request["index"], request["receipt"])
            return journal.status(key)
        if operation == "verify":
            return journal.verify(key, request["snapshot"])
        if operation == "stop":
            return journal.stop(key, request["snapshot"])
        if operation == "status":
            return journal.status(key)
        raise SharewellError("UNKNOWN_OPERATION")
    finally:
        journal.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["normalize", "analyze", "propose", "approve", "dispatch", "record", "verify", "stop", "status", "snapshot", "history", "memory-summary", "policy-get", "policy-set", "preference-get", "preference-set"])
    parser.add_argument("--input", required=True)
    parser.add_argument("--state")
    args = parser.parse_args()
    try:
        path = Path(args.input)
        require(path.stat().st_size <= 64 * 1024 * 1024, "REQUEST_TOO_LARGE")
        request = json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=pairs)
        print(canonical({"ok": True, "result": run(args.operation, request, args.state)}))
        return 0
    except SharewellError as exc:
        print(canonical({"ok": False, "error": str(exc)}))
    except (KeyError, TypeError, AttributeError, ValueError, DecimalException):
        print(canonical({"ok": False, "error": "MALFORMED_REQUEST"}))
    except (OSError, sqlite3.Error):
        print(canonical({"ok": False, "error": "STORAGE_ERROR"}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

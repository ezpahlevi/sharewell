import argparse
import json
import sqlite3
import sys
from decimal import DecimalException
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.journal import Journal
from core.portfolio import analyze
from core.rebalance import propose
from core.schemas import SharewellError, canonical, now_ms, require
from providers.binance_mcp import bind_order, normalize_snapshot


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "DUP_JSON_KEY")
        result[key] = value
    return result


def run(operation: str, request: dict, state: str | None):
    require(isinstance(request, dict), "INVALID_REQUEST")
    if operation == "normalize":
        return normalize_snapshot(request, now=now_ms())
    if operation == "analyze":
        return analyze(request["snapshot"])
    require(state is not None, "MISSING_STATE")
    journal = Journal(state)
    try:
        if operation == "propose":
            plan = propose(request["snapshot"], request["targets"],
                           fee_allowance_bps=request["fee_allowance_bps"],
                           slippage_bps=request["slippage_bps"],
                           ttl_ms=request.get("ttl_ms", 120_000))
            journal.save(plan, request["snapshot"])
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
    parser.add_argument("operation", choices=["normalize", "analyze", "propose", "approve", "dispatch", "record", "verify", "stop", "status"])
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

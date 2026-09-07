from .schemas import asset, canonical, require


POLICY_VALUES = {"ALLOW", "BLOCK"}


def account_key(account: dict) -> str:
    require(isinstance(account, dict), "INVALID_ACCOUNT")
    return canonical(account)


def normalize(policies) -> dict[str, str]:
    if policies is None:
        return {}
    result = {}
    if isinstance(policies, dict):
        rows = policies.items()
    else:
        require(isinstance(policies, list), "INVALID_POLICIES")
        rows = []
        for row in policies:
            require(isinstance(row, dict), "INVALID_POLICY")
            rows.append((row.get("asset"), row.get("policy")))
    for name, policy in rows:
        asset(name)
        require(policy in POLICY_VALUES, "INVALID_POLICY")
        if result.get(name) == "BLOCK" or policy == "BLOCK":
            result[name] = "BLOCK"
        else:
            result[name] = "ALLOW"
    return result


def context(policies) -> list[dict]:
    return [{"asset": name, "policy": policy}
            for name, policy in sorted(normalize(policies).items())]


def allowlist_configured(policies) -> bool:
    return any(policy == "ALLOW" for policy in normalize(policies).values())


def tradable(name: str, policies) -> bool:
    normalized = normalize(policies)
    if normalized.get(name) == "BLOCK":
        return False
    return not allowlist_configured(normalized) or normalized.get(name) == "ALLOW"


def conflict(name: str, current, desired, policies) -> dict | None:
    if current == desired:
        return None
    normalized = normalize(policies)
    if normalized.get(name) == "BLOCK":
        return {"asset": name, "reason": "BLOCKED_ASSET", "policy": "BLOCK"}
    if allowlist_configured(normalized) and normalized.get(name) != "ALLOW":
        return {"asset": name, "reason": "ASSET_NOT_ALLOWED", "policy": "ALLOWLIST"}
    return None

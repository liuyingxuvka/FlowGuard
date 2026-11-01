"""Reprove a stored witness on current code; the cache is never its verdict."""

import json

from .engine import _cached, cache_root, content_identity, prove
from .project import UnsupportedWorld, replay
from .report import item_id
from .skeleton import NoSkeleton, derive


def why(root, identifier=None, *, coverage=False, defects=False):
    if coverage or defects:
        try:
            spec = derive(root)
        except NoSkeleton as exc:
            return {"state": "unchecked", "matched": False, "reason": exc.facts["reason"]}
        identity = content_identity(spec)
        facts = _cached(cache_root(root) / "latest-audit-facts.json", identity)
        if facts is None:
            return {"state": "unchecked", "matched": False,
                    "reason": "no audit facts with a complete unchanged input footprint for this source; run audit"}
        key = "coverage" if coverage else "engine_defects"
        return {"state": "recorded", "matched": False, "identity": identity,
                key: facts.get(key, {} if coverage else []), "inputs": facts.get("inputs", [])}
    if identifier is None:
        raise ValueError("give a finding id, --coverage or --defects")
    if len(identifier) not in {6, 8} or identifier[:2] not in {"W-", "N-", "S-", "L-", "C-", "A-", "T-", "U-", "B-"} or any(char not in "0123456789abcdef" for char in identifier[2:]):
        raise ValueError("unknown witness id")
    path = cache_root(root) / "witnesses" / (identifier + ".json")
    try:
        candidate = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("no stored proof recipe for " + identifier) from exc
    if item_id(candidate["semantic"], length=len(identifier) - 2) != identifier:
        raise ValueError("stored witness semantic identity changed")
    try:
        result = prove(root, candidate, persist=False)
    except NoSkeleton as exc:
        return {"state": "unchecked", "matched": False, "reason": exc.facts["reason"]}
    result["label"] = candidate.get("label", candidate["semantic"].get("kind", "finding"))
    if candidate.get("origin"):
        result["origin"] = candidate["origin"]
    result["details"] = {key: candidate[key] for key in ("search", "answers", "comparison", "effects", "dead_code") if key in candidate}
    if candidate.get("rule_evidence"):
        result["details"]["rule"] = {key: candidate["rule_evidence"][key] for key in (
            "rule", "message", "fixture", "path", "line", "provenance",
        ) if key in candidate["rule_evidence"]}
    if result.get("evidence"):
        result["details"]["versions"] = result["evidence"]
    if result.get("matched"):
        prefix = list(candidate.get("prefix", []))
        if candidate["semantic"].get("check") == "GC6":
            prefix.append(candidate["violation"]["call"])
        try:
            facts = replay(derive(root), prefix, candidate.get("start", {}), timeout=300)
            result["trace"] = [{key: row[key] for key in ("call", "outcome", "exception") if key in row}
                               for row in facts["steps"]]
        except UnsupportedWorld as exc:
            result["trace_reason"] = str(exc)
    return result

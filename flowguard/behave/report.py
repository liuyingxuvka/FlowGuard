"""Small output derived from execution extent, never a saved green verdict."""

from __future__ import annotations

import hashlib
import json


def item_id(semantic, *, length=4):
    incidental = {"seed", "prefix", "trace", "order", "timestamp", "identity", "engine"}
    subject = {key: value for key, value in semantic.items() if key not in incidental}
    kind = {"GC1": "N", "GC3": "S"}.get(subject.get("check"), "W")
    return kind + "-" + hashlib.sha256(json.dumps(subject, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()[:length]


def render(result, *, as_json=False):
    runs = result["runs"]
    extent = {"world_runs": len(runs), "sampled": sum(not run["facts"]["extent"]["complete"] for run in runs),
              "capped": sum(run["facts"]["extent"]["capped"] for run in runs), "unsupported": len(result["errors"])}
    items = sorted((item for item in result["items"] if item.get("proof", {}).get("matched")
                    and item["proof"].get("state") == "reproduced" and item["proof"].get("identity") == result["identity"]), key=lambda item: item["id"])
    coverage = {**result["coverage"], "hit_functions": len(result["coverage"]["hit_functions"])}
    unknown = [row for run in runs for check in ("reach", "stuck") for row in run["facts"].get(check, {}).get("unknown", [])]
    verdict = "BLOCKED" if items else "UNCHECKED"
    payload = {"verdict": verdict, "reached": "shipped reach and stuck checks", "extent": extent,
               "coverage": coverage, "missing_checks": result["missing_checks"], "unknown": unknown,
               "errors": result["errors"], "items": [{key: item[key] for key in ("id", "semantic", "label", "search", "explanations", "answers") if key in item} for item in items], "facts_reused": result["facts_reused"]}
    payload["test_scope"] = result.get("test_scope", {})
    payload["input_gaps"] = sorted({reason for run in runs for reason in run["facts"]["footprint"].get("untracked", [])})
    if as_json:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    lines = [f"{verdict} shipped reach and stuck checks; {len(runs)} world/seed runs; missing checks: " + ", ".join(result["missing_checks"]),
             f"scope: {extent['sampled']} sampled; {extent['capped']} capped; {extent['unsupported']} unsupported; facts reused {result['facts_reused']}",
             f"coverage: {len(result['coverage']['hit_functions'])}/{result['coverage']['known_functions']} known source functions; UI {result['coverage']['ui']}"]
    for run in runs:
        value = run["facts"]["extent"]
        extra = "" if run["facts"]["footprint"]["reusable"] else "; input footprint incomplete"
        lines.append(f"explored under shipped: world {run['world']}; seed {run['seed']}; steps {value['successful']}/{value['successful_step_budget']}; {value['reason']}" + extra)
    if result["coverage"]["front_doors"]:
        lines.append("unrecognized front doors: " + "; ".join(result["coverage"]["front_doors"]))
    lines.extend("not judged: " + row["world"] + ": " + row["reason"] for row in result["errors"])
    lines.extend("input scope: " + reason for reason in payload["input_gaps"])
    for item in items:
        semantic = item["semantic"]
        term = semantic.get("query") + "=" + repr(semantic["value"]) if semantic.get("kind") == "query" else semantic.get("kind", "") + " " + str(semantic.get("name", semantic.get("value")))
        explanation = ", ".join(row["setting"] + "=" + repr(row["value"]) for row in item.get("explanations", []))
        suffix = " (reached only with " + explanation + ")" if explanation else " (no one-setting variation reaches it)" if item["label"] == "NEVER REACHED" else ""
        if item["label"] == "STUCK":
            suffix = f" - no way out within {item['bounds']['depth']} actions (complete, {item['search']['visited']} states)"
        heading = "STUCK (1 entities)" if item["label"] == "STUCK" else item["label"]
        lines.append(heading + ": " + term + suffix + " · " + item["id"])
        for answer in item.get("answers", []):
            lines.append("  " + answer["call"]["name"] + " -> " + answer["outcome"] + (" " + repr(answer["exception"]["message"]) if answer["exception"] else ""))
        lines.append("python -m flowguard.behave why " + item["id"])
    lines.extend("UNKNOWN " + row["check"] + " search: " + row["extent"]["reason"] for row in unknown)
    return "\n".join(lines)

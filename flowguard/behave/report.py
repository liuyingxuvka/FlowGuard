"""Small output derived from execution extent, never a saved green verdict."""

from __future__ import annotations

import hashlib
import json


def item_id(semantic):
    incidental = {"seed", "prefix", "trace", "order", "timestamp", "identity", "engine"}
    subject = {key: value for key, value in semantic.items() if key not in incidental}
    return "W-" + hashlib.sha256(json.dumps(subject, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()[:16]


def render(result, *, as_json=False):
    runs = result["runs"]
    extent = {"world_runs": len(runs), "sampled": sum(not run["facts"]["extent"]["complete"] for run in runs),
              "capped": sum(run["facts"]["extent"]["capped"] for run in runs), "unsupported": len(result["errors"])}
    # This item implements the execution/proof core. No generic checker exists yet.
    payload = {"verdict": "UNCHECKED", "reached": "bounded exploration only", "extent": extent,
               "coverage": result["coverage"], "missing_checks": result["missing_checks"],
               "errors": result["errors"], "items": [], "facts_reused": result["facts_reused"]}
    if as_json:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    lines = [f"UNCHECKED bounded exploration only; {len(runs)} world/seed runs; generic checks not implemented",
             f"scope: {extent['sampled']} sampled; {extent['capped']} capped; {extent['unsupported']} unsupported; facts reused {result['facts_reused']}",
             f"coverage: {len(result['coverage']['hit_functions'])}/{result['coverage']['known_functions']} known source functions; UI {result['coverage']['ui']}"]
    for run in runs:
        value = run["facts"]["extent"]
        extra = "" if run["facts"]["footprint"]["reusable"] else "; input footprint incomplete"
        lines.append(f"explored under shipped: world {run['world']}; seed {run['seed']}; steps {value['successful']}/{value['successful_step_budget']}; {value['reason']}" + extra)
    if result["coverage"]["front_doors"]:
        lines.append("unrecognized front doors: " + "; ".join(result["coverage"]["front_doors"]))
    lines.extend("not judged: " + row["world"] + ": " + row["reason"] for row in result["errors"])
    return "\n".join(lines)

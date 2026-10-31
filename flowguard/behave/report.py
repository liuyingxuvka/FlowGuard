"""Small output derived from execution extent, never a saved green verdict."""

from __future__ import annotations

import hashlib
import json


def item_id(semantic, *, length=4):
    incidental = {"seed", "prefix", "trace", "order", "timestamp", "identity", "engine"}
    subject = {key: value for key, value in semantic.items() if key not in incidental}
    kind = "L" if subject.get("kind") in {"loading", "loading_crash"} else {"GC1": "N", "GC2": "C", "GC3": "S", "GC5": "A"}.get(subject.get("check"), "W")
    return kind + "-" + hashlib.sha256(json.dumps(subject, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()[:length]


def render(result, *, as_json=False):
    runs = result["runs"]
    extent = {"world_runs": len(runs), "sampled": sum(not run["facts"]["extent"]["complete"] for run in runs),
              "capped": sum(run["facts"]["extent"]["capped"] for run in runs), "unsupported": len(result["errors"])}
    items = sorted((item for item in result["items"] if item.get("proof", {}).get("matched")
                    and item["proof"].get("state") == "reproduced" and item["proof"].get("identity") == result["identity"]), key=lambda item: item["id"])
    coverage = {**result["coverage"], "hit_functions": len(result["coverage"]["hit_functions"])}
    unknown = [row for run in runs for check in ("reach", "stuck", "agreement") for row in run["facts"].get(check, {}).get("unknown", [])]
    unknown.extend(result.get("saved_files", {}).get("unknown", []))
    settings = result.get("settings", {})
    unknown.extend(settings.get("unknown", []))
    verdict = "BLOCKED" if items else "UNCHECKED"
    reached = "shipped reach, stuck, agreement and setting checks"
    payload = {"verdict": verdict, "reached": reached, "extent": extent,
               "coverage": coverage, "missing_checks": result["missing_checks"], "unknown": unknown,
               "errors": result["errors"], "items": [{key: item[key] for key in ("id", "semantic", "label", "search", "explanations", "answers", "effects") if key in item} for item in items], "facts_reused": result["facts_reused"]}
    for item, row in zip(items, payload["items"]):
        if item.get("comparison"):
            row["comparison"] = {key: item["comparison"][key] for key in (
                "predictor", "action", "other_predictor", "predictor_mode", "other_mode", "option",
                "expected_permission", "observed", "answer", "before_key", "predictor_value", "other_predictor_value",
            ) if key in item["comparison"]}
    payload["settings"] = {key: settings[key] for key in ("information", "unknown", "profiles", "traces") if key in settings}
    payload["advice"] = result.get("advice", [])
    payload["test_scope"] = result.get("test_scope", {})
    payload["saved_files"] = {key: value for key, value in result.get("saved_files", {}).items() if key != "candidates"}
    payload["input_gaps"] = sorted({reason for run in runs for reason in run["facts"]["footprint"].get("untracked", [])})
    if as_json:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    lines = [f"{verdict} {reached}; {len(runs)} world/seed runs; missing checks: " + ", ".join(result["missing_checks"]),
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
        if semantic.get("kind") in {"loading", "loading_crash"}:
            term = semantic["source"] + " file " + semantic["file"][:12] + " -> " + semantic["loader"]
        if semantic.get("kind") == "agreement":
            term = semantic["predictor"] + " -> " + semantic["action"] + "; expected " + ("success" if semantic["expected"] else "refusal")
        if semantic.get("kind") == "setting":
            term = semantic["setting"]
        explanation = ", ".join(row["setting"] + "=" + repr(row["value"]) for row in item.get("explanations", []))
        suffix = " (reached only with " + explanation + ")" if explanation else " (no one-setting variation reaches it)" if item["label"] == "NEVER REACHED" else ""
        if item["label"] == "STUCK":
            suffix = f" - no way out within {item['bounds']['depth']} actions (complete, {item['search']['visited']} states)"
        if item["label"] == "ADVICE ONLY":
            effects = item.get("effects", {})
            suffix = f" - {effects.get('replays', 0)} public replays across {effects.get('profiles', 0)} profiles; changed queries: " + ", ".join(effects.get("query_changes", semantic.get("queries", []))) + "; no action or domain effect in these replays"
        heading = "STUCK (1 entities)" if item["label"] == "STUCK" else item["label"]
        lines.append(heading + ": " + term + suffix + " · " + item["id"])
        answers = item.get("answers", [])
        if not answers and isinstance(item.get("comparison", {}).get("answer"), dict):
            answers = [item["comparison"]["answer"]]
        for answer in answers:
            message = answer.get("exception")
            lines.append("  " + answer.get("call", {}).get("name", semantic.get("action", "answer")) + " -> " + answer.get("outcome", "unrecorded") + (" " + repr(message["message"]) if message else ""))
        lines.append("python -m flowguard.behave why " + item["id"])
    if settings.get("profiles"):
        lines.append("setting profiles: " + json.dumps(settings["profiles"], ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    for row in settings.get("information", []):
        detail = f"; {row['replays']} public replays" if "replays" in row else ""
        detail += f"; {row['profiles']} profiles" if "profiles" in row else ""
        lines.append("setting " + row["setting"] + ": " + row["label"] + detail)
    for row in payload["advice"]:
        lines.append("STATIC advice: " + (row if isinstance(row, str) else json.dumps(row, ensure_ascii=False, sort_keys=True)))
    for file in payload["saved_files"].get("files", []):
        lines.append("saved file: " + str(file["source"].get("revision", "unknown")) + " " + str(file["file"]["name"])
                     + ": " + file["status"] + " (" + ("HEAD fixture " if file["source"].get("kind") == "current-fixture" else "old ")
                     + str(file.get("old_outcome")) + ", current " + str(file.get("outcome", "unchecked")) + ")")
    if payload["saved_files"].get("no_saved_files"):
        lines.append("no saved files: give fixtures or a release base")
    if payload["saved_files"].get("fixture_scope"):
        lines.append("committed fixture scope: .json only; other formats not screened")
    for row in unknown:
        scope = " " + row["setting"] if row.get("setting") else ""
        if "profile" in row:
            scope += " profile " + json.dumps(row["profile"], ensure_ascii=False, sort_keys=True)
        lines.append("UNKNOWN " + row["check"] + scope + ": " + row.get("reason", row.get("extent", {}).get("reason", "unjudged scope")))
    return "\n".join(lines)

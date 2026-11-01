"""Small output derived from execution extent, never a saved green verdict."""

from __future__ import annotations

import hashlib
import json


def item_id(semantic, *, length=4):
    incidental = {"seed", "prefix", "trace", "order", "timestamp", "identity", "engine"}
    subject = {key: value for key, value in semantic.items() if key not in incidental}
    if subject.get("check") == "GC8":
        kind = {"lost": "L", "new_stuck": "S", "new_contradiction": "C", "transition": "T", "new_goal": "N", "world_unbuildable": "U"}.get(subject.get("kind"), "W")
    else:
        kind = "L" if subject.get("kind") in {"loading", "loading_crash"} else {"GC1": "N", "GC2": "C", "GC3": "S", "GC5": "A", "GC6": "C"}.get(subject.get("check"), "W")
    return kind + "-" + hashlib.sha256(json.dumps(subject, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()[:length]


def render(result, *, as_json=False):
    runs = result["runs"]
    extent = {"world_runs": len(runs), "sampled": sum(not run["facts"]["extent"]["complete"] for run in runs),
              "capped": sum(run["facts"]["extent"]["capped"] for run in runs), "unsupported": len(result["errors"])}
    order = {kind: index for index, kind in enumerate("LNSUCXBRVTGPAE")}
    items = sorted((item for item in result["items"] if item.get("proof", {}).get("matched")
                    and item["proof"].get("state") == "reproduced" and item["proof"].get("identity") == result["identity"]), key=lambda item: item["id"])
    items.sort(key=lambda item: (order.get(item["id"][0], len(order)), item["id"]))
    coverage = {**result["coverage"], "hit_functions": len(result["coverage"]["hit_functions"])}
    coverage.pop("hit_lines", None)  # Full execution lines stay in the on-demand coverage facts.
    unknown = [row for run in runs for check in ("reach", "stuck", "agreement", "crashes") for row in run["facts"].get(check, {}).get("unknown", [])]
    unknown.extend(result.get("saved_files", {}).get("unknown", []))
    test_starts = result.get("test_starts", {})
    unknown.extend(test_starts.get("unknown", []))
    test_probes = result.get("test_probes", {})
    for name in ("agreement", "crashes"):
        unknown.extend(test_probes.get(name, {}).get("unknown", []))
    test_extent = test_starts.get("extent")
    if test_extent:
        extent["test_start_runs"] = test_starts.get("runs", 0)
        extent["sampled"] += not test_extent["complete"]
        extent["capped"] += test_extent["capped"]
    settings = result.get("settings", {})
    unknown.extend(settings.get("unknown", []))
    difference = result.get("diff", {})
    unknown.extend({"check": "GC8", **row} for row in difference.get("unknown", []))
    scope = result.get("coverage", {})
    changed = scope.get("changed_lines", [])
    unhit = scope.get("unhit_lines", changed)
    changed_run = len(changed) - len(unhit)
    gaps = (unknown or result["errors"] or result["missing_checks"] or extent["sampled"]
            or extent["capped"] or scope.get("front_doors") or scope.get("scope_unknown")
            or result.get("engine_defects") or not runs)
    verdict = "BLOCKED" if items else "CLEAR" if changed_run and not gaps else "UNCHECKED"
    modules = scope.get("modules", {})
    least = min(([name, *counts] for name, counts in modules.items() if counts[0] < counts[1]),
                key=lambda row: (row[1] / row[2], row[0]), default=None)
    reached = "shipped reach, stuck, agreement, setting and crash/refusal checks"
    fallback = result.get("fallback")
    if fallback:
        reached = "static skeleton diagnostics; behavior not explored"
    if difference:
        reached += " and change comparison"
    payload = {"verdict": verdict, "reached": reached, "extent": extent,
               "coverage": coverage, "missing_checks": result["missing_checks"], "unknown": unknown,
               "errors": result["errors"], "items": [{key: item[key] for key in ("id", "semantic", "label", "search", "explanations", "answers", "effects", "goal", "dead_code", "reason", "origin") if key in item} for item in items], "facts_reused": result["facts_reused"]}
    payload.update(word=verdict, exit=0, new=len(items), existing=0,
                   explored=[coverage["hit_functions"], coverage["known_functions"]], least=least,
                   change_lines=[changed_run, len(changed)], moved=result.get("moved", []),
                   tree=scope.get("tree"), dirty_files=scope.get("dirty_files", []),
                   elapsed_seconds=scope.get("elapsed_seconds"), engine_defects=result.get("engine_defects", []),
                   next=result.get("next") or ("python -m flowguard.behave why " + items[0]["id"] if items else
                        "python -m flowguard.behave why --coverage"))
    if fallback:
        payload["fallback"] = {key: fallback[key] for key in ("reason", "world_kind", "entries", "required", "corrections")}
    for item, row in zip(items, payload["items"]):
        if item.get("violation"):
            row["violation"] = {key: item["violation"][key] for key in (
                "call", "outcome", "exception", "before_key", "after_key", "outputs",
            ) if key in item["violation"]}
        if item.get("file_input"):
            row["file_input"] = item["file_input"]
        if item.get("diff_evidence"):
            evidence = item["diff_evidence"]
            row["diff_evidence"] = {key: evidence[key] for key in ("base_ref", "base_revision") if key in evidence}
            for side in ("old", "current"):
                if side in evidence:
                    row["diff_evidence"][side] = {key: evidence[side][key] for key in ("found", "matched", "divergence", "replay_found", "extent") if key in evidence[side]}
        row.update(kind=item["label"], subject=item["semantic"],
                   fact=item.get("search", item.get("diff_evidence", item.get("comparison", item.get("violation", {})))),
                   fix=["code"], proof="python -m flowguard.behave why " + item["id"])
        if item.get("comparison"):
            row["comparison"] = {key: item["comparison"][key] for key in (
                "predictor", "action", "other_predictor", "predictor_mode", "other_mode", "option",
                "expected_permission", "observed", "answer", "before_key", "predictor_value", "other_predictor_value",
            ) if key in item["comparison"]}
    payload["settings"] = {key: settings[key] for key in ("information", "unknown", "profiles", "traces") if key in settings}
    if difference:
        payload["diff"] = {key: difference[key] for key in (
            "base_ref", "base_revision", "base_identity", "current_identity", "configurations", "unknown", "transitions", "dead_code",
        ) if key in difference}
    payload["advice"] = result.get("advice", [])
    payload["test_scope"] = result.get("test_scope", {})
    payload["inputs"] = result.get("inputs", {})
    payload["test_starts"] = test_starts
    payload["test_probes"] = test_probes
    payload["saved_files"] = {key: value for key, value in result.get("saved_files", {}).items() if key != "candidates"}
    payload["input_gaps"] = sorted({reason for run in runs for reason in run["facts"]["footprint"].get("untracked", [])})
    if "textrules" in result:
        from flowguard.map.textrules import render as text_render
        payload["textrules"] = json.loads(text_render(result["textrules"], as_json=True))
    if as_json:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)
    first = f"{verdict} {len(items)} new · explored {coverage['hit_functions']}/{coverage['known_functions']} functions"
    if least:
        first += f" (least: {least[0]} {least[1]}/{least[2]})"
    if coverage.get("front_doors"):
        first += f" · not recognised: {len(coverage['front_doors'])} front doors"
    first += f" · change: {changed_run}/{len(changed)} lines run"
    if scope.get("elapsed_seconds") is not None:
        first += f" · {scope['elapsed_seconds']:.2f}s"
    first += " · tree " + str(scope.get("tree", "not recorded"))
    if scope.get("dirty_files"):
        count = scope["dirty_files"] if isinstance(scope["dirty_files"], int) else len(scope["dirty_files"])
        first += "+" + str(count) + " files"
    first += " · next: " + payload["next"]
    lines = [first,
             f"scope: {reached}; {len(runs)} world/seed runs; missing checks: " + ", ".join(result["missing_checks"]),
             f"scope: {extent['sampled']} sampled; {extent['capped']} capped; {extent['unsupported']} unsupported; facts reused {result['facts_reused']}",
             "coverage denominator: " + scope.get("function_scope", "known project source functions") + "; UI " + result["coverage"]["ui"]]
    if verdict == "UNCHECKED":
        lines.append("reason: " + ("no changed source line ran" if not changed_run else "required checks or explored scope remain incomplete"))
    if fallback:
        from .skeleton import render_fallback
        lines.append(render_fallback(fallback))
    for run in runs:
        value = run["facts"]["extent"]
        extra = "" if run["facts"]["footprint"]["reusable"] else "; input footprint incomplete"
        extra += f"; node cap {value['node_cap']}; alphabet cap {value['alphabet_cap']}" if "node_cap" in value else ""
        lines.append(f"explored under shipped: world {run['world']}; seed {run['seed']}; steps {value['successful']}/{value['successful_step_budget']}; {value['reason']}" + extra)
        if "elapsed_seconds" in run:
            lines.append(f"time: world {run['world']}; seed {run['seed']}; {run['elapsed_seconds']:.2f}s")
    if result["coverage"]["front_doors"]:
        lines.append("unrecognized front doors: " + "; ".join(result["coverage"]["front_doors"]))
    lines.extend("not judged: " + str(row.get("world", "source")) + ": " + row["reason"] for row in result["errors"])
    lines.extend("input scope: " + reason for reason in payload["input_gaps"])
    if difference:
        lines.append("base comparison: " + difference["base_ref"] + " (" + difference["base_revision"][:12] + "); only confirmed items below are findings")
    for item in items:
        semantic = item["semantic"]
        if semantic.get("check") == "GC6":
            violation = item["violation"]
            actual = violation["call"]
            file_input = item.get("file_input", {})
            def argument(value):
                if isinstance(value, dict) and set(value) == {"$file"}:
                    return "<file: " + file_input.get("kind", value["$file"]) + ">"
                return repr(value)
            arguments = [argument(value) for value in actual.get("args", [])]
            keywords = actual.get("kwargs", {})
            only_keyword = next(iter(keywords.values())) if len(keywords) == 1 else None
            if not arguments and isinstance(only_keyword, dict) and set(only_keyword) == {"$file"}:
                arguments.append(argument(only_keyword))
            else:
                arguments.extend(name + "=" + argument(value) for name, value in keywords.items())
            text = item["label"] + " " + actual["name"] + "(" + ", ".join(arguments) + ")"
            exception = violation.get("exception")
            if exception:
                text += ": " + exception["type"].rsplit(":", 1)[-1] + ": " + exception["message"].replace("\n", "\\n")
                source = exception.get("source")
                if source:
                    text += " (" + source["path"] + ":" + str(source["line"]) + ")"
            lines.append(item["id"] + " " + text + ". fix: code · why " + item["id"])
            if item.get("origin"):
                lines.append("  origin: " + item["origin"])
            lines.append("python -m flowguard.behave why " + item["id"])
            continue
        term = semantic.get("query") + "=" + repr(semantic["value"]) if semantic.get("kind") == "query" else semantic.get("kind", "") + " " + str(semantic.get("name", semantic.get("value")))
        if semantic.get("kind") in {"loading", "loading_crash"}:
            term = semantic["source"] + " file " + semantic["file"][:12] + " -> " + semantic["loader"]
        if semantic.get("kind") == "agreement":
            term = semantic["predictor"] + " -> " + semantic["action"] + "; expected " + ("success" if semantic["expected"] else "refusal")
        if semantic.get("kind") == "setting":
            term = semantic["setting"]
        if semantic.get("check") == "GC8":
            goal = item.get("goal", semantic.get("subject", {}))
            goal_kind = goal.get("kind")
            if goal_kind == "query":
                term = goal["query"] + "=" + repr(goal["value"])
            elif goal_kind == "action":
                term = "action " + goal["name"]
            elif goal_kind in {"option", "screen"}:
                term = goal_kind + " " + str(goal["value"])
            elif goal_kind == "transition":
                term = goal["query"] + ": " + repr(goal["before"]) + " -> " + repr(goal["value"]) + " via " + goal["action"]
            elif semantic.get("kind") == "new_contradiction":
                offered = {**semantic, **goal}
                term = offered["predictor"] + " -> " + offered["action"] + "; expected " + ("success" if offered["expected"] else "refusal")
            elif semantic.get("kind") == "world_unbuildable":
                term = str(semantic.get("world", goal.get("world", "world")))
                reason = item.get("reason", semantic.get("reason", goal.get("reason")))
                if reason:
                    term += ": " + reason
        explanation = ", ".join(row["setting"] + "=" + repr(row["value"]) for row in item.get("explanations", []))
        suffix = " (reached only with " + explanation + ")" if explanation else " (no one-setting variation reaches it)" if item["label"] == "NEVER REACHED" and semantic.get("check") != "GC8" else ""
        if item["label"] in {"STUCK", "NEW STUCK"}:
            suffix = f" - no way out within {item['bounds']['depth']} actions (complete, {item['search']['visited']} states)"
        if item["label"] == "ADVICE ONLY":
            effects = item.get("effects", {})
            suffix = f" - {effects.get('replays', 0)} public replays across {effects.get('profiles', 0)} profiles; changed queries: " + ", ".join(effects.get("query_changes", semantic.get("queries", []))) + "; no action or domain effect in these replays"
        heading = "STUCK (1 entities)" if item["label"] == "STUCK" else item["label"]
        lines.append(item["id"] + " " + heading + ": " + term + suffix + ". fix: code · why " + item["id"])
        if item.get("origin"):
            lines.append("  origin: " + item["origin"])
        for source in item.get("dead_code", []):
            text = "  DEAD CODE " + source["path"] + ":" + source["function"] + ": " + str(source["count"]) + " statement(s)"
            if source.get("example"):
                text += ", e.g. " + repr(source["example"])
            lines.append(text)
        answers = item.get("answers", [])
        if not answers and isinstance(item.get("comparison", {}).get("answer"), dict):
            answers = [item["comparison"]["answer"]]
        for answer in answers:
            message = answer.get("exception")
            lines.append("  " + answer.get("call", {}).get("name", semantic.get("action", "answer")) + " -> " + answer.get("outcome", "unrecorded") + (" " + repr(message["message"]) if message else ""))
        lines.append("python -m flowguard.behave why " + item["id"])
    if settings.get("profiles"):
        lines.append("setting profiles: " + "; ".join(
            ", ".join(name + "=" + repr(value) for name, value in row.items()) for row in settings["profiles"]))
    for row in settings.get("information", []):
        detail = f"; {row['replays']} public replays" if "replays" in row else ""
        detail += f"; {row['profiles']} profiles" if "profiles" in row else ""
        lines.append("setting " + row["setting"] + ": " + row["label"] + detail)
    for row in payload["advice"]:
        lines.append("STATIC advice: " + (row if isinstance(row, str) else "; ".join(name + "=" + repr(value) for name, value in row.items())))
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
        lines.append("UNKNOWN " + row.get("check", "scope") + scope + ": " + row.get("reason", row.get("extent", {}).get("reason", "unjudged scope")))
    if payload["engine_defects"]:
        lines.append("engine defect: " + str(len(payload["engine_defects"])) + " items did not replay (why --defects)")
    if "textrules" in result:
        lines.append(text_render(result["textrules"]))
    lines.append(f"audit: {len(items)} finding(s), {len(payload['advice'])} advice, {len(unknown)} coverage item(s)")
    return "\n".join(lines)

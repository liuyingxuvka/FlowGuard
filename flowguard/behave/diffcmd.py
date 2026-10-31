"""Two real source trees, concrete witnesses and bounded opposite-side proofs."""

from __future__ import annotations

import json
from pathlib import Path

from flowguard.map.common import atomic_write_text

from .checks import goals, matches
from .project import UnsupportedWorld, replay, state_key
from .skeleton import derive


def _summary(facts):
    return {key: facts[key] for key in ("found", "matched", "divergence", "extent", "origin") if key in facts}


def _replay(spec, witness, goal):
    return replay(spec, witness["prefix"], witness.get("start", {}), operation="prove",
                  options={"goal": goal, "outcomes": witness.get("outcomes")}, timeout=300)


def _seek(spec, goal, context, facts, bounds, known=()):
    known = [{**row, "semantic": {**row.get("semantic", goal), "origin": context.get("origin")}} for row in known]
    return replay(spec, context.get("prefix", []), context["start"], operation="directed", timeout=300,
                  options={"goal": goal, "states": facts.get("states", []), "known": list(known),
                           "origin": context.get("origin"), "secondary_seed": context["start"].get("seed", 0) + 1,
                           "secondary_steps": bounds["steps"], **{key: bounds[key] for key in ("depth", "node_cap", "alphabet_cap")}})


def _known(root, goal):
    from .engine import cache_root
    result = []
    for path in sorted((cache_root(root) / "witnesses").glob("*.json")):
        try:
            row = json.loads(path.read_text())
            subject = row.get("goal", row.get("search_goal", row["semantic"]))
            if matches(goal, subject):
                result.append({**{key: row[key] for key in ("prefix", "start", "outcomes") if key in row}, "semantic": goal})
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return result


def _witness(facts, goal):
    return next((row for row in facts.get("witnesses", []) if matches(goal, row["semantic"])), None)


def compare(root, base, *, worlds=None, seeds=(0, 1), steps=64, node_cap=1000, alphabet_cap=1000,
            use_cache=True, depth=5, targets=None, checks=True, saved=True, provided_only=False, known=()):
    """Discover candidates from facts; only fresh two-sided proof makes an item."""
    from .engine import _cached, cache_root, collect_saves, content_identity, footprint_identity, old_releases

    root = Path(root).resolve()
    history = old_releases(root, ref=base)
    if not history["sources"]:
        raise UnsupportedWorld("base source unavailable: " + str(history["unknown"]))
    source = history["sources"][0]
    old, current = source["spec"], derive(root)
    identity = content_identity(current)
    bounds = dict(steps=steps, depth=depth, node_cap=node_cap, alphabet_cap=alphabet_cap)
    contexts = [{"start": {"world": world, "seed": seed}, "prefix": []}
                for world in worlds or ("default", "small", "crowded") for seed in seeds]
    unknown, transitions, runs, items, seen = [], [], [], [], set()
    if saved and current.get("persistence"):
        inputs = collect_saves(root, steps=min(steps, 8), node_cap=node_cap, alphabet_cap=alphabet_cap, generate=not provided_only)
        unknown.extend(inputs["unknown"])
        for data in inputs["saves"]:
            if provided_only and data["source"]["kind"] != "provided-fixture":
                continue
            file = data["file"]
            for seed in seeds:
                contexts.append({"start": {"files": {file["name"]: file["bytes"]}, "seed": seed},
                                 "prefix": [{"receiver": "system", "name": current["persistence"]["load"], "args": [{"$file": file["name"]}], "replace": True}],
                                 "origin": {"kind": "saved-file", "file": file["sha256"], "name": file["name"]}, "saved_file": data})

    def native(spec, context):
        own = content_identity(spec)
        options = {key: bounds[key] for key in ("steps", "node_cap", "alphabet_cap")}
        options.update(seed=context["start"].get("seed", 0), checks=checks)
        token = state_key([own, context["start"], context["prefix"], options])
        path = cache_root(root) / ("diff-facts-" + token + ".json")
        facts = _cached(path, own) if use_cache else None
        if facts is None:
            facts = replay(spec, context["prefix"], context["start"], operation="diff", options=options, timeout=300)
            if footprint_identity(facts["footprint"]):
                atomic_write_text(path, json.dumps({"identity": own, "body": state_key(facts), "facts": facts}))
        return facts

    def submit(kind, goal, context, before, after, witness=None, native_case=None, dead_code=None, statement_witnesses=None):
        semantic = {"check": "GC8", "kind": kind, "subject": goal}
        if context.get("origin"):
            semantic["origin"] = context["origin"]
        key = state_key(semantic)
        if key in seen:
            return
        seen.add(key)
        case = {"semantic": semantic, "goal": goal, "base_ref": str(base), "base_revision": source["revision"],
                "prefix": list((witness or {}).get("prefix", context["prefix"])), "start": context["start"],
                "bounds": bounds, "context": context, "old_facts": {"states": before.get("states", [])},
                "current_facts": {"states": after.get("states", [])}, "witness": witness,
                "label": {"lost": "LOST", "new_goal": "NEVER REACHED", "new_stuck": "NEW STUCK",
                          "new_contradiction": "NEW CONTRADICTION", "transition": goal.get("direction", "NEW")}[kind]}
        if native_case:
            case["native_case"] = native_case
            for name in ("bounds", "search", "answers", "comparison"):
                if name in native_case:
                    case[name] = native_case[name]
        if dead_code:
            case["dead_code"] = dead_code
            case["statement_witnesses"] = statement_witnesses
        proof = prove(root, case)
        if proof["matched"]:
            items.append({**case, "id": proof["id"], "proof": proof, "diff_evidence": proof["evidence"]})
        else:
            row = {"goal": goal, "origin": context.get("origin"), "reason": proof.get("reason", proof["state"]), "evidence": proof.get("evidence")}
            (transitions if kind == "transition" else unknown).append(row)

    for context in contexts:
        try:
            before, after = native(old, context), native(current, context)
            runs.append({"world": context["start"].get("world", "saved-file"), "seed": context["start"].get("seed", 0), "reused": False, "facts": after})
            selected = targets if targets is not None else goals(old)
            for goal in selected:
                if goal.get("kind") == "new_goal":
                    submit("new_goal", goal["goal"], context, before, after)
                    continue
                if goal.get("kind") in {"new_stuck", "new_contradiction"}:
                    category = "stuck" if goal["kind"] == "new_stuck" else "agreement"
                    for candidate in after.get(category, {}).get("candidates", []):
                        submit(goal["kind"], candidate.get("search_goal", candidate["semantic"]), context, before, after, native_case=candidate)
                    unknown.extend({"side": "current", **row} for row in after.get(category, {}).get("unknown", []))
                    continue
                if goal.get("kind") == "transition":
                    side = after if goal.get("direction") == "NEW" else before
                    positive = _witness(side, {key: value for key, value in goal.items() if key != "direction"})
                    if positive:
                        submit("transition", goal, context, before, after, positive)
                    else:
                        transitions.append({"goal": goal, "reason": "no actual positive transition witness"})
                    continue
                positive = _witness(before, goal)
                if positive is None:
                    supplied = [row for row in known if matches(goal, row.get("semantic", {}))]
                    sought = _seek(old, goal, context, before, bounds, [*_known(root, goal), *supplied])
                    if sought["found"]:
                        positive = {"prefix": sought["prefix"], "start": sought.get("start", context["start"]), "semantic": goal}
                    else:
                        unknown.append({"goal": goal, "reason": "no old positive witness", "extent": sought["extent"]})
                        continue
                if _witness(after, goal) is None:
                    submit("lost", goal, context, before, after, positive)
            if targets is None:
                old_goals = {state_key(goal) for goal in goals(old)}
                for goal in goals(current):
                    if state_key(goal) not in old_goals and _witness(after, goal) is None:
                        submit("new_goal", goal, context, before, after)
                for category, kind in (("stuck", "new_stuck"), ("agreement", "new_contradiction")):
                    for candidate in after.get(category, {}).get("candidates", []):
                        submit(kind, candidate.get("search_goal", candidate["semantic"]), context, before, after, native_case=candidate)
                for side, other, direction in ((before, after, "LOST"), (after, before, "NEW")):
                    for witness in side.get("witnesses", []):
                        goal = witness["semantic"]
                        if goal.get("kind") == "transition" and _witness(other, goal) is None:
                            submit("transition", {**goal, "direction": direction}, context, before, after, witness)
                present = {row["id"]: row for row in current.get("statements", []) if row["unambiguous"]}
                grouped = {}
                for witness in before.get("witnesses", []):
                    goal = witness["semantic"]
                    row = present.get(goal.get("statement")) if goal.get("kind") == "statement" else None
                    if row and row["id"] not in after["execution"].get("hit_statements", []):
                        grouped.setdefault((row["path"], row["function"]), []).append((row, witness))
                for (path, function), rows in grouped.items():
                    goal = {"kind": "statement", "statements": sorted({row["id"] for row, _ in rows})}
                    detail = [{"path": path, "function": function, "count": len(goal["statements"]), "example": rows[0][0]["text"], "statements": goal["statements"]}]
                    submit("lost", goal, context, before, after, rows[0][1], dead_code=detail,
                           statement_witnesses=list({state_key(witness["prefix"]): witness for _, witness in rows}.values()))
        except (UnsupportedWorld, ValueError, KeyError) as exc:
            unknown.append({"origin": context.get("origin"), "world": context["start"].get("world"), "reason": str(exc)})
    hits = {name for run in runs for name in run["facts"]["execution"]["hit_functions"]}
    return {"identity": identity, "runs": runs, "errors": [], "items": items, "facts_reused": 0,
            "coverage": {"hit_functions": sorted(hits), "known_functions": len(current["source_functions"]), "ui": "derived", "front_doors": current["unknown"]},
            "missing_checks": ["GC7", "GC9"], "diff": {"base_ref": str(base), "base_revision": source["revision"],
            "base_identity": source["identity"], "current_identity": identity,
            "configurations": {"base": old["shipped"], "current": current["shipped"]}, "unknown": unknown, "transitions": transitions}}


def prove(root, candidate, *, persist=True):
    """Fresh opposite-side execution, followed by bounded proof where required."""
    from .engine import cache_root, content_identity, footprint_identity, old_releases, prove as prove_native
    from .report import item_id

    history = old_releases(root, ref=candidate["base_revision"])
    if not history["sources"]:
        return {"matched": False, "state": "unchecked", "reason": "base source unavailable"}
    old, current = history["sources"][0]["spec"], derive(root)
    identity = content_identity(current)
    kind, goal = candidate["semantic"]["kind"], candidate["goal"]
    context, bounds = candidate["context"], candidate["bounds"]
    evidence, observed = {}, []
    try:
        if context.get("saved_file"):
            saved = context["saved_file"]
            load = {"name": old["persistence"]["load"], "args": [{"$file": saved["file"]["name"]}], "replace": True}
            accepted = replay(old, [load], context["start"], operation="loading-proof", options={"outcome": "success"})
            observed.append(accepted)
            if not accepted["matched"]:
                raise UnsupportedWorld("the actual base loader did not accept the provided saved bytes")
        if kind in {"lost", "transition"}:
            witness = candidate["witness"]
            positive_spec = current if kind == "transition" and goal.get("direction") == "NEW" else old
            opposite = old if positive_spec is current else current
            positive = _replay(positive_spec, witness, goal)
            observed.append(positive)
            if not positive["matched"]:
                raise UnsupportedWorld("the positive source witness no longer reproduces")
            if candidate.get("statement_witnesses"):
                covered = set(positive["execution"].get("hit_statements", []))
                for statement_witness in candidate["statement_witnesses"]:
                    receipt = _replay(old, statement_witness, goal)
                    observed.append(receipt)
                    covered.update(receipt["execution"].get("hit_statements", []))
                if not set(goal["statements"]) <= covered:
                    raise UnsupportedWorld("not every old statement has a fresh positive execution")
            negative = _replay(opposite, witness, goal)
            observed.append(negative)
            evidence.update({"current" if positive_spec is current else "old": _summary(positive),
                             "old" if opposite is old else "current": _summary(negative)})
            if negative["matched"]:
                return {"matched": False, "state": "no-longer-reproduces", "reason": "the opposite source reproduces the witness", "evidence": evidence}
            last = negative.get("last", {})
            aligned = any(row["query"] == goal.get("query") and state_key(row["args"]) == state_key(goal.get("args", []))
                          and state_key(row["value"]) == state_key(goal.get("before"))
                          for row in last.get("before_observations", {}).get("values", []))
            if kind == "transition" and aligned and last.get("call", {}).get("name") == goal.get("action"):
                matched = True
            else:
                search_goal = {key: value for key, value in goal.items() if key != "direction"}
                if kind == "transition" and goal.get("action") not in opposite["actions"]:
                    search_goal.pop("action", None)
                facts = candidate["old_facts"] if opposite is old else candidate["current_facts"]
                known = [*_known(root, search_goal), {**witness, "semantic": search_goal}]
                known.extend({**row, "semantic": search_goal} for row in candidate.get("statement_witnesses", []))
                negative = _seek(opposite, search_goal, context, facts, bounds, known)
                observed.append(negative)
                evidence["opposite_search"] = _summary(negative)
                matched = not negative["found"] and negative["extent"]["complete"]
        elif kind == "new_goal":
            negative = _seek(current, goal, context, candidate["current_facts"], bounds, _known(root, goal))
            observed.append(negative)
            evidence["current"] = _summary(negative)
            matched = not negative["found"] and negative["extent"]["complete"]
        elif kind in {"new_stuck", "new_contradiction"}:
            native = candidate["native_case"]
            now = prove_native(root, native, persist=False)
            evidence["current"] = _summary(now.get("proof", {}))
            if not now["matched"]:
                if not now.get("proof", {}).get("extent", {}).get("complete", True):
                    raise UnsupportedWorld("the current no-exit proof was capped or incomplete")
                raise UnsupportedWorld("the current native finding no longer reproduces")
            observed.append(now["proof"])
            if kind == "new_stuck":
                initial_goal = {key: value for key, value in native["search_goal"].items() if key != "comparison"}
                same_value = _replay(old, {"prefix": native["prefix"], "start": native["start"]}, initial_goal)
                observed.append(same_value)
                if not same_value["matched"]:
                    raise UnsupportedWorld("the counterpart public prefix did not reproduce the starting categorical value")
                previous = replay(old, [], native["start"], operation="search", options={"goal": native["search_goal"], "prefix": native["prefix"], **native["bounds"]}, timeout=300)
                matched = previous["found"] and len(previous["prefix"]) > len(native["prefix"])
            else:
                previous = replay(old, native["prefix"], native["start"], operation="agreement-proof", options={"comparison": native["comparison"]}, timeout=300)
                matched = not previous["matched"] and not previous["unknown"] and previous["compared"] == 1
            observed.append(previous)
            evidence.update(current={"matched": True}, old=_summary(previous))
        else:
            raise UnsupportedWorld("this change item kind is not implemented")
        if any(not footprint_identity(row.get("footprint", {})) for row in observed):
            raise UnsupportedWorld("a source execution footprint is incomplete or changed")
        result = {"matched": bool(matched), "state": "reproduced" if matched else "unchecked", "identity": identity,
                  "id": item_id(candidate["semantic"]), "semantic": candidate["semantic"], "evidence": evidence}
        if not matched:
            result["reason"] = "opposite-side proof was capped, incomplete or did not establish a change"
        if persist and matched:
            path = cache_root(root) / "witnesses" / (result["id"] + ".json")
            atomic_write_text(path, json.dumps({**candidate, "identity": identity}, ensure_ascii=False))
        return result
    except (UnsupportedWorld, ValueError, KeyError) as exc:
        return {"matched": False, "state": "unchecked", "reason": str(exc), "evidence": evidence}

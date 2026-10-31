"""Reach and stuck candidates derived from concrete native observations."""

from __future__ import annotations

import json

from .explore import directed_search, focused_search, observations, plain
from .project import UnsupportedWorld


def goals(spec):
    result = [{"kind": "query", "receiver": "system", "query": name,
               "entity": spec["parameters"][name][0]["entity"], "value": value}
              for name, values in spec["status_values"].items() for value in values]
    result += [{"kind": "action", "receiver": "system", "name": name, "outcome": "success"} for name in spec["actions"]]
    result += [{"kind": kind, "value": value, "ui_class": spec["ui"]} for kind, field in (("option", "options"), ("screen", "screens"))
               for value in spec["ui_facts"][field]]
    return sorted(result, key=lambda value: ({"query": 0, "action": 1, "option": 2, "screen": 3}[value["kind"]], json.dumps(value, sort_keys=True)))


def matches(goal, term):
    return all(term.get(key) == value for key, value in goal.items() if key != "entity")


def variations(spec):
    for name, value in sorted(spec["shipped"].items()):
        choices = [not value] if type(value) is bool else [0, 1, 2, value - 1, value + 1, value * 2] if type(value) is int else []
        for changed in sorted(set(choices)):
            if changed != value:
                yield name, changed


def reach(session, facts, *, known=(), witnessed=(), states=(), origin=None, depth=5, node_cap=None, alphabet_cap=None):
    """Known witnesses, a second fixed seed, then bounded complete directed search."""
    extent = facts["extent"]
    bounds = {"depth": depth, "node_cap": node_cap or extent["node_cap"],
              "alphabet_cap": alphabet_cap or extent["alphabet_cap"]}
    witnessed = [*facts["witnesses"], *witnessed]
    candidates, unknown, covered, unjudged = [], [], [], []
    original = session.start
    concrete = [*states, *facts["states"]]
    variant_facts = {}
    for goal in goals(session.spec):
        if any(matches(goal, row["semantic"]) for row in witnessed):
            continue
        relevant = [row for row in known if row["semantic"].get("origin") == origin and matches(goal, row["semantic"])]
        result = directed_search(session, goal=goal, known=relevant, states=concrete, origin=origin,
                                 secondary_seed=int(original.get("seed", 0)) + 1,
                                 secondary_steps=extent["successful_step_budget"], **bounds)
        if result["found"]:
            covered.append({"goal": goal, "origin": result["origin"], "prefix": result["prefix"], "start": result.get("start", original)})
            concrete.append({"prefix": result["prefix"], "start": result.get("start", original), "observations": observations(session), "outcomes": list(session.outcomes)})
            continue
        if not result["extent"]["complete"]:
            unknown.append({"check": "GC1", "goal": goal, "extent": result["extent"]})
            continue
        explanations = []
        for name, changed in variations(session.spec):
            key = (name, changed)
            try:
                if key not in variant_facts:
                    session.start = {**original, "settings": {name: changed}}
                    session.reset()
                    from .explore import explore
                    variant_facts[key] = explore(session, seed=int(original.get("seed", 0)),
                                                  steps=extent["successful_step_budget"],
                                                  node_cap=bounds["node_cap"], alphabet_cap=bounds["alphabet_cap"])
                if variant_facts[key] is None:
                    continue
                if any(matches(goal, witness["semantic"]) for witness in variant_facts[key]["witnesses"]):
                    explanations.append({"setting": name, "value": changed})
            except UnsupportedWorld as exc:
                variant_facts[key] = None
                unjudged.append({"setting": name, "value": changed, "reason": str(exc)})
            finally:
                session.start = original
        label = "NOT REACHED UNDER SHIPPED" if explanations else "NEVER REACHED"
        if explanations and all(type(session.spec["shipped"][row["setting"]]) is bool for row in explanations):
            label = "OFF BY DEFAULT"
        candidates.append({"semantic": {"check": "GC1", **goal}, "negative": True, "label": label,
                           "prefix": result["search_prefix"], "start": result["start"],
                           "bounds": bounds, "explanations": explanations, "search": result["extent"]})
    session.start = original
    session.reset()
    return {"candidates": candidates, "unknown": unknown, "coverage": covered, "not_judged": unjudged}


def stuck(session, facts, *, states=(), depth=5, node_cap=None, alphabet_cap=None):
    """An abstract candidate needs an exact public prefix and concrete no-exit search."""
    concrete = [*states, *facts["states"]]
    by_prefix, left, seen, candidates, unknown = {}, set(), set(), [], []
    original = session.start
    for state in concrete:
        key = json.dumps([state.get("start", original), state["prefix"]], sort_keys=True)
        previous = by_prefix.get(json.dumps([state.get("start", original), state["prefix"][:-1]], sort_keys=True))
        if previous:
            before = {(row["query"], tuple(row["args"])): row["value"] for row in previous["observations"]["values"]}
            for row in state["observations"]["values"]:
                old = before.get((row["query"], tuple(row["args"])))
                if row["query"] in session.spec["status_values"] and old != row["value"] and old is not None:
                    left.add((row["query"], old))
        by_prefix[key] = state
    bounds = {"depth": depth, "node_cap": node_cap or facts["extent"]["node_cap"],
              "alphabet_cap": alphabet_cap or facts["extent"]["alphabet_cap"]}
    for state in facts["states"]:
        for term in state["observations"]["values"]:
            if (term["query"], term["value"]) not in left:
                continue
            session.start = state.get("start", original)
            session.reset(state["prefix"])
            observed = observations(session, all_queries=True)
            context = {row["query"]: row["value"] for row in observed["values"]
                       if row["entity"] == term["entity"] and row["args"] == term["args"] and type(row["value"]) in {str, bool, type(None)}}
            key = json.dumps([term["query"], term["value"], term["args"], context], sort_keys=True)
            if key in seen:
                continue
            seen.add(key)
            goal = {"kind": "query", "query": term["query"], "args": term["args"], "value": term["value"], "comparison": "ne"}
            selected = {"query": term["query"], "identifier": term["args"][0]}
            probe = focused_search(session, goal=goal, prefix=state["prefix"], related=selected, **{**bounds, "depth": 1})
            if probe["found"]:
                continue
            result = focused_search(session, goal=goal, prefix=state["prefix"], related=selected, **bounds)
            if not result["found"]:
                if not result["extent"]["complete"]:
                    unknown.append({"check": "GC3", "goal": goal, "extent": result["extent"]})
                else:
                    candidates.append({"semantic": {"check": "GC3", "kind": "query", "query": term["query"],
                                                      "entity": term["entity"], "value": term["value"], "context": context},
                                       "negative": True, "search_goal": goal, "label": "STUCK", "prefix": state["prefix"],
                                       "start": session.start, "bounds": {**bounds, "related": selected},
                                       "search": result["extent"], "answers": result["answers"]})
    session.start = original
    session.reset()
    terminals = [{"query": name, "value": value} for name, values in session.spec["status_values"].items()
                 for value in values if (name, value) not in left and any(row["query"] == name and row["value"] == value for state in concrete for row in state["observations"]["values"])]
    return {"candidates": candidates, "unknown": unknown, "terminal_observed": terminals}


def saved_files(session, saves, *, seed=0, steps=64, node_cap=1000, alphabet_cap=1000):
    """Load exact old file bytes, then reuse the same supported native checks."""
    import base64
    import hashlib

    from .explore import explore

    original, base_prefix = session.start, list(session.base_prefix)
    candidates, files, unknown = [], [], []
    missing = ["GC" + str(number) for number in (2, 5, 6, 7, 8, 9)]
    loader = session.spec.get("persistence", {}).get("load") if session.spec.get("persistence") else None
    try:
        for saved in saves:
            source, file = saved.get("source", {}), saved.get("file", {})
            schema = saved.get("schema")
            provenance = {"source": source, "schema": schema,
                          "file": {key: file.get(key) for key in ("name", "sha256")}}
            summary = {**provenance, "old_outcome": saved.get("old_load", {}).get("outcome")}
            files.append(summary)
            if not loader:
                summary.update(status="unchecked", reason="no current public loader was derived")
                unknown.append({"check": "GC4", **provenance, "reason": summary["reason"]})
                continue
            try:
                if not isinstance(source.get("revision"), str) or not source["revision"]:
                    raise UnsupportedWorld("saved source revision is missing")
                if not isinstance(file.get("name"), str) or not isinstance(file.get("bytes"), str):
                    raise UnsupportedWorld("saved file name or exact bytes are missing")
                try:
                    payload = base64.b64decode(file["bytes"], validate=True)
                except ValueError as exc:
                    raise UnsupportedWorld("saved file bytes are not valid base64") from exc
                if hashlib.sha256(payload).hexdigest() != file.get("sha256"):
                    raise UnsupportedWorld("saved file bytes do not match their content identity")
                session.base_prefix = []
                start = {"files": {file["name"]: file["bytes"]}, "seed": seed}
                session.reset([], start=start)
                load = {"receiver": "system", "name": loader, "args": [{"$file": file["name"]}], "replace": True}
                row = session.step(load)
                summary.update(outcome=row["outcome"], exception=row["exception"])
                semantic = {"check": "GC4", "source": source["revision"], "schema": schema,
                            "file": file["sha256"], "loader": session.spec["system"] + "." + loader}
                if row["outcome"] == "crash" or row["outcome"] == "refusal" and summary["old_outcome"] == "success":
                    label = "LOADING CRASH" if row["outcome"] == "crash" else "LOST"
                    kind = "loading_crash" if row["outcome"] == "crash" else "loading"
                    candidates.append({"semantic": {**semantic, "kind": kind, "label": label},
                                       "label": label, "prefix": [load], "outcomes": [row["outcome"]],
                                       "start": start, "saved_file": saved})
                    summary["status"] = "candidate"
                    continue
                if row["outcome"] == "refusal":
                    summary["status"] = "designed_progress" if summary["old_outcome"] == "refusal" else "unchecked"
                    if summary["status"] == "unchecked":
                        unknown.append({"check": "GC4", **provenance, "reason": "no accepted or declared-refusal old load was observed"})
                    continue
                summary["status"] = "loaded"
                session.base_prefix = [load]
                origin = {"kind": "saved-file", "source": source["revision"], "file": file["sha256"], "schema": schema}
                facts = explore(session, seed=seed, steps=steps, node_cap=node_cap, alphabet_cap=alphabet_cap)
                reached = reach(session, facts, origin=origin)
                trapped = stuck(session, facts)
                for check in (reached, trapped):
                    candidates.extend({**candidate, "semantic": {**candidate["semantic"], "origin": origin},
                                       "saved_file": saved} for candidate in check["candidates"])
                    unknown.extend({**item, "origin": origin} for item in check["unknown"])
                unknown.extend({"check": "GC1", "origin": origin, **item} for item in reached["not_judged"])
                summary["extent"] = facts["extent"]
                summary["missing_checks"] = missing
            except UnsupportedWorld as exc:
                summary.update(status="unchecked", reason=str(exc))
                unknown.append({"check": "GC4", **provenance, "reason": str(exc)})
    finally:
        session.base_prefix = base_prefix
        session.reset(start=original)
    return {"candidates": candidates, "files": files, "unknown": unknown, "missing_checks": missing}

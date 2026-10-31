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


def reach(session, facts, *, known=(), witnessed=(), states=(), depth=5, node_cap=None, alphabet_cap=None):
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
        relevant = [row for row in known if matches(goal, row["semantic"])]
        result = directed_search(session, goal=goal, known=relevant, states=concrete,
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

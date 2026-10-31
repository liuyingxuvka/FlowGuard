"""Concrete finite walks and bounded search over the shared native session."""

from __future__ import annotations

from collections import deque
import itertools
import json
import random

from .project import UnsupportedWorld, state_key


def plain(pack):
    nodes = pack["nodes"]
    def read(value):
        if not isinstance(value, dict):
            return value
        if "float" in value:
            return float.fromhex(value["float"])
        if "enum" in value:
            return value["value"]
        if "ref" not in value:
            raise UnsupportedWorld("this query value has no finite scalar view")
        node = nodes[value["ref"]]
        if node["type"] in {"builtins:list", "builtins:tuple", "builtins:set", "builtins:frozenset"}:
            return [read(item) for item in node["items"]]
        if node["type"] == "builtins:dict":
            return {read(key): read(item) for key, item in node["items"]}
        raise UnsupportedWorld("object-valued query needs an explicit world")
    return read(pack["root"])


def evaluate(session, goal):
    if goal.get("kind", "query") == "action":
        row = session.last
        return bool(row and row["call"]["name"] == goal["name"] and row["call"].get("receiver", "system") == goal.get("receiver", "system") and row["outcome"] == goal["outcome"])
    receiver = goal.get("receiver", "system")
    recipe = {"receiver": receiver, "name": goal["query"], "args": goal.get("args", []), "kwargs": goal.get("kwargs", {})}
    if goal.get("property"):
        recipe["property"] = True
    row = session.step(recipe, keep=False)
    if row["outcome"] != "success" or row["before_key"] != row["after_key"]:
        raise UnsupportedWorld("a goal query is not a pure successful observation")
    value = plain(row["value"])
    return value != goal["value"] if goal.get("comparison") == "ne" else value == goal["value"]


def _numbers(value):
    if type(value) is int:
        return {value}
    if isinstance(value, list):
        return set().union(*(_numbers(item) for item in value)) if value else set()
    if isinstance(value, dict) and "ref" not in value:
        return set().union(*(_numbers(item) for item in value.values())) if value else set()
    return set()


def _identifiers(session):
    return {kind: plain(session.query("system", item["list"])) for kind, item in session.spec["entities"].items()}


def _alphabet(session, only=None, domains=None, alphabet_cap=1000):
    spec = session.spec
    identifiers = _identifiers(session)
    numbers = {0, 1, 2} | _numbers(spec["shipped"])
    for node in session.current["graph"]["nodes"]:
        numbers |= _numbers(node.get("items", [])) | _numbers(node.get("attributes", []))
    candidates = []
    truncated = False
    for name in sorted(only if only is not None else spec["actions"]):
        if name not in spec["parameters"] or name.startswith("_"):
            raise UnsupportedWorld("unknown action in finite slice: " + name)
        choices = []
        for row in spec["parameters"][name]:
            explicit = (domains or {}).get(name, {}).get(row["name"])
            if explicit is not None:
                values = explicit
            elif row.get("entity"):
                values = identifiers[row["entity"]]
            else:
                literals = row.get("literals", [])
                strings = [value for value in literals if isinstance(value, str)]
                if strings or isinstance(row.get("default"), str) or row.get("annotation") == "str":
                    values = [*strings, *([row["default"]] if isinstance(row.get("default"), str) else [])]
                elif type(row.get("default")) is bool or row.get("annotation") == "bool":
                    values = [False, True]
                else:
                    values = sorted(numbers)
                    if "default" in row:
                        values = [row["default"], *values]
            unique = {json.dumps(value, sort_keys=True): value for value in values}
            if not unique:
                raise UnsupportedWorld("no finite values for " + name + "." + row["name"])
            choices.append([unique[key] for key in sorted(unique)])
        for values in itertools.product(*choices):
            if len(candidates) == alphabet_cap:
                truncated = True
                break
            candidates.append({"name": name, "args": list(values)})
        if truncated:
            break
    if only is None and "ui" in session.objects:
        names = spec["ui_methods"]
        options = plain(session.query("ui", names["options"]))
        fields = spec["ui_facts"]["inputs"]
        identifiers_by_arg = {item["parameters"][0]["name"]: identifiers[kind] for kind, item in spec["entities"].items()}
        choices = [identifiers_by_arg.get(name, [""]) for name in fields]
        for option, values in itertools.product(options, itertools.product(*choices)):
            if len(candidates) == alphabet_cap:
                truncated = True
                break
            candidates.append({"receiver": "ui", "name": names["choose"], "args": [option], "kwargs": dict(zip(fields, values))})
    return candidates, truncated


def _terms(session):
    identifiers = _identifiers(session)
    terms = []
    for name in sorted(session.spec["status_values"]):
        row = session.spec["parameters"][name][0]
        for identifier in identifiers.get(row.get("entity"), []):
            value = plain(session.query("system", name, [identifier]))
            terms.append({"kind": "query", "receiver": "system", "query": name, "args": [identifier], "value": value})
    if "ui" in session.objects and ("screen" in vars(session.objects["ui"]) or any("screen" in cls.__dict__ for cls in type(session.objects["ui"]).__mro__)):
        value = plain(session.query("ui", "screen", property=True))
        terms.append({"kind": "query", "receiver": "ui", "query": "screen", "property": True, "value": value})
    return terms


def _compact(row):
    return {key: value for key, value in row.items() if key not in {"before", "after"}}


def _extent(strategy, *, depth=None, node_cap=None, alphabet_cap=None):
    return {"strategy": strategy, "depth": depth, "node_cap": node_cap, "alphabet_cap": alphabet_cap,
            "visited": 0, "attempted": 0, "complete": False, "capped": False, "partial": False,
            "domain_truncated": False, "reason": "not started"}


def explore(session, *, seed=0, steps=64, node_cap=1000, alphabet_cap=1000, domains=None, goal=None):
    if min(steps, node_cap, alphabet_cap) < 1:
        raise UnsupportedWorld("exploration budgets must be positive")
    rng = random.Random(seed)
    extent = _extent("coverage-guided", node_cap=node_cap, alphabet_cap=alphabet_cap)
    extent.update(seed=seed, successful_step_budget=steps, successful=0)
    witnesses, features, visits, events = {}, set(), {}, []
    corpus = [[]]
    states = set()
    while extent["successful"] < steps and extent["attempted"] < node_cap:
        if extent["attempted"] and extent["attempted"] % 16 == 0:
            session.reset(rng.choice(corpus))
        for term in _terms(session):
            key = json.dumps(term, sort_keys=True)
            if key not in witnesses:
                witnesses[key] = {"semantic": term, "prefix": list(session.prefix), "outcomes": list(session.outcomes), "start": session.start}
        if goal is not None and evaluate(session, goal):
            witnesses.setdefault(json.dumps(goal, sort_keys=True), {"semantic": goal, "prefix": list(session.prefix), "outcomes": list(session.outcomes), "start": session.start})
        choices, truncated = _alphabet(session, domains=domains, alphabet_cap=alphabet_cap)
        extent["domain_truncated"] |= truncated
        if not choices:
            extent["partial"] = True
            extent["reason"] = "no generated public actions"
            break
        least = min(visits.get(item["name"], 0) for item in choices)
        choices = [item for item in choices if visits.get(item["name"], 0) == least]
        recipe = rng.choice(choices)
        row = session.step(recipe)
        visits[recipe["name"]] = visits.get(recipe["name"], 0) + 1
        extent["attempted"] += 1
        extent["successful"] += row["outcome"] == "success"
        states.add(row["after_key"])
        feature = (recipe.get("receiver", "system"), recipe["name"], row["outcome"])
        if feature not in features:
            features.add(feature)
            corpus.append(list(session.prefix))
        term = {"kind": "action", "receiver": recipe.get("receiver", "system"), "name": recipe["name"], "outcome": row["outcome"]}
        witnesses.setdefault(json.dumps(term, sort_keys=True), {"semantic": term, "prefix": list(session.prefix), "outcomes": list(session.outcomes), "start": session.start})
        events.append(_compact(row))
    for term in _terms(session):
        key = json.dumps(term, sort_keys=True)
        witnesses.setdefault(key, {"semantic": term, "prefix": list(session.prefix), "outcomes": list(session.outcomes), "start": session.start})
    if goal is not None and evaluate(session, goal):
        witnesses.setdefault(json.dumps(goal, sort_keys=True), {"semantic": goal, "prefix": list(session.prefix), "outcomes": list(session.outcomes), "start": session.start})
    extent["visited"] = len(states)
    extent["capped"] = extent["attempted"] >= node_cap and extent["successful"] < steps
    if extent["reason"] == "not started":
        extent["reason"] = "attempt/node cap" if extent["capped"] else "successful-step envelope finished (sampled)"
    # A sampled walk never licenses a negative proof, even after its envelope finishes.
    return {"extent": extent, "events": events, "witnesses": [witnesses[key] for key in sorted(witnesses)],
            "features": [list(item) for item in sorted(features)]}


def focused_search(session, *, goal, prefix=(), depth=3, node_cap=1000, alphabet_cap=1000, actions=None, domains=None):
    if depth < 0 or min(node_cap, alphabet_cap) < 1:
        raise UnsupportedWorld("search bounds must be finite and nonnegative")
    extent = _extent("complete-bfs", depth=depth, node_cap=node_cap, alphabet_cap=alphabet_cap)
    session.reset(prefix)
    initial = state_key(session.current)
    pending = deque([(list(prefix), 0)])
    seen = {initial}
    while pending:
        current, distance = pending.popleft()
        session.reset(current)
        if evaluate(session, goal):
            extent.update(visited=len(seen), reason="goal reached")
            return {"found": True, "prefix": current, "goal": goal, "extent": extent}
        if distance == depth:
            continue
        choices, truncated = _alphabet(session, actions, domains, alphabet_cap)
        extent["domain_truncated"] |= truncated
        for recipe in choices:
            session.reset(current)
            row = session.step(recipe)
            extent["attempted"] += 1
            if evaluate(session, goal):
                extent.update(visited=len(seen), reason="goal reached")
                return {"found": True, "prefix": [*current, recipe], "goal": goal, "extent": extent}
            key = row["after_key"]
            if key not in seen:
                if len(seen) >= node_cap:
                    extent.update(visited=len(seen), capped=True, reason="node cap")
                    return {"found": False, "goal": goal, "extent": extent}
                seen.add(key)
                pending.append(([*current, recipe], distance + 1))
    extent.update(visited=len(seen), complete=not extent["domain_truncated"],
                  reason="argument alphabet capped" if extent["domain_truncated"] else "bounded queue exhausted")
    return {"found": False, "goal": goal, "extent": extent}


def directed_search(session, *, goal, known=(), secondary_seed=1, secondary_steps=16, **bounds):
    for witness in known:
        session.reset(witness["prefix"])
        if evaluate(session, goal):
            return {"found": True, "prefix": witness["prefix"], "goal": goal, "origin": "known-public-witness",
                    "extent": {"complete": False, "reason": "known witness replayed"}}
    session.reset()
    facts = explore(session, seed=secondary_seed, steps=secondary_steps, node_cap=bounds.get("node_cap", 1000),
                    alphabet_cap=bounds.get("alphabet_cap", 1000), domains=bounds.get("domains"), goal=goal)
    for witness in facts["witnesses"]:
        if witness["semantic"] == goal:
            session.reset(witness["prefix"])
            if evaluate(session, goal):
                return {"found": True, "prefix": witness["prefix"], "goal": goal, "origin": "second-fixed-seed", "extent": facts["extent"]}
    return focused_search(session, goal=goal, **bounds)

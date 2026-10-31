"""Concrete finite walks and bounded search over the shared native session."""

from __future__ import annotations

from collections import deque
import heapq
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
    if goal.get("kind") in {"option", "screen"}:
        for receiver in (name for name in session.objects if name != "system"):
            value = plain(session.query(receiver, session.spec["ui_methods"]["options"])) if goal["kind"] == "option" else plain(session.query(receiver, "screen", property=True))
            if goal["value"] in value if goal["kind"] == "option" else value == goal["value"]:
                return True
        return False
    if goal.get("kind", "query") == "action":
        row = session.last
        return bool(row and row["call"].get("name") == goal["name"] and row["call"].get("receiver", "system") == goal.get("receiver", "system") and row["outcome"] == goal["outcome"])
    receiver = goal.get("receiver", "system")
    if goal.get("entity") and not goal.get("args"):
        return any(evaluate(session, {key: value for key, value in {**goal, "args": [identifier]}.items() if key != "entity"})
                   for identifier in _identifiers(session)[goal["entity"]])
    value = plain(session.query(receiver, goal["query"], goal.get("args", []), goal.get("kwargs", {}), property=goal.get("property", False)))
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


def _ensure_ui(session):
    if not session.spec.get("ui") or any(name != "system" for name in session.objects):
        return
    facts = session.spec.get("ui_constructor", {})
    if not facts.get("system_parameter"):
        raise UnsupportedWorld("the UI constructor needs a source-bound system parameter")
    if facts["parameters"][0]["name"] != facts["system_parameter"]:
        raise UnsupportedWorld("the UI system argument must be the source-bound first parameter")
    identifiers = _identifiers(session)
    parameters = [row for row in facts["parameters"] if row["name"] != facts["system_parameter"]]
    values = []
    for row in parameters:
        choices = identifiers[row["entity"]] if row.get("entity") else [False, True] if type(row.get("default")) is bool else [row.get("default")]
        if "default" in row:
            choices = list(dict.fromkeys([row["default"], *choices]))
        if row["required"] and not choices:
            raise UnsupportedWorld("the UI constructor has no finite input for " + row["name"])
        values.append(choices)
    for index, chosen in enumerate(itertools.product(*values)):
        recipe = {"construct": "ui", "receiver": "ui:auto:" + str(index), "kwargs": dict(zip((row["name"] for row in parameters), chosen))}
        before = state_key(session.current)
        try:
            session.step(recipe)
        except UnsupportedWorld:
            raise
        except (ValueError, *session.refusals):
            from .project import snapshot
            session.current = snapshot(session.objects, session.arena, session.defaults)
            if state_key(session.current) != before:
                raise UnsupportedWorld("a rejected UI construction changed its system")
    if not any(name != "system" for name in session.objects):
        raise UnsupportedWorld("no generated public UI constructor profile is buildable")


def observations(session, *, all_queries=False):
    """Small public observations, never a substitute for the complete native state key."""
    values, unknown = [], []
    identifiers = _identifiers(session)
    requested = set(session.spec["status_values"]) | {row["query"] for goal in session.spec.get("goal_guards", []) for row in goal["comparisons"]}
    for query, facts in session.spec.get("entity_queries", {}).items():
        if not all_queries and query not in requested:
            continue
        for identifier in identifiers[facts["entity"]]:
            row = session.query("system", query, [identifier])
            try:
                value = plain(row)
            except UnsupportedWorld:
                unknown.append(query)
                continue
            values.append({"query": query, "entity": facts["entity"], "args": [identifier], "value": value})
    return {"values": values, "unknown": sorted(set(unknown))}


def related_slice(session, query, identifier):
    identifiers = _identifiers(session)
    parameter = session.spec["parameters"][query][0]
    related = {kind: set() for kind in identifiers}
    related[parameter["entity"]].add(identifier)
    def add(value):
        if isinstance(value, dict):
            for item in value.values(): add(item)
        elif isinstance(value, (list, tuple)):
            for item in value: add(item)
        elif type(value) in {str, int}:
            for kind, known in identifiers.items():
                if value in known: related[kind].add(value)
    observed = observations(session, all_queries=True)
    for row in observed["values"]:
        if row["entity"] == parameter["entity"] and row["args"] == [identifier]:
            add(row["value"])
    return {kind: sorted(values, key=str) for kind, values in related.items()}, observed["unknown"]


def _alphabet(session, only=None, domains=None, alphabet_cap=1000):
    spec = session.spec
    identifiers = _identifiers(session)
    numbers = {0, 1, 2}
    for row in observations(session, all_queries=True)["values"]:
        numbers |= _numbers(row["value"])
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
                    values.extend(value for value in literals if type(value) is int)
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
    if only is None and any(name != "system" for name in session.objects):
        names = spec["ui_methods"]
        identifiers_by_arg = {item["parameters"][0]["name"]: identifiers[kind] for kind, item in spec["entities"].items()}
        for receiver in (name for name in session.objects if name != "system"):
            options = plain(session.query(receiver, names["options"]))
            for option in options:
                fields = spec["ui_facts"].get("option_inputs", {}).get(option)
                if fields is None:
                    truncated = True
                    continue
                choices = [identifiers_by_arg.get(name, [""]) for name in fields]
                for values in itertools.product(*choices):
                    if len(candidates) >= alphabet_cap:
                        return candidates, True
                    candidates.append({"receiver": receiver, "name": names["choose"], "args": [option], "kwargs": dict(zip(fields, values))})
    return candidates, truncated


def _terms(session):
    identifiers = _identifiers(session)
    terms = []
    for name in sorted(session.spec["status_values"]):
        row = session.spec["parameters"][name][0]
        for identifier in identifiers.get(row.get("entity"), []):
            value = plain(session.query("system", name, [identifier]))
            terms.append({"kind": "query", "receiver": "system", "query": name, "args": [identifier], "value": value})
    for receiver in (name for name in session.objects if name != "system"):
        if "screen" in vars(session.objects[receiver]) or any("screen" in cls.__dict__ for cls in type(session.objects[receiver]).__mro__):
            value = plain(session.query(receiver, "screen", property=True))
            terms.append({"kind": "screen", "value": value, "ui_class": session.spec["ui"]})
        for option in plain(session.query(receiver, session.spec["ui_methods"]["options"])):
            terms.append({"kind": "option", "value": option, "ui_class": session.spec["ui"]})
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
    witnesses, features, visits, events, concrete = {}, set(), {}, [], []
    corpus = [list(session.prefix)]
    states = set()
    while extent["successful"] < steps and extent["attempted"] < node_cap:
        if extent["attempted"] and extent["attempted"] % 16 == 0:
            session.reset(rng.choice(corpus))
        _ensure_ui(session)
        concrete.append({"prefix": list(session.prefix), "outcomes": list(session.outcomes), "start": dict(session.start), "observations": observations(session)})
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
            "features": [list(item) for item in sorted(features)], "states": concrete}


def focused_search(session, *, goal, prefix=(), depth=3, node_cap=1000, alphabet_cap=1000, actions=None, domains=None, related=None, priority=False, rank_states=()):
    if depth < 0 or min(node_cap, alphabet_cap) < 1:
        raise UnsupportedWorld("search bounds must be finite and nonnegative")
    extent = _extent("complete-bfs", depth=depth, node_cap=node_cap, alphabet_cap=alphabet_cap)
    if priority:
        extent["strategy"] = "guard-priority-complete"
    extent["numeric_domain"] = "small integers, parameter literals/defaults and integers returned by public one-entity queries"
    session.reset(prefix)
    initial = state_key(session.current)
    order = itertools.count()
    pending = [(0, 0, next(order), session.checkpoint())] if priority else deque([(session.checkpoint(), 0)])
    seen = {initial: 0}
    answers = []
    hints = _rank_hints(session, rank_states) if priority else {}
    while pending:
        if priority:
            _, distance, _, checkpoint = heapq.heappop(pending)
        else:
            checkpoint, distance = pending.popleft()
        session.restore_checkpoint(checkpoint)
        if distance > seen[state_key(session.current)]:
            continue
        current = list(session.prefix)
        if goal.get("kind") in {"option", "screen"}:
            _ensure_ui(session)
            current = list(session.prefix)
        if evaluate(session, goal):
            extent.update(visited=len(seen), reason="goal reached")
            return {"found": True, "prefix": current, "goal": goal, "extent": extent}
        if distance == depth:
            continue
        choices, truncated = _alphabet(session, actions, domains, alphabet_cap)
        extent["domain_truncated"] |= truncated
        if related:
            selected, unknown = related_slice(session, related["query"], related["identifier"])
            extent["domain_truncated"] |= bool(unknown)
            def applicable(recipe):
                parameters = session.spec["parameters"][recipe["name"]]
                return not any(row.get("entity") for row in parameters) or any(row.get("entity") and value in selected[row["entity"]] for row, value in zip(parameters, recipe.get("args", [])))
            choices = [row for row in choices if row.get("receiver", "system") == "system" and applicable(row)]
        if distance == 0:
            extent["initial_alphabet"] = len(choices)
        checkpoint = session.checkpoint()
        for recipe in choices:
            session.restore_checkpoint(checkpoint)
            row = session.step(recipe)
            if distance == 0:
                answers.append({"call": recipe, "outcome": row["outcome"], "exception": row["exception"]})
            extent["attempted"] += 1
            if evaluate(session, goal):
                extent.update(visited=len(seen), reason="goal reached")
                return {"found": True, "prefix": [*current, recipe], "goal": goal, "extent": extent}
            key = row["after_key"]
            if key not in seen or distance + 1 < seen[key]:
                if key not in seen and len(seen) >= node_cap:
                    extent.update(visited=len(seen), capped=True, reason="node cap")
                    return {"found": False, "goal": goal, "extent": extent, "answers": answers}
                seen[key] = distance + 1
                saved = session.checkpoint()
                if priority:
                    rank = _guard_distance(session, goal, observations(session), hints)
                    writers = {name for item in session.spec.get("goal_guards", []) if all(goal.get(k) == value for k, value in item["goal"].items()) for name in item["actions"]}
                    if goal.get("kind") in {"option", "screen"}:
                        writers.add(session.spec["ui_methods"]["choose"])
                    rank -= depth if recipe.get("name") in writers else 0
                    heapq.heappush(pending, (rank, distance + 1, next(order), saved))
                else:
                    pending.append((saved, distance + 1))
    extent.update(visited=len(seen), complete=not extent["domain_truncated"],
                  reason="argument alphabet capped" if extent["domain_truncated"] else "bounded queue exhausted")
    return {"found": False, "goal": goal, "extent": extent, "answers": answers}


def _rank_hints(session, states):
    by_prefix = {json.dumps([state.get("start", session.start), state["prefix"]], sort_keys=True): state for state in states}
    increases, before_actions, edges = {}, {}, {}
    for state in states:
        before = by_prefix.get(json.dumps([state.get("start", session.start), state["prefix"][:-1]], sort_keys=True))
        if before is None or not state["prefix"]:
            continue
        categorical = [(row["entity"], row["query"], row["value"]) for row in before["observations"]["values"] if row["query"] in session.spec["status_values"]]
        name = state["prefix"][-1].get("name")
        before_actions.setdefault(name, set()).update(categorical)
        changed = {(row["query"], tuple(row["args"])): row for row in state["observations"]["values"]}
        for row in before["observations"]["values"]:
            after = changed.get((row["query"], tuple(row["args"])))
            if after is None:
                continue
            if type(row["value"]) is int and type(after["value"]) is int and after["value"] > row["value"]:
                increases.setdefault(row["query"], set()).update(item for item in categorical if item[0] == row["entity"])
            if row["query"] in session.spec["status_values"] and row["value"] != after["value"]:
                edges.setdefault((row["entity"], row["query"], row["value"]), set()).add(after["value"])
    return {"increases": increases, "before_actions": before_actions, "edges": edges}


def _guard_distance(session, goal, observed, hints=None):
    hints = hints or {"increases": {}, "before_actions": {}, "edges": {}}
    selected = [item for item in session.spec.get("goal_guards", []) if all(goal.get(key) == value for key, value in item["goal"].items())]
    comparisons = [row for item in session.spec.get("goal_guards", [])
                   if all(goal.get(key) == value for key, value in item["goal"].items())
                   for row in (item.get("preferred_comparisons", []) if item.get("preferred_sources") else item["comparisons"])]
    score = 0
    for row in comparisons:
        threshold = row["threshold"].get("value", session.defaults.get(row["threshold"].get("setting")))
        values = [value["value"] for value in observed["values"] if value["query"] == row["query"] and type(value["value"]) is int]
        if values and type(threshold) is int:
            target = threshold + (row["operator"] == ">") - (row["operator"] == "<")
            distance = min(abs(value - target) for value in values)
            score += distance * 16
            desired = hints["increases"].get(row["query"], set()) if distance else set().union(*(hints["before_actions"].get(name, set()) for item in selected for name in item["actions"]))
            if desired:
                closest = {value["args"][0] for value in observed["values"] if value["query"] == row["query"] and type(value["value"]) is int and abs(value["value"] - target) == distance}
                distances = []
                for value in observed["values"]:
                    if value["query"] not in session.spec["status_values"] or value["args"][0] not in closest:
                        continue
                    targets = {item[2] for item in desired if item[:2] == (value["entity"], value["query"])}
                    pending, seen = deque([(value["value"], 0)]), set()
                    while pending:
                        current, steps = pending.popleft()
                        if current in targets:
                            distances.append(steps)
                            break
                        if current not in seen:
                            seen.add(current)
                            pending.extend((next_value, steps + 1) for next_value in hints["edges"].get((value["entity"], value["query"], current), set()))
                    else:
                        distances.append(2)
                score += min(distances, default=0)
    sources = [row for item in selected for row in (item.get("preferred_sources") or [row for row in item["sources"] if goal.get("kind") == "action" and row["function"].endswith("." + goal["name"])])]
    desired = {value for values in session.spec["status_values"].values() for value in values if any(repr(value) in row["expression"] for row in sources)}
    if desired:
        score += 32 if not any(row["query"] in session.spec["status_values"] and row["value"] in desired for row in observed["values"]) else 0
    return score


def directed_search(session, *, goal, known=(), states=(), origin=None, secondary_seed=1, secondary_steps=16, **bounds):
    original_start = session.start
    for witness in known:
        start = witness.get("start", original_start)
        if witness.get("semantic", {}).get("origin") != origin or start.get("files", {}) != original_start.get("files", {}):
            continue
        shipped = session.spec["shipped"]
        if {**shipped, **start.get("settings", {})} != {**shipped, **original_start.get("settings", {})}:
            continue
        if session.base_prefix:
            if witness["prefix"][:len(session.base_prefix)] != session.base_prefix:
                continue
        elif any(row.get("replace") and row.get("name") == (session.spec.get("persistence") or {}).get("load") for row in witness["prefix"]):
            continue
        session.reset(start=start)
        for index, recipe in enumerate(witness["prefix"]):
            row = session.step(recipe)
            if witness.get("outcomes") and row["outcome"] != witness["outcomes"][index]:
                break
        else:
            if evaluate(session, goal):
                result = {"found": True, "prefix": list(session.prefix), "start": session.start, "goal": goal, "origin": "known-public-witness",
                          "extent": {"complete": False, "reason": "known witness replayed"}}
                session.start = original_start
                return result
    session.start = original_start
    session.reset()
    facts = explore(session, seed=secondary_seed, steps=secondary_steps, node_cap=bounds.get("node_cap", 1000),
                    alphabet_cap=bounds.get("alphabet_cap", 1000), domains=bounds.get("domains"), goal=goal)
    for witness in facts["witnesses"]:
        session.reset(witness["prefix"])
        if evaluate(session, goal):
            return {"found": True, "prefix": witness["prefix"], "start": original_start, "goal": goal, "origin": "second-fixed-seed", "extent": facts["extent"]}
    concrete = [*states, *facts["states"]]
    hints = _rank_hints(session, concrete)
    nearest = min(concrete, key=lambda row: (_guard_distance(session, goal, row["observations"], hints), len(row["prefix"]), json.dumps(row["prefix"], sort_keys=True))) if concrete else {"prefix": []}
    session.start = nearest.get("start", original_start)
    result = focused_search(session, goal=goal, prefix=nearest["prefix"], priority=True, rank_states=concrete, **bounds)
    result.update(start=session.start, search_prefix=nearest["prefix"], origin="nearest-guard-complete-search",
                  guard_sources=[item["sources"] for item in session.spec.get("goal_guards", []) if all(goal.get(key) == value for key, value in item["goal"].items())])
    session.start = original_start
    return result

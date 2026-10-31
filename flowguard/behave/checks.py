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


def setting_effects(session, traces, *, setting=None, alphabet_cap=1000):
    """Compare a finite union of real public traces, using the actual saved representation."""
    import base64
    from dataclasses import fields, is_dataclass
    from pathlib import Path
    import stat

    from .explore import _alphabet
    from .project import state_key

    original, base_prefix = dict(session.start), list(session.base_prefix)
    shipped = dict(session.defaults)
    requested = {name: value for name, value in shipped.items() if setting is None or name == setting}
    candidates, information, unknown, profiles = [], [], [], []
    initial_key, initial_checkpoint = None, None
    saved_binding, saved_facts = None, {}
    mirror = session.spec.get("serializer_settings_mirror")
    persistence = session.spec.get("persistence")
    unique = {state_key([row.get("start", {}), row["prefix"]]): row for row in traces if row.get("eligible", True)}
    traces = list(unique.values())
    if not mirror or not persistence:
        reason = "no uniquely source-bound JSON settings mirror in the public serializer"
        return {"candidates": [], "information": [], "profiles": [], "unknown": [
            {"check": "GC5", "setting": name, "reason": reason} for name in requested], "traces": len(traces)}

    def profile():
        value = getattr(session.objects["system"], mirror["attribute"], None)
        locator = type(value).__module__ + ":" + type(value).__qualname__
        if locator != session.spec["settings"] or not is_dataclass(value):
            raise UnsupportedWorld("the actual settings instance is not bound to the serializer")
        return json.loads(json.dumps({field.name: getattr(value, field.name) for field in fields(value)}))

    def without_mirror(data, actual):
        result = json.loads(json.dumps(data))
        parent = result
        try:
            for key in mirror["path"][:-1]:
                parent = parent[key]
            key = mirror["path"][-1]
            if state_key(parent[key]) != state_key(actual):
                raise UnsupportedWorld("saved settings subtree does not match the actual settings instance")
            del parent[key]
        except (KeyError, IndexError, TypeError) as exc:
            raise UnsupportedWorld("the source-bound settings mirror is absent from the saved JSON") from exc
        return json.dumps(result, separators=(",", ":"), ensure_ascii=False)

    def saved_domain(actual):
        nonlocal saved_binding
        binding = type(session.objects["system"])
        if binding is not saved_binding:
            saved_facts.clear()
            saved_binding = binding
        reusable = session.observed.inputs is not None and session.observed.inputs.reusable
        key = state_key(session.current)
        if reusable and key in saved_facts:
            return list(saved_facts[key])
        before, prefix, start = session.current, list(session.prefix), dict(session.start)
        try:
            checkpoint = session.checkpoint()
        except UnsupportedWorld:
            checkpoint = None
        try:
            name = "temp/_flowguard_settings.json"
            row = session.step({"name": persistence["save"], "args": [{"$file": name}]})
            if row["outcome"] != "success":
                raise UnsupportedWorld("public save did not succeed during the setting comparison")
            path = session.arena / name
            try:
                data = json.loads(path.read_bytes())
            except (OSError, ValueError, UnicodeError) as exc:
                raise UnsupportedWorld("GC5 settings mirror comparison currently requires JSON save bytes") from exc
            result = (without_mirror(data, actual), stat.S_IMODE(path.stat().st_mode))
            if reusable and session.observed.inputs.reusable:
                saved_facts[key] = result
            return list(result)
        finally:
            if checkpoint is not None:
                session.restore_checkpoint(checkpoint)
            else:
                session.reset(prefix, start=start)
                if session.current != before:
                    raise UnsupportedWorld("public prefix did not restore the setting comparison state")

    def run(trace, change, baseline=None):
        nonlocal initial_key, initial_checkpoint
        start = dict(trace.get("start", {}))
        if start.get("settings"):
            raise UnsupportedWorld("TS5 requires a shipped replay rather than the test's own settings")
        wanted = {**shipped, **change}
        session.base_prefix = []
        beginning = {**start, **({"settings": change} if change else {})}
        key = state_key(beginning)
        same_binding = initial_checkpoint is not None and type(session.objects["system"]) is type(initial_checkpoint["bundle"][0]["system"])
        if initial_key == key and same_binding and session.observed.inputs.reusable:
            session.start = beginning
            session.restore_checkpoint(initial_checkpoint)
        else:
            session.reset(start=beginning)
            initial_key = key
            try:
                initial_checkpoint = session.checkpoint()
            except UnsupportedWorld:
                initial_checkpoint = None
        if state_key(profile()) != state_key(wanted):
            raise UnsupportedWorld("construction did not apply the requested settings profile")
        effects, answers, saved_paths = [], {}, set()

        def files(actual):
            result = []
            for row in session.current["files"]:
                if row[1] == "file" and row[0] in saved_paths:
                    try:
                        value = without_mirror(json.loads(base64.b64decode(row[3])), actual)
                    except (ValueError, UnicodeError) as exc:
                        raise UnsupportedWorld("a trace save is not supported JSON") from exc
                    result.append([*row[:3], value])
                else:
                    result.append(row)
            return result

        effects.append(["initial", saved_domain(wanted), files(wanted)])
        if baseline is not None and effects[0] != baseline["effects"][0]:
            return {"effects": effects, "answers": answers, "effect_prefix": 0}
        for index, recipe in enumerate(trace["prefix"]):
            row = session.step(recipe)
            if state_key(profile()) != state_key(wanted):
                raise UnsupportedWorld("the public prefix or load overwrote the requested configuration")
            expected = trace.get("outcomes")
            if not change and expected is not None and (index >= len(expected) or row["outcome"] != expected[index]):
                raise UnsupportedWorld("the shipped TS5 public prefix no longer reproduces its outcome")
            if row["outcome"] == "crash":
                raise UnsupportedWorld("a TS5 public call crashed; its setting effect is not judged")
            receiver = recipe.get("receiver", "system")
            query_call = receiver == "system" and recipe.get("name") in session.spec["queries"]
            query_call |= receiver != "system" and not recipe.get("construct") and recipe.get("name") != session.spec["ui_methods"]["choose"]
            if query_call:
                if row["before_key"] != row["after_key"]:
                    raise UnsupportedWorld("a TS5 query changed the complete observation")
                answers[str(index) + ":" + recipe["name"]] = [row["value"], row["stdout"], row["stderr"], row["exception"]]
            else:
                if receiver == "system" and recipe.get("name") == persistence["save"] and row["outcome"] == "success":
                    value = recipe.get("args", [None])[0] if recipe.get("args") else recipe.get("kwargs", {}).get("path")
                    if isinstance(value, dict) and set(value) == {"$file"}:
                        value = value["$file"]
                    if not isinstance(value, str) or Path(value).is_absolute() or ".." in Path(value).parts:
                        raise UnsupportedWorld("a trace save path is not a relative file recipe")
                    saved_paths.add(Path(value).as_posix())
                effects.append([row["outcome"], saved_domain(wanted), files(wanted)])
                if baseline is not None and effects[-1] != baseline["effects"][len(effects) - 1]:
                    return {"effects": effects, "answers": answers, "effect_prefix": index + 1}
        return {"effects": effects, "answers": answers}

    def extra_answers(trace, change, preferred, recipes=None, partner=None):
        run(trace, change)  # The same concrete public prefix, with its actual configuration.
        complete = True
        if recipes is None:
            recipes, truncated = _alphabet(session, only=session.spec["queries"], alphabet_cap=alphabet_cap, include_optional=True)
            complete = not truncated
            recipes.sort(key=lambda row: (row["name"] not in preferred, json.dumps(row, sort_keys=True)))
            for receiver in (key for key in session.objects if key != "system"):
                recipes.append({"receiver": receiver, "name": session.spec["ui_methods"]["options"]})
        answers = {}
        for recipe in recipes:
            before, prefix, start = session.current, list(session.prefix), dict(session.start)
            try:
                row = session.step(recipe, keep=False)
                if row["before_key"] != row["after_key"] or row["outcome"] not in {"success", "refusal"}:
                    raise UnsupportedWorld("an extra query was not a pure supported answer")
                key = json.dumps(recipe, sort_keys=True)
                answers[key] = [row["outcome"], row["value"], row["stdout"], row["stderr"], row["exception"]]
                if partner is not None and key in partner and state_key(answers[key]) != state_key(partner[key]):
                    complete = False  # The existential witness is complete; the remaining probes are unnecessary.
                    break
            except UnsupportedWorld:
                complete = False
                session.reset(prefix, start=start)
                if session.current != before:
                    raise UnsupportedWorld("an extra query could not restore its complete before-state")
        return recipes, answers, complete

    def differences(left, right):
        # Lazy observations are evidence only when both sides actually executed the same recipe.
        return {key.split(":", 1)[-1] if not key.startswith("{") else json.loads(key)["name"]
                for key in left.keys() & right.keys() if state_key(left[key]) != state_key(right[key])}

    try:
        baselines = []
        for trace in traces:
            try:
                baselines.append(run(trace, {}))
            except (UnsupportedWorld, ValueError, TypeError) as exc:
                baselines.append(None)
                unknown.append({"check": "GC5", "reason": str(exc), "origin": trace.get("origin", "public-prefix")})
        for name, default in requested.items():
            if type(default) not in {bool, int}:
                unknown.append({"check": "GC5", "setting": name, "reason": "only boolean and integer setting variations are currently supported"})
                continue
            changes = [value for field, value in variations({"shipped": shipped}) if field == name]
            changed_queries, compared, judged, effect, incomplete = set(), 0, 0, False, any(row is None for row in baselines) or not traces
            probe_incomplete = False
            preferred = session.spec.get("setting_query_reads", {}).get(name, [])
            ordered = sorted(zip(traces, baselines), key=lambda pair: (
                not any(row.get("name") in preferred for row in pair[0]["prefix"]), len(pair[0]["prefix"])))
            for profile_index, value in enumerate(changes):
                entry = {"setting": name, "value": value, "replays": 0, "state": "not-judged"}
                profiles.append(entry)
                try:
                    session.base_prefix = []
                    session.reset(start={"settings": {name: value}})
                except (UnsupportedWorld, ValueError, TypeError) as exc:
                    entry["state"] = "not-buildable"
                    unknown.append({"check": "GC5", "setting": name, "profile": value, "reason": "profile not buildable: " + str(exc)})
                    continue
                for trace, baseline in ordered:
                    if baseline is None:
                        continue
                    try:
                        changed = run(trace, {name: value}, baseline)
                    except (UnsupportedWorld, ValueError, TypeError) as exc:
                        unknown.append({"check": "GC5", "setting": name, "profile": value, "reason": str(exc)})
                        incomplete = True
                        continue
                    entry["replays"] += 1
                    compared += 1
                    effect |= baseline["effects"] != changed["effects"]
                    if "effect_prefix" in changed:
                        entry["effect_prefix"] = changed["effect_prefix"]
                    changed_queries.update(differences(baseline["answers"], changed["answers"]))
                    if not effect and not changed_queries:
                        try:
                            recipes, varied_answers, varied_complete = extra_answers(trace, {name: value}, preferred)
                            _, base_answers, base_complete = extra_answers(trace, {}, preferred, recipes, varied_answers)
                            changed_queries.update(differences(base_answers, varied_answers))
                            probe_incomplete |= not varied_complete or not base_complete
                        except UnsupportedWorld:
                            probe_incomplete = True
                    entry["state"] = "effect-observed" if effect else "compared"
                    if effect:
                        break
                judged += entry["replays"] > 0
                if effect:
                    profiles.extend({"setting": name, "value": skipped, "replays": 0, "state": "not-run-effect-observed"}
                                    for skipped in changes[profile_index + 1:])
                    break
            summary = {"setting": name, "replays": compared, "profiles": judged, "query_changes": sorted(changed_queries), "action_effect": effect}
            if effect:
                information.append({**summary, "label": "EFFECT OBSERVED"})
            elif incomplete or not compared:
                unknown.append({"check": "GC5", "setting": name, "reason": "the finite TS5 setting comparison is incomplete"})
            elif changed_queries:
                candidates.append({"semantic": {"check": "GC5", "kind": "setting", "setting": name},
                                   "label": "ADVICE ONLY", "prefix": [], "start": {}, "effects": summary,
                                   "settings_traces": traces, "alphabet_cap": alphabet_cap})
            elif probe_incomplete:
                unknown.append({"check": "GC5", "setting": name, "reason": "extra query observations were incomplete; no paired answer-change witness was found"})
            else:
                information.append({**summary, "label": "NO OBSERVED EFFECT"})
    finally:
        session.base_prefix = base_prefix
        session.reset(start=original)
    return {"candidates": candidates, "information": information, "unknown": unknown, "profiles": profiles, "traces": len(traces)}


def _output_multiset(row):
    """Only captured append-output increments lose order, never the state graph."""
    result = {}
    for stream in ("stdout", "stderr"):
        counts = {}
        for value in row.get(stream, "").splitlines():
            counts[value] = counts.get(value, 0) + 1
        result[stream] = [{"value": value, "count": count} for value, count in sorted(counts.items())]
    return result


def crashes(session, facts=None, *, states=(), case=None, generate=True):
    """Judge actual public calls and small source-bound files in this native world."""
    import base64
    import csv
    import hashlib
    import io
    from .project import state_key

    original, original_prefix = dict(session.start), list(session.prefix)
    candidates, unknown, inputs, seen = [], [], [], set()
    compared = 0

    def observe(row, prefix, outcomes, start, file_input=None):
        nonlocal compared
        compared += 1
        kind = "crash" if row["outcome"] == "crash" else "refused_changed_state" if row["outcome"] == "refusal" and row["before_key"] != row["after_key"] else None
        if kind is None:
            return
        exception = row.get("exception") or {}
        source = exception.get("source") or {}
        call = row["call"]
        semantic = {"check": "GC6", "kind": kind, "receiver": call.get("receiver", "system"),
                    "action": call["name"], "args": call.get("args", []), "kwargs": call.get("kwargs", {}),
                    "exception": exception.get("type"), "source": {key: source[key] for key in ("path", "function") if key in source}}
        if semantic["receiver"].startswith("ui:"):
            from .project import ui_identity
            semantic.update(ui_identity(session.spec, prefix, semantic["receiver"]))
        if file_input:
            semantic["file_kind"] = file_input["kind"]
        violation = {key: row[key] for key in ("call", "outcome", "exception", "before_key", "after_key")}
        violation["outputs"] = _output_multiset(row)
        if case is not None:
            expected = {key: value for key, value in case["semantic"].items() if key != "origin"}
            if semantic != expected or violation["outputs"] != case["violation"]["outputs"]:
                return
        key = state_key([semantic, start])
        if key not in seen:
            seen.add(key)
            candidates.append({"semantic": semantic, "label": "CRASH" if kind == "crash" else "REFUSED CHANGED STATE",
                               "prefix": list(prefix), "outcomes": list(outcomes), "start": dict(start),
                               "violation": violation, **({"file_input": file_input} if file_input else {})})

    try:
        if case is not None:
            prefix, outcomes = list(session.prefix), list(session.outcomes)
            observe(session.step(case["violation"]["call"]), prefix, outcomes, session.start, case.get("file_input"))
        else:
            facts = facts or {}
            for record in facts.get("failures", []):
                observe(record["row"], record["prefix"], record["outcomes"], record["start"])
            # Prefixes are already TS2-validated; replay each actual tail, not a new alphabet.
            for state in states:
                prefix, start = state["prefix"], state.get("start", original)
                if session.start != start or prefix[:len(session.prefix)] != session.prefix:
                    session.reset(start=start)
                for recipe in prefix[len(session.prefix):]:
                    before, outcomes = list(session.prefix), list(session.outcomes)
                    observe(session.step(recipe), before, outcomes, start)
            if generate:
                unknown.extend({"check": "GC6", **row} for row in session.spec.get("file_input_unknown", []))
                for schema in session.spec.get("file_schemas", []):
                    columns = {row["name"]: row for row in schema["columns"]}
                    header = schema["required"] or list(columns)
                    values = []
                    for name in header:
                        column = columns[name]
                        domain = column.get("values", [])
                        values.append(domain[0] if domain else {"str": "generated-1", "int": 0, "float": 0.0, "bool": True}[column["converter"]])
                    for kind, cells in (("normal", values), ("extra cell", [*values, "extra"]), ("missing cell", values[:-1])):
                        buffer = io.StringIO(newline="")
                        writer = csv.writer(buffer)
                        writer.writerow(header)
                        writer.writerow(cells)
                        payload = buffer.getvalue().encode("utf-8")
                        name = f"flowguard-input-{schema['action']}-{kind.replace(' ', '-')}.csv"
                        file_input = {"kind": kind, "name": name, "parameter": schema["parameter"], "source": schema["source"],
                                      "sha256": hashlib.sha256(payload).hexdigest()}
                        start = {**original, "files": {**original.get("files", {}), name: base64.b64encode(payload).decode("ascii")}}
                        try:
                            session.reset(start=start)
                            kwargs = {row["name"]: row["default"] for row in session.spec["parameters"][schema["action"]] if "default" in row}
                            kwargs[schema["parameter"]] = {"$file": name}
                            if any(row["required"] and row["name"] not in kwargs for row in session.spec["parameters"][schema["action"]]):
                                raise UnsupportedWorld("the file action has an unbound required parameter")
                            before, outcomes = list(session.prefix), list(session.outcomes)
                            row = session.step({"name": schema["action"], "kwargs": kwargs})
                            inputs.append({**file_input, "action": schema["action"], "outcome": row["outcome"]})
                            observe(row, before, outcomes, start, file_input)
                            if kind == "normal" and row["outcome"] != "success":
                                unknown.append({"check": "GC6", "action": schema["action"], "reason": "the source-bound normal file did not succeed", "exception": row["exception"]})
                        except UnsupportedWorld as exc:
                            unknown.append({"check": "GC6", "action": schema["action"], "reason": str(exc)})
    finally:
        session.reset(original_prefix, start=original)
    return {"candidates": candidates, "unknown": unknown, "inputs": inputs, "compared": compared,
            "matched": bool(candidates), "scope": "actual fresh/test/saved calls and one normal/extra/missing file per supported source-bound CSV schema; other formats unjudged"}


def saved_files(session, saves, *, seed=0, steps=64, node_cap=1000, alphabet_cap=1000):
    """Load exact old file bytes, then reuse the same supported native checks."""
    import base64
    import hashlib

    from .explore import explore

    original, base_prefix = session.start, list(session.base_prefix)
    candidates, files, unknown = [], [], []
    missing = ["GC" + str(number) for number in (7, 8, 9)]
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
                if row["outcome"] == "refusal" and row["before_key"] != row["after_key"]:
                    loading = crashes(session, {"failures": [{"prefix": [], "outcomes": [], "start": start, "row": row}]}, generate=False)
                    origin = {"kind": "saved-file", "source": source["revision"], "file": file["sha256"], "schema": schema}
                    candidates.extend({**candidate, "semantic": {**candidate["semantic"], "origin": origin}, "saved_file": saved}
                                      for candidate in loading["candidates"])
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
                agreement = offered(session, facts)
                reached = reach(session, facts, origin=origin)
                trapped = stuck(session, facts)
                crashed = crashes(session, facts)
                for check in (reached, trapped, agreement, crashed):
                    candidates.extend({**candidate, "semantic": {**candidate["semantic"], "origin": origin},
                                       "saved_file": saved} for candidate in check["candidates"])
                    unknown.extend({**item, "origin": origin} for item in check["unknown"])
                unknown.extend({"check": "GC1", "origin": origin, **item} for item in reached["not_judged"])
                summary["extent"] = facts["extent"]
                if session.spec.get("settings"):
                    unknown.append({"check": "GC5", "origin": origin,
                                    "reason": "loaded configurations are retained; no distinct actual settings profile was compared for this saved start"})
                summary["missing_checks"] = missing
            except UnsupportedWorld as exc:
                summary.update(status="unchecked", reason=str(exc))
                unknown.append({"check": "GC4", **provenance, "reason": str(exc)})
    finally:
        session.base_prefix = base_prefix
        session.reset(start=original)
    return {"candidates": candidates, "files": files, "unknown": unknown, "missing_checks": missing}


def offered(session, facts, *, states=(), case=None):
    """Compare a public prediction and its action at one complete checkpoint."""
    from .project import state_key, ui_identity

    candidates, unknown, compared = [], [], 0
    original = session.start

    def compact_unknown():
        grouped = {}
        for row in unknown:
            comparison = row.get("comparison", {})
            summary = {key: row[key] for key in ("check", "reason", "predictor", "action", "option") if key in row}
            for key in ("predictor", "action"):
                if key in comparison:
                    summary[key] = comparison[key]["name"]
            if "option" in comparison:
                summary["option"] = comparison["option"]
            key = state_key(summary)
            grouped.setdefault(key, {**summary, "count": 0})["count"] += 1
        return list(grouped.values())

    def permission(recipe, mode, option=None, *, readings=None, field=None):
        value = plain(session.query(recipe.get("receiver", "system"), recipe["name"],
                                    recipe.get("args", []), recipe.get("kwargs", {})))
        if readings is not None:
            readings[field] = value
        if mode == "why_not" and (value is None or type(value) is str):
            return value is None
        if mode == "can" and type(value) is bool:
            return value
        if mode == "offered" and type(value) is list and all(type(item) is str for item in value):
            return option in value
        raise UnsupportedWorld("the predictor has no declared permission answer")

    def compare(comparison):
        nonlocal compared
        checkpoint = session.checkpoint()
        prefix, outcomes = list(session.prefix), list(session.outcomes)
        try:
            readings = {}
            expected = permission(comparison["predictor"], comparison["predictor_mode"], comparison.get("option"),
                                  readings=readings, field="predictor_value")
            if comparison["predictor_mode"] == "offered" and not expected:
                return
            if "expected_permission" in comparison and expected != comparison["expected_permission"]:
                return
            session.restore_checkpoint(checkpoint)
            if "other_predictor" in comparison:
                observed = permission(comparison["other_predictor"], comparison["other_mode"],
                                      readings=readings, field="other_predictor_value")
                mismatch = expected != observed
            else:
                row = session.step(comparison["action"])
                readings["answer"] = {key: row[key] for key in ("call", "outcome", "exception", "value")}
                readings["before_key"] = row["before_key"]
                observed = row["outcome"]
                if observed not in {"success", "refusal"}:
                    raise UnsupportedWorld("the compared action crashed rather than succeeding or refusing")
                mismatch = expected != (observed == "success")
            compared += 1
            if not mismatch or "observed" in comparison and observed != comparison["observed"]:
                return
            predictor, action = comparison["predictor"], comparison["action"]
            semantic = {"check": "GC2", "kind": "agreement", "receiver": predictor.get("receiver", "system"),
                        "predictor": predictor["name"], "action": action["name"], "expected": expected,
                        "observed": observed, "args": action.get("args", []), "kwargs": action.get("kwargs", {})}
            if semantic["receiver"] != "system":
                semantic.update(ui_identity(session.spec, prefix, semantic["receiver"]))
            if "option" in comparison:
                semantic["option"] = comparison["option"]
            if "other_predictor" in comparison:
                semantic["other_predictor"] = comparison["other_predictor"]["name"]
            candidates.append({"semantic": semantic, "label": "CONTRADICTION", "prefix": prefix,
                               "outcomes": outcomes, "start": dict(session.start),
                               "comparison": {**comparison, **readings, "expected_permission": expected, "observed": observed}})
        except UnsupportedWorld as exc:
            unknown.append({"check": "GC2", "comparison": comparison, "reason": str(exc)})
        finally:
            session.restore_checkpoint(checkpoint)

    def bound_predictor(binding, action):
        parameters = session.spec["parameters"]
        supplied = dict(zip((row["name"] for row in parameters[action["name"]]), action.get("args", [])))
        supplied.update(action.get("kwargs", {}))
        for row in parameters[action["name"]]:
            if row["name"] not in supplied and "default" in row:
                supplied[row["name"]] = row["default"]
        mapping = {row["predictor"]: row["action"] for row in binding["parameters"]}
        extra = [row for row in parameters[action["name"]] if row["name"] not in mapping.values()]
        if any("default" not in row or row["name"] not in supplied or state_key(supplied[row["name"]]) != state_key(row["default"]) for row in extra):
            raise UnsupportedWorld("action parameters outside the predictor are not verified defaults")
        kwargs = {}
        for row in parameters[binding["predictor"]]:
            target = mapping.get(row["name"])
            if target not in supplied:
                raise UnsupportedWorld("predictor parameters are not uniquely bound to the action")
            kwargs[row["name"]] = supplied[target]
        return {"receiver": "system", "name": binding["predictor"], "kwargs": kwargs}

    def resolve(binding, receiver, inputs):
        if set(binding) == {"value"}:
            return binding["value"]
        if set(binding) == {"input"}:
            return inputs[binding["input"]]
        if set(binding) == {"ui_path"}:
            value = session.objects[receiver]
            for key in binding["ui_path"]:
                if type(value) in {dict, list, tuple}:
                    value = value[key]
                else:
                    value = vars(value)[key]
            return value
        raise UnsupportedWorld("the UI action has no supported source-bound argument")

    def applicable(binding, receiver):
        for guard in binding.get("guards", []):
            if (resolve({"ui_path": guard["ui_path"]}, receiver, {}) == guard["value"]) != guard["equal"]:
                return False
        if binding.get("context_unknown"):
            raise UnsupportedWorld("the UI/domain pair has an unresolved source context")
        return True

    bindings = session.spec.get("predictor_bindings", [])
    ui_bindings = session.spec.get("ui_bindings", [])
    if case is not None:
        current = False
        if case["predictor_mode"] == "offered":
            receiver = case["predictor"].get("receiver")
            if receiver in session.objects and receiver != "system":
                try:
                    if not permission(case["predictor"], "offered", case.get("option")):
                        return {"candidates": [], "unknown": [], "compared": 0, "matched": False, "not_applicable": True}
                except UnsupportedWorld as exc:
                    unknown.append({"check": "GC2", "comparison": case, "reason": str(exc)})
                    return {"candidates": [], "unknown": compact_unknown(), "compared": 0, "matched": False}
            current = (receiver in session.objects and receiver != "system"
                       and case["predictor"]["name"] == session.spec["ui_methods"]["options"]
                       and case["action"].get("receiver") == receiver
                       and case["action"]["name"] == session.spec["ui_methods"]["choose"]
                       and case["action"].get("args") == [case.get("option")])
            if "other_predictor" in case:
                options = [row for row in ui_bindings if row["option"] == case.get("option")]
                active = []
                for binding in options:
                    try:
                        if applicable(binding, receiver):
                            active.append(binding)
                    except (UnsupportedWorld, KeyError, IndexError, TypeError) as exc:
                        unknown.append({"check": "GC2", "option": case.get("option"), "reason": str(exc)})
                if options and not active:
                    return {"candidates": [], "unknown": compact_unknown(), "compared": 0, "matched": False,
                            "not_applicable": not unknown}
                options = active
                shapes = {json.dumps({key: row[key] for key in ("action", "args", "kwargs")}, sort_keys=True) for row in options}
                current = current and len(shapes) == 1
                matched = False
                for binding in options if current else ():
                    try:
                        actual = {"name": binding["action"], "args": [resolve(item, receiver, case["action"].get("kwargs", {})) for item in binding["args"]],
                                  "kwargs": {name: resolve(item, receiver, case["action"].get("kwargs", {})) for name, item in binding["kwargs"].items()}}
                        for pair in bindings:
                            if pair["predictor"] == binding["predictor"] and pair["action"] == binding["action"]:
                                matched |= (bound_predictor(pair, actual) == case["other_predictor"]
                                            and case["other_mode"] == ("why_not" if pair["allow"] == "none" else "can"))
                    except (UnsupportedWorld, KeyError, IndexError, TypeError):
                        continue
                current = current and matched
        else:
            current = any(pair["action"] == case["action"]["name"]
                          and pair["predictor"] == case["predictor"]["name"]
                          and case["predictor_mode"] == ("why_not" if pair["allow"] == "none" else "can")
                          and bound_predictor(pair, case["action"]) == case["predictor"] for pair in bindings)
        if current:
            compare(case)
        else:
            unknown.append({"check": "GC2", "reason": "the compared pair has no current unique source binding"})
        return {"candidates": candidates, "unknown": compact_unknown(), "compared": compared, "matched": bool(candidates)}

    if not bindings and not ui_bindings and not session.spec.get("ui"):
        return {"candidates": [], "unknown": [], "compared": 0, "scope": "observed public calls"}
    concrete = [*facts.get("states", []), *states]
    next_calls = {}
    for state, event in zip(facts.get("states", []), facts.get("events", [])):
        key = state_key([state.get("start", original), state["prefix"]])
        next_calls.setdefault(key, []).append(event["call"])
    for state in states:
        if state["prefix"]:
            key = state_key([state.get("start", original), state["prefix"][:-1]])
            next_calls.setdefault(key, []).append(state["prefix"][-1])
    trace_calls = {}
    for state in states:
        if not state.get("test"):
            continue
        calls = trace_calls.setdefault(state["test"], {})
        for index, recipe in enumerate(state["prefix"]):
            if recipe.get("receiver", "system") != "system":
                continue
            if any(row["action"] == recipe.get("name") for row in bindings):
                calls.setdefault(state_key(recipe), recipe)
            inverse = [row for row in bindings if row["predictor"] == recipe.get("name")]
            if len(inverse) != 1 or state.get("outcomes", [])[index:index + 1] != ["success"]:
                continue
            binding = inverse[0]
            given = dict(zip((row["name"] for row in session.spec["parameters"][recipe["name"]]), recipe.get("args", [])))
            given.update(recipe.get("kwargs", {}))
            for row in session.spec["parameters"][recipe["name"]]:
                if row["name"] not in given and "default" in row:
                    given[row["name"]] = row["default"]
            values = {}
            valid = len(recipe.get("args", [])) <= len(session.spec["parameters"][recipe["name"]]) and set(given) <= {row["name"] for row in session.spec["parameters"][recipe["name"]]}
            for row in binding["parameters"]:
                if row["predictor"] not in given or row["action"] in values and values[row["action"]] != given[row["predictor"]]:
                    valid = False
                    break
                values[row["action"]] = given[row["predictor"]]
            for row in session.spec["parameters"][binding["action"]]:
                if row["name"] not in values:
                    if "default" not in row:
                        valid = False
                    else:
                        values[row["name"]] = row["default"]
            if valid:
                action = {"name": binding["action"], "kwargs": values}
                calls.setdefault(state_key(action), action)
            else:
                unknown.append({"check": "GC2", "predictor": binding["predictor"], "action": binding["action"],
                                "reason": "the same-trace predictor has no unique complete action parameter mapping"})
    seen_states, seen_cases = set(), set()
    try:
        for state in concrete:
            start, prefix = state.get("start", original), state["prefix"]
            if session.start == start and prefix[:len(session.prefix)] == session.prefix:
                for recipe in prefix[len(session.prefix):]:
                    session.step(recipe)
            else:
                session.reset(prefix, start=start)
            observed = list(next_calls.get(state_key([start, prefix]), []))
            observed.extend(trace_calls.get(state.get("test"), {}).values())
            current_key = state_key(session.current)
            key = state_key([current_key, observed])
            if key in seen_states:
                continue
            seen_states.add(key)
            roots, root_keys = [], set()
            for row in observed:
                if row.get("receiver", "system") == "system" and row.get("name") in session.spec["actions"]:
                    parameters = session.spec["parameters"][row["name"]]
                    values = {parameter["name"]: parameter["default"] for parameter in parameters if "default" in parameter}
                    values.update(zip((parameter["name"] for parameter in parameters), row.get("args", [])))
                    values.update(row.get("kwargs", {}))
                    key = state_key([row["name"], values])
                    if key not in root_keys:
                        roots.append(row)
                        root_keys.add(key)
            ui_calls = [row for row in observed if row.get("receiver", "system") != "system"
                        and row.get("name") == session.spec["ui_methods"]["choose"]]
            offers = {}
            for receiver in (name for name in session.objects if name != "system"):
                offers[receiver] = plain(session.query(receiver, session.spec["ui_methods"]["options"]))
                for option in offers[receiver]:
                    if session.spec["ui_facts"].get("option_inputs", {}).get(option) == []:
                        ui_calls.append({"receiver": receiver, "name": session.spec["ui_methods"]["choose"], "args": [option], "kwargs": {}})

            def once(comparison):
                key = state_key([current_key, comparison])
                if key not in seen_cases:
                    seen_cases.add(key)
                    compare(comparison)

            for action in roots:
                for binding in (row for row in bindings if row["action"] == action["name"]):
                    try:
                        predictor = bound_predictor(binding, action)
                        once({"predictor": predictor, "predictor_mode": "why_not" if binding["allow"] == "none" else "can", "action": action})
                    except UnsupportedWorld as exc:
                        unknown.append({"check": "GC2", "predictor": binding["predictor"], "reason": str(exc)})

            for action in ui_calls:
                if action["args"][0] not in offers[action["receiver"]]:
                    continue
                once({"predictor": {"receiver": action["receiver"], "name": session.spec["ui_methods"]["options"]},
                      "predictor_mode": "offered", "option": action["args"][0], "action": action})

            for receiver in (name for name in session.objects if name != "system"):
                for binding in ui_bindings:
                    option = binding["option"]
                    if option not in offers[receiver]:
                        continue
                    try:
                        if not applicable(binding, receiver):
                            continue
                    except (UnsupportedWorld, KeyError, IndexError, TypeError) as exc:
                        unknown.append({"check": "GC2", "option": option, "reason": str(exc)})
                        continue
                    choices = [row for row in ui_bindings if row["option"] == option]
                    unique = {json.dumps({key: row[key] for key in ("action", "args", "kwargs")}, sort_keys=True) for row in choices}
                    if len(unique) != 1:
                        unknown.append({"check": "GC2", "option": option, "reason": "the UI option has multiple source-bound actions"})
                        continue
                    actions = [row for row in roots if row["name"] == binding["action"]]
                    try:
                        actions.append({"name": binding["action"], "args": [resolve(item, receiver, {}) for item in binding["args"]],
                                        "kwargs": {name: resolve(item, receiver, {}) for name, item in binding["kwargs"].items()}})
                    except (UnsupportedWorld, KeyError, IndexError, TypeError):
                        pass
                    mapped = False
                    for action in actions:
                        try:
                            given = dict(zip((row["name"] for row in session.spec["parameters"][action["name"]]), action.get("args", [])))
                            given.update(action.get("kwargs", {}))
                            for row in session.spec["parameters"][action["name"]]:
                                if row["name"] not in given and "default" in row:
                                    given[row["name"]] = row["default"]
                            expressions = dict(zip((row["name"] for row in session.spec["parameters"][action["name"]]), binding["args"]))
                            expressions.update(binding["kwargs"])
                            inputs = {}
                            valid = True
                            for name, expression in expressions.items():
                                if set(expression) == {"input"}:
                                    field = expression["input"]
                                    if field in inputs and inputs[field] != given[name]:
                                        valid = False
                                    inputs[field] = given[name]
                                elif resolve(expression, receiver, inputs) != given[name]:
                                    valid = False
                            if not valid:
                                continue
                            actual = {"name": binding["action"], "args": [resolve(item, receiver, inputs) for item in binding["args"]],
                                      "kwargs": {name: resolve(item, receiver, inputs) for name, item in binding["kwargs"].items()}}
                            pair = next((row for row in bindings if row["predictor"] == binding["predictor"] and row["action"] == binding["action"]), None)
                            if pair is None:
                                raise UnsupportedWorld("the UI offer has no unique root predictor binding")
                            mapped = True
                            choose = {"receiver": receiver, "name": session.spec["ui_methods"]["choose"], "args": [option], "kwargs": inputs}
                            if option in offers[receiver]:
                                ui_calls.append(choose)
                                once({"predictor": {"receiver": receiver, "name": session.spec["ui_methods"]["options"]},
                                      "predictor_mode": "offered", "option": option, "action": choose})
                            once({"predictor": {"receiver": receiver, "name": session.spec["ui_methods"]["options"]},
                                  "predictor_mode": "offered", "option": option,
                                  "other_predictor": bound_predictor(pair, actual),
                                  "other_mode": "why_not" if pair["allow"] == "none" else "can",
                                  "action": choose})
                        except (UnsupportedWorld, KeyError, IndexError, TypeError) as exc:
                            unknown.append({"check": "GC2", "option": option, "reason": "the UI arguments could not be bound: " + str(exc)})
                    if not mapped:
                        unknown.append({"check": "GC2", "option": option, "reason": "UI nondefault arguments were not bound by observed calls or source-bound session values"})
            for receiver, options in offers.items():
                for option in options:
                    if not any(row.get("receiver") == receiver and row.get("args", [None])[0] == option for row in ui_calls):
                        unknown.append({"check": "GC2", "option": option, "reason": "offered choice parameters were not observed or source-bound"})
    finally:
        session.reset(start=original)
    return {"candidates": candidates, "unknown": compact_unknown(), "compared": compared,
            "scope": "observed fresh calls, same-test paired calls and uniquely mapped predictor arguments at verified prefixes, and source-bound offered choices; other parameters unjudged"}

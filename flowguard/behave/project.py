"""Source-pilot operations delegated to the shipped native capture owner."""
from __future__ import annotations
import base64
import hashlib
import json
from pathlib import Path

from flowguard.native import session as _native
from flowguard.native.session import (state_key, _Inputs, _ObservedState, UnsupportedWorld, NativeEngineError, _diagnostic, _Graph, snapshot, _load, construct, ui_identity, _arguments, call, capture_facts, _arena_guard, _Session, _worker, run_isolated_process)


def _audit_phase(session, phase, options):
    """One complete audit computation, with public reconstruction between children."""
    from .checks import crashes, offered, reach, stuck
    from .explore import explore

    def handoff():
        # The observation alone omits prior results and their aliases. Retain
        # those plus the last native call, without copying user objects.
        # Monitoring hits and synthesized transitions remain provenance in the
        # walk facts, not native state. Statement/diff searches use their own operations.
        last = {key: session.last[key] for key in ("call", "outcome", "exception", "value", "stdout", "stderr",
                "before_key", "after_key") if key in session.last} if session.last else None
        return {"start": dict(session.start), "prefix": list(session.prefix), "outcomes": list(session.outcomes),
                "observation": json.loads(json.dumps(session.current, ensure_ascii=False, allow_nan=False)),
                "results_graph": _Graph(session.arena).pack([session.objects, session.results]), "last": last}

    if phase == "walk":
        bounds = {key: options[key] for key in ("seed", "steps", "node_cap", "alphabet_cap") if key in options}
        public_before = session.public_steps - session.replayed_steps
        response = explore(session, **bounds)
        response["rule_uncaptured_steps"] = max(0, session.public_steps - session.replayed_steps - public_before - len(response["events"]))
        response["handoff"] = handoff()
    else:
        walk = options["walk"]
        expected = walk["handoff"]
        if expected["start"] != session.start:
            raise UnsupportedWorld("audit phase handoff has a different starting recipe")
        session.reset(expected["prefix"])
        restored = handoff()
        if restored != expected:
            changed = sorted(key for key in restored.keys() | expected.keys() if restored.get(key) != expected.get(key))
            raise UnsupportedWorld("audit phase public prefix did not restore its complete handoff: " + ", ".join(changed))
        recorded = options.get("test_replay", {"witnesses": [], "prefixes": []})
        states = () if options.get("shared_test_probes", False) else recorded["prefixes"]
        public_before = session.public_steps - session.replayed_steps
        if phase == "crash":
            response = crashes(session, walk, states=states)
        elif phase == "agreement":
            response = offered(session, walk, states=states)
        elif phase == "reach":
            response = reach(session, walk, known=options.get("known", []),
                             witnessed=recorded["witnesses"], states=recorded["prefixes"])
        elif phase == "stuck":
            response = stuck(session, walk, states=recorded["prefixes"])
        else:
            raise UnsupportedWorld("unknown audit phase: " + str(phase))
        response["rule_uncaptured_steps"] = session.public_steps - session.replayed_steps - public_before
    result = {**response, "phase": phase}
    if session.rule_ledger is not None:
        result["rule_captures"] = session.rule_ledger.dump()
    return result


def _run_session(request, arena, observed):
    """Dispatch operations over the one worker-owned native session."""
    session = _Session(request["spec"], request.get("start", {}), arena, observed)
    session.reset()

    def finish(response):
        if session.rule_ledger is not None:
            response["rule_captures"] = session.rule_ledger.dump()
        return response

    operation = request.get("operation", "trace")
    if operation == "trace":
        initial = session.current
        steps = [session.step(item) for item in request["calls"]]
        limits = {}
        inventory = _native.public_inventory(session.objects, limits=limits)
        return finish({"initial": initial, "steps": steps, "final": session.current, "inventory": inventory, "inventory_limits": limits,
                "defaults": session.defaults,
                "seeding": session.seeded, "construction_stdout": session.construction_stdout,
                "construction_stderr": session.construction_stderr})
    from .explore import explore, focused_search, directed_search, evaluate
    options = request.get("options", {})
    session.observe_transitions = options.get("goal", {}).get("kind") == "transition"
    from .explore import observations
    session.observe = observations
    if operation == "rule-proof":
        for recipe in request["calls"]:
            session.step(recipe)
        return finish({"captures": session.rule_ledger.dump(),
                       "outcomes": list(session.outcomes), "execution": session.receipt()})
    if operation in {"explore", "directed", "search", "diff"} and request["calls"]:
        session.reset(request["calls"])
        session.base_prefix = list(request["calls"])
    if operation == "saves":
        persistence = session.spec.get("persistence")
        if not persistence:
            raise UnsupportedWorld("no public save/load root was derived")
        from .explore import plain
        original = dict(session.start)
        prefixes = options.get("prefixes")
        walk = None
        if not options.get("generate", True):
            prefixes = []
        elif prefixes is None or not prefixes:
            walk = explore(session, **{key: options[key] for key in ("seed", "steps", "node_cap", "alphabet_cap") if key in options})
            # Keep concrete categorical and successful-action witnesses, not every walk step.
            prefixes = [[]] + [row["prefix"] for row in walk["witnesses"]
                               if row["semantic"].get("kind") == "query" or
                               row["semantic"].get("kind") == "action" and row["semantic"].get("outcome") == "success"]
        saves, unknown, seen = [], [], set()

        open_shape = [False]

        def structure(value, identifiers):
            if isinstance(value, dict):
                open_shape[0] |= not value
                fixed, dynamic = {}, []
                for key, item in value.items():
                    if key in identifiers:
                        dynamic.append(structure(item, identifiers))
                    else:
                        fixed[key] = structure(item, identifiers)
                if dynamic:
                    fixed["<entity-id>"] = sorted({json.dumps(item, sort_keys=True) for item in dynamic})
                return {"object": fixed}
            if isinstance(value, list):
                open_shape[0] |= not value
                return {"array": sorted({json.dumps(structure(item, identifiers), sort_keys=True) for item in value})}
            return type(value).__name__

        for prefix in prefixes:
            session.reset(prefix, start=original)
            before = state_key(session.current)
            if before in seen:
                continue
            seen.add(before)
            identifiers = {str(value) for entity in session.spec["entities"].values()
                           for value in plain(session.query("system", entity["list"]))}
            name = "saved.json"
            save_call = {"name": persistence["save"], "args": [{"$file": name}]}
            row = session.step(save_call)
            if row["outcome"] != "success":
                unknown.append({"reason": "old public save " + row["outcome"], "exception": row["exception"], "prefix": prefix})
                continue
            path = session.arena / name
            if not path.is_file() or path.is_symlink():
                unknown.append({"reason": "public save did not produce an ordinary file", "prefix": prefix})
                continue
            data = path.read_bytes()
            open_shape[0] = False
            try:
                observed_schema = structure(json.loads(data), identifiers)
                schema = None if open_shape[0] else observed_schema
            except (ValueError, UnicodeError):
                observed_schema = None
                schema = None  # An opaque format retains its source rather than a guessed schema.
            file = {"name": name, "bytes": base64.b64encode(data).decode("ascii"), "sha256": hashlib.sha256(data).hexdigest()}
            session.reset(start={"files": {name: file["bytes"]}})
            loaded = session.step({"name": persistence["load"], "args": [{"$file": name}], "replace": True})
            saves.append({"recipe": {"start": original, "prefix": prefix, "save": save_call}, "file": file,
                          "schema": schema, "observed_schema": observed_schema,
                          "old_load": {key: loaded[key] for key in ("outcome", "exception", "stdout", "stderr")}})
        for file in options.get("committed", []):
            data = base64.b64decode(file["bytes"])
            session.reset(start={"files": {file["name"]: file["bytes"]}})
            loaded = session.step({"name": persistence["load"], "args": [{"$file": file["name"]}], "replace": True})
            saves.append({"recipe": None, "file": {**file, "sha256": hashlib.sha256(data).hexdigest()}, "schema": None,
                          "old_load": {key: loaded[key] for key in ("outcome", "exception", "stdout", "stderr")}})
        response = {"saves": saves, "unknown": unknown, "extent": walk["extent"] if walk else None}
    elif operation == "saved":
        from .checks import saved_files
        response = saved_files(session, **options)
    elif operation == "loading-proof":
        rows = [session.step(item) for item in request["calls"]]
        response = {"matched": bool(rows) and rows[-1]["outcome"] == options["outcome"],
                    "loading": {key: rows[-1][key] for key in ("outcome", "exception", "stdout", "stderr")} if rows else None}
    elif operation == "explore":
        response = explore(session, **options)
    elif operation == "diff":
        from .checks import offered, stuck
        options = dict(options)
        checks = options.pop("checks", True)
        response = explore(session, **options)
        if checks:
            response["stuck"] = stuck(session, response)
            response["agreement"] = offered(session, response)
    elif operation == "search":
        response = focused_search(session, **options)
    elif operation == "directed":
        response = directed_search(session, **options)
    elif operation == "agreement":
        from .checks import offered
        response = offered(session, **options)
    elif operation == "agreement-proof":
        from .checks import offered
        session.reset(request["calls"])
        response = offered(session, {}, case=options["comparison"])
    elif operation == "crashes":
        from .checks import crashes
        response = crashes(session, **options)
    elif operation == "crash-proof":
        from .checks import crashes
        session.reset(request["calls"])
        response = crashes(session, {}, case=options["case"], generate=False)
    elif operation in {"settings", "settings-proof"}:
        from .checks import setting_effects
        response = setting_effects(session, **options)
    elif operation == "witnesses":
        from .testrec import replay_prefixes
        response = replay_prefixes(session, options["recordings"])
        if options.get("probe_tests"):
            from .checks import crashes, offered
            response["agreement"] = offered(session, {}, states=response["prefixes"])
            response["crashes"] = crashes(session, {}, states=response["prefixes"], generate=False)
    elif operation == "test-start":
        from .checks import crashes, offered, stuck
        options = dict(options)
        initial_states = options.pop("initial_states")
        response = explore(session, initial_states=initial_states, **options)
        response["agreement"] = offered(session, response)
        response["crashes"] = crashes(session, response, generate=False)
        response["stuck"] = stuck(session, response, states=initial_states)
        response["reach"] = {"candidates": [], "unknown": [], "scope": "global reach is judged by the shipped audit runs"}
        for check in ("agreement", "crashes", "stuck"):
            for candidate in response[check]["candidates"]:
                actual = [row for row in response["states"] if row["prefix"] == candidate["prefix"]]
                if not actual:
                    actual = [row for row in initial_states if candidate["prefix"][:len(row["prefix"])] == row["prefix"]]
                if actual:
                    source = max(actual, key=lambda row: len(row["prefix"]))
                    candidate["origin"] = "test-start: " + source["test"]
    elif operation == "audit-phase":
        response = _audit_phase(session, options["phase"], options)
    elif operation == "audit":
        from .testrec import replay_prefixes
        options = dict(options)
        recorded = options.get("test_replay")
        if recorded is None:
            recorded = replay_prefixes(session, options.pop("recordings", []))
        options["test_replay"] = recorded
        walk = _audit_phase(session, "walk", options)
        response = {key: value for key, value in walk.items() if key not in {"phase", "handoff"}}
        for phase, field in (("crash", "crashes"), ("agreement", "agreement"), ("reach", "reach"), ("stuck", "stuck")):
            response[field] = {key: value for key, value in _audit_phase(session, phase, {**options, "walk": walk}).items()
                               if key != "phase"}
        response["test_replay"] = {key: value for key, value in recorded.items() if key not in {"prefixes", "witnesses", "replays", "footprint", "execution"}}
    elif operation == "prove":
        divergence = None
        for index, item in enumerate(request["calls"]):
            row = session.step(item)
            expected = options.get("outcomes")
            if expected is not None and (index >= len(expected) or row["outcome"] != expected[index]):
                divergence = index
                break
        response = {"matched": divergence is None and evaluate(session, options["goal"]),
                    "divergence": divergence, "state_key": state_key(session.current),
                    "last": {key: session.last[key] for key in ("call", "outcome", "hit_statements", "before_observations", "after_observations", "transitions") if session.last and key in session.last}}
    else:
        raise UnsupportedWorld("unknown native operation")
    response["execution"] = session.receipt()
    return finish(response)


def _dispatch(request, arena, observed):
    response = _run_session(request, arena, observed)
    if request.get("operation") == "rule-proof":
        footprint = observed.inputs.receipt()
        import copy
        response["footprint"] = copy.deepcopy(footprint)
        observed.enabled = False
        from .rules import judge
        try:
            response["judgment"] = judge(request["options"]["rule_plan"], response["captures"])
        except BaseException as exc:
            raise NativeEngineError(str(exc), phase="judgment") from exc
        response["judgment_footprint"] = copy.deepcopy(observed.inputs.receipt())
    return response


def replay(spec, calls, start=None, *, timeout=30, operation="trace", options=None):
    return _native.replay(spec, calls, start, timeout=timeout, operation=operation, options=options,
                          _dispatch="flowguard.behave.project:_dispatch", _runner=run_isolated_process)


def restore(spec, prefix, checkpoint, start=None, tail=(), *, session=None):
    return _native.restore(spec, prefix, checkpoint, start, tail, session=session)

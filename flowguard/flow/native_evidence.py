"""Native confirmation over an existing flow graph; no second explorer or driver."""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import pprint
import re
from dataclasses import replace

from ..native.inputs import footprint_evidence
from ..trace import Trace, TraceStep
from ..replay import ReplayInput
from .adapter import check_trace, trace_calls, witness_trace
from .checks import GONE, replay_conflict
from .explore import Bounds, Refusal, show_step
from .model import ModelError, State, load_model, show_key

SCHEMA = "flowguard.native-evidence.v1"


def _literal_inputs(inputs):
    data = [{key: getattr(value, key) for key in
             ("external_input", "function_name", "function_input")} for value in inputs]
    text = pprint.pformat(data, sort_dicts=False, width=100)
    try:
        if ast.literal_eval(text) != data:
            raise ValueError("input projection changed")
    except (ValueError, SyntaxError) as error:
        raise ModelError("native replay inputs need an explicit finite literal projection") from error
    return text


def _read_inputs(origin):
    """Read the actual retained call inputs, never an old expected state/output."""
    try:
        if (not isinstance(origin, dict) or origin.get("schema") != "flowguard.native-drift-origin.v1" or
                not isinstance(origin.get("witness"), dict) or
                not re.fullmatch(r"\.flowguard/cache/flow/parts/[0-9a-f]{64}\.json", origin["witness"].get("record", ""))):
            raise ValueError("invalid native witness origin")
        code = origin.get("code_inputs")
        if code is not None and (not isinstance(code, dict) or any(not isinstance(path, str) or
                not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest) for path, digest in code.items())):
            raise ValueError("invalid original code identities")
        oracle = origin.get("model_oracle_digest")
        if oracle is not None and (not isinstance(oracle, str) or not re.fullmatch(r"[0-9a-f]{64}", oracle)):
            raise ValueError("invalid original model oracle identity")
        data = ast.literal_eval(origin["inputs_literal"])
        if not isinstance(data, list) or any(not isinstance(row, dict) or
                set(row) != {"external_input", "function_name", "function_input"} or
                not isinstance(row["function_name"], str) or not isinstance(row["function_input"], dict)
                for row in data):
            raise ValueError("invalid production-call input records")
        return tuple(ReplayInput(**row) for row in data)
    except (KeyError, ValueError, TypeError, SyntaxError) as error:
        raise ModelError("the original native production-call inputs are unavailable or invalid") from error


def _retained_origin(root, entry):
    """Legacy entries recover inputs only from their actual original core receipt."""
    origin = entry.get("detail", {}).get("native_origin")
    if origin is not None:
        return origin
    digest = entry.get("history", {}).get("baseline", {}).get("receipt")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ModelError("the original native computation receipt was not retained")
    from .jobs import read_json
    from .parts import PartResult
    from .project import cache_dir
    raw = read_json(cache_dir(root) / "parts" / (digest + ".json"))
    if raw is None:
        raise ModelError("the original native witness is no longer in the computation cache")
    core = PartResult.from_json(raw)
    if core.digest != digest or core.kind != "core" or core.model != entry["model"]:
        raise ModelError("the original native witness belongs to another computation")
    from .native_finding import native_drift
    drift = native_drift(entry["model"], core)
    if drift is None or drift[0].id != entry["id"]:
        raise ModelError("the original computation has no matching native drift witness")
    return drift[0].native_origin


def _model_calibration(root, graph, entry, current, comparison):
    """Prove a recorded inventory overclaim, retaining every real old promise."""
    if entry['kind'] != 'MODEL DRIFT' or comparison['outcome'] != 'retain':
        return None
    reasons = comparison['reasons']
    if not reasons or any(row['code'] not in {'coverage_removed', 'obligation_relation_unknown'} for row in reasons):
        return None
    origin = _retained_origin(root, entry)
    if _read_inputs(origin):                     # only a pre-behavior construction record
        return None
    from .jobs import read_json
    from .descriptors import closed_rule_evidence
    from .native_finding import native_drift
    from .project import cache_dir
    baseline = entry['history']['baseline']
    digest = baseline['receipt']
    if origin['witness']['record'] != f'.flowguard/cache/flow/parts/{digest}.json':
        return None
    core = read_json(cache_dir(root) / 'parts' / (digest + '.json'))
    if not core or core.get('digest') != digest or core.get('kind') != 'core' or core.get('model') != entry['model']:
        return None
    from .parts import PartResult
    original = native_drift(entry['model'], PartResult.from_json(core))
    descriptor, native = core['info'].get('descriptor', {}), core['info'].get('native', {})
    if (original is None or original[0].id != entry['id'] or original[0].native_origin != origin or not core['complete'] or
            any(descriptor.get(key) != baseline[key] for key in ('scope', 'obligations'))):
        return None
    check = origin['witness']['check']
    if set(native.get('checks', {})) != {check} or native.get('walk'):
        return None
    recorded = native['checks'][check]
    violations = recorded.get('conformance', {}).get('violations', [])
    replayed = recorded.get('conformance', {}).get('replayed_steps', [])
    capture = recorded.get('native', {})
    if (not violations or any(row.get('rule_name') != 'operation_inventory' for row in violations) or
            native.get('operation_coverage', {}).get('construction_check') != check or
            any(capture.get('inventory_limits', {}).values()) or recorded.get('trace', {}).get('steps') != [] or
            len(replayed) != 1 or replayed[0].get('label') != 'construct' or
            replayed[0].get('observed_state') != recorded['trace'].get('initial_state')):
        return None
    inventory = {(receiver, item['name']):item for receiver, items in capture.get('inventory', {}).items()
                 for item in items if item.get('kind') in {'method', 'class', 'static'}}
    names = {receiver + '.' + name: (receiver, name) for receiver, name in inventory}
    missing = set()
    for row in violations:
        message = row.get('message', '')
        if not message.startswith('unmodeled code operation: '):
            return None
        for name in message.removeprefix('unmodeled code operation: ').split(', '):
            if name not in names:
                return None
            missing.add(names[name])
    binding = graph.model.adapter_binding
    prefixes = [row['prefix'] for row in descriptor.get('start_inputs', {}).values() if 'prefix' in row]
    if prefixes != ([list(binding.prefix)] if binding.prefix else []):
        return None
    prefix_targets = {(row.get('receiver', 'system'), row['name']) for row in binding.prefix if 'name' in row}
    selected = set(inventory) - missing - prefix_targets
    targets = [binding.operations[action.name] for action in graph.model.actions]
    targets = [dict(name=value) if isinstance(value, str) else value for value in targets]
    if not selected or selected != {(value.get('receiver', 'system'), value['name']) for value in targets}:
        return None
    anchors, classes = set(), set()
    paths = origin.get('code_inputs') or {}
    for receiver, name in selected:
        item = inventory[receiver, name]
        sources = [row for row in capture.get('inventory_sources', {}).get(receiver, []) if row['owner'] == item['owner']]
        if len(sources) != 1 or not sources[0].get('path'):
            return None
        source = sources[0]
        relative = [path for path in paths if source['path'].replace('\\', '/').endswith('/' + path.replace('\\', '/'))]
        if len(relative) != 1:
            return None
        owner = relative[0] + ':' + source['symbol']
        classes.add(owner)
        anchors.add(owner + '.' + name)
    old_anchors = baseline['scope']['coverage'].get('anchors', [])
    new_anchors = current['scope']['coverage'].get('anchors', [])
    if set(old_anchors) != classes or set(new_anchors) != anchors or set(old_anchors) == set(new_anchors):
        return None
    closed = []
    old_rows = {row['id']:row for row in baseline['obligations']}
    new_rows = {row['id']:row for row in current['obligations']}
    rules = {f'rule:{rule.kind}:{rule.name}':rule for rule in graph.model.rules}
    for reason in reasons:
        name = reason['subject']
        if reason['code'] == 'coverage_removed':
            if name not in {'anchors: ' + anchor for anchor in old_anchors}:
                return None
        else:
            old, new, rule = old_rows.get(name), new_rows.get(name), rules.get(name)
            if (old is None or new is None or rule is None or old['cases'] is not None or new['cases'] is not None or
                    old['definition'] is None or old['definition'] != new['definition']):
                return None
            proof = closed_rule_evidence(rule, old, entry)
            if proof is None or ('source' in proof and proof['source']['path'] != native['operation_coverage'].get('model_path')):
                return None
            closed.append(dict(proof, id=name, definition=old['definition']))
    return dict(kind='model_corrected', original_receipt=digest, inventory_check=check,
                anchors=dict(before=sorted(old_anchors), after=sorted(new_anchors)),
                targets=sorted(receiver + '.' + name for receiver, name in selected),
                closed_rules=sorted(closed, key=lambda row:row['id']))


def _trace_from_inputs(graph, inputs):
    """Rebuild the current model oracle for saved production inputs."""
    calls = []
    for value in inputs:
        matches = [call.index for call in graph.calls if call.action.name == value.function_name and
                   dict(zip(call.action.params, call.args)) == value.function_input]
        if len(matches) != 1:
            raise ModelError(f"the original native call {value.function_name!r} is not in the retained model scope")
        calls.append(matches[0])
    trace = trace_calls(graph, calls)
    return replace(trace, steps=tuple(replace(step, external_input=value.external_input)
                                     for step, value in zip(trace.steps, inputs)))


def _operation_witnesses(graph):
    """One enabled witness per operation; otherwise one known refusal probe."""
    for action in graph.model.actions:
        calls = [call.index for call in graph.calls if call.action is action]
        enabled = next(((state, call) for state, row in enumerate(graph.out)
                        for call in calls if row[call] >= 0), None)
        selected = enabled or next(((state, call) for state, row in enumerate(graph.out)
                                   for call in calls if row[call] <= -3), None)
        if selected is None:
            yield action.name, "unknown", None
        else:
            selection = "enabled" if enabled is not None else "refusal" if graph.complete else "refusal in partial scope"
            yield action.name, selection, witness_trace(graph, *selected)


def path_calls(graph, path):
    calls = {show_step(c.step()): c.index for c in graph.calls}
    try:
        return tuple(calls[step] for step in path)
    except KeyError as error:
        raise ModelError(f"the original call {error.args[0]!r} is not in the retained model scope") from error


def target_trace(graph, target):
    """Find a concrete reaching witness for a retained NEVER REACHED obligation."""
    kind = target["kind"]
    if kind == "action":
        for i, row in enumerate(graph.out):
            for c, successor in enumerate(row):
                if successor >= 0 and graph.calls[c].action.name == target["name"]:
                    return witness_trace(graph, i, c)
    else:
        for i, state in enumerate(graph.states):
            values = State(zip(graph.keys, state))
            if kind == "value":
                reached = any(show_key(k) == target["field"] and repr(v) == target["value"]
                              for k, v in values.items())
            elif kind == "reach":
                rule = next((r for r in graph.model.rules if r.kind == "reach" and r.name == target["name"]), None)
                reached = rule is not None and (rule.pred(values) if rule.obj is None else rule.pred(values, rule.obj))
            elif kind == "option":
                reached = any(option.name == target["name"] and option.offered(values, *args)
                              for option, args in graph.option_calls)
            else:
                raise ModelError("the retained reach target has an unknown kind")
            if reached:
                return witness_trace(graph, i)
    raise ModelError("the original reach obligation has no current reaching witness")


def repair_trace(graph, entry):
    """Include the operation that repairs the original condition in its regression."""
    calls = path_calls(graph, entry.get("path", ()))
    if entry["kind"] == "CONTRADICTION":
        call = entry.get("replay", {}).get("call")
        return trace_calls(graph, (*calls, *path_calls(graph, (call,))))
    trace = trace_calls(graph, calls)
    if entry["kind"] != "STUCK" or any(step.label == "refusal" for step in trace.steps):
        return trace
    spec = entry["replay"]
    start = tuple(trace.final_state[key] for key in graph.keys)
    if spec["stuck"] == "progress":
        rule = next((rule for rule in graph.model.rules if rule.kind == "progress" and rule.name == spec["rule"]), None)
        if rule is None:
            raise ModelError("the original progress obligation is missing")
        def reached(state):
            values = State(zip(graph.keys, state))
            return rule.goal(values) if rule.obj is None else rule.goal(values, rule.obj)
    else:
        pos = next((i for i, key in enumerate(graph.keys) if show_key(key) == spec["key"]), None)
        if pos is None:
            raise ModelError("the original stuck field is missing")
        if repr(start[pos]) != spec["value"]:
            return trace
        def reached(state):
            return state[pos] != start[pos]
    if reached(start):
        return trace
    from .explore import explore
    continuation = explore(graph.model, Bounds(graph.max_states), start=start, reduce=False)
    escape = next((i for i, state in enumerate(continuation.states) if reached(state)), None)
    if escape is None:
        raise ModelError("the original stuck condition has no current escape witness")
    return trace_calls(graph, (*calls, *continuation.path_calls(escape)))


def _literal_trace(trace):
    data = {"initial_state": trace.initial_state,
            "steps": [{k: getattr(step, k) for k in ("external_input", "function_name", "function_input",
                       "function_output", "old_state", "new_state", "label", "reason")} for step in trace.steps]}
    if dict(trace.metadata).get('saved_sample') is not None:
        data['saved_sample'] = dict(trace.metadata)['saved_sample']
    # Emit data, never a project object's repr as executable Python.
    text = pprint.pformat(data, sort_dicts=False, width=100)
    try:
        value = ast.literal_eval(text)
    except (ValueError, SyntaxError) as error:
        raise ModelError("this regression observation needs an explicit finite literal projection") from error
    if value != data:
        raise ModelError("this regression observation has no stable finite literal projection")
    return text


def assert_regression(root, model_path, data, *, max_states=Bounds().max_states):
    """The generated regression uses the current binding and the frozen repaired oracle."""
    root = Path(root).resolve()
    if data.get('saved_sample') is not None:
        from .samples import restore_start
        graph = restore_start(root,root/model_path,data['saved_sample'],Bounds(max_states)).graph
    else:
        loaded = load_model(root / model_path, root)
        from .explore import explore
        graph = explore(loaded.model, Bounds(max_states))
    trace = Trace(tuple(TraceStep(**row) for row in data["steps"]), data["initial_state"])
    if not graph.complete or graph.errors:
        raise AssertionError("the repaired native regression needs a complete current model oracle")
    try:
        current = _trace_from_inputs(graph, tuple(ReplayInput.from_trace_step(step) for step in trace.steps))
    except ModelError as error:
        raise AssertionError("the repaired native regression's model inputs changed: " + str(error)) from error
    keys = ("external_input", "function_name", "function_input", "function_output", "old_state", "new_state", "label")
    if current.initial_state != trace.initial_state or [tuple(getattr(s, key) for key in keys) for s in current.steps] != [
            tuple(getattr(s, key) for key in keys) for s in trace.steps]:
        raise AssertionError("the repaired native regression's frozen model oracle changed")
    result = check_trace(graph, trace)
    if result.status != "conformant":
        raise AssertionError("the repaired native regression no longer conforms: " + result.reason)
    return result


def write_regression(root, model_path, identifier, trace, *, max_states=Bounds().max_states,
                     requirement_entry=None, additional=()):
    """Write executable source, execute it, then return its actual content identity."""
    from .regression import write_executable
    root = Path(root).resolve()
    suffix = '_requirements' if requirement_entry is not None else ''
    relative = Path("tests/flowguard_native") / ("test_" + identifier.replace("-", "_") + suffix + ".py")
    data = _literal_trace(trace)
    function = "test_" + identifier.replace("-", "_")
    source = ("\"\"\"Preserve the native behavior that repaired an earlier flow conflict.\"\"\"\n"
              "from pathlib import Path\nfrom flowguard.flow.native_evidence import assert_regression\n\n"
              f"def {function}():\n"
              "    root = Path(__file__).resolve().parents[2]\n"
              f"    assert_regression(root, {model_path!r}, {data}, max_states={max_states!r})\n\n"
              "if __name__ == '__main__':\n"
              f"    {function}()\n")
    if additional and requirement_entry is None:
        source = ('"""Preserve the corrected model scope and its native operations."""\n'
                  'from pathlib import Path\nfrom flowguard.flow.native_evidence import assert_regression\n\n'
                  f'def {function}():\n    root = Path(__file__).resolve().parents[2]\n'
                  '    for data in [' + ',\n'.join(_literal_trace(item) for item in (trace, *additional)) + ']:\n'
                  f'        assert_regression(root, {model_path!r}, data, max_states={max_states!r})\n\n'
                  "if __name__ == '__main__':\n" + f'    {function}()\n')
    if requirement_entry is not None:
        original = {key:requirement_entry[key] for key in
                    ('id','kind','model','subject','sources','subject_terms','history') if key in requirement_entry}
        original['history'] = {**original['history'], 'latest':None}
        source = ('"""Preserve the implemented replacement requirement and actual native behavior."""\n'
                  'from pathlib import Path\nfrom flowguard.flow.native_evidence import assert_regression\n'
                  'from flowguard.flow.regression import assert_requirement_regression\n\n'
                  f'def {function}():\n    root = Path(__file__).resolve().parents[2]\n'
                  f'    assert_requirement_regression(root, {model_path!r}, {pprint.pformat(original, sort_dicts=True, width=100)})\n'
                  '    for data in [' + ',\n'.join(_literal_trace(item) for item in (trace, *additional)) + ']:\n'
                  f'        assert_regression(root, {model_path!r}, data, max_states={max_states!r})\n\n'
                  "if __name__ == '__main__':\n" + f'    {function}()\n')
    return write_executable(root, relative, source)


def requirement_traces(graph, resolution):
    """Concrete changed-operation/end witnesses, plus actual construction."""
    traces = [trace_calls(graph, ())]
    names = set()
    endings = set()
    for change in resolution['changes']:
        old = change['old']
        if old['kind'] in {'guard','operation'}:
            names.add(old['id'].split(':')[1])
        endings.update(identity.removeprefix('ending:') for identity in change['replacement']
                       if identity.startswith('ending:'))
    for name, _, trace in _operation_witnesses(graph):
        if name in names and trace is not None:
            traces.append(trace)
    for family in endings:
        for index, values in enumerate(graph.states):
            if any(field.family == family and value in graph.model.terminals.get(family, ())
                   for field,value in zip(graph.model.fields,values)):
                traces.append(witness_trace(graph,index))
                break
    return list({_literal_trace(trace):trace for trace in traces}.values())


def _scope(graph):
    return {"states": len(graph.states), "calls": len(graph.calls), "complete": graph.complete,
            "model": graph.model.id or graph.model.name,
            "boundary": "declared model fields, operations, starts and native projection"}


def evaluate_report(root, report, previous=(), *, full=False, observation=None):
    """Confirm current witnesses and prepare complete-scope, executable repair evidence.

    The caller still compares retained scope and sourced obligations before applying
    a closure. A successful replay alone never authorizes closing.
    """
    root, graph = Path(root).resolve(), report.graph
    binding = getattr(graph.model, "adapter_binding", None)
    evidence = {"schema": SCHEMA, "bound": binding is not None, "status": "model-only",
                "scope": _scope(graph), "confirmed": {}, "closures": {}, "checks": [],
                "footprints": [], "reads": [], "writes": [], "limits": []}
    if binding is None:
        evidence["limits"].append("No native binding; findings describe the model only.")
        return evidence
    checks, footprints, reads, traces = {}, {}, set(), {}
    extra_statuses, retained_origins, repair_oracles = set(), {}, {}

    def compare(trace):
        key = _literal_trace(trace)
        if key in traces:
            return traces[key]
        result = check_trace(graph, trace)
        result_data = result.to_dict()
        result_data["native"] = result.native
        result_data["replay_inputs_literal"] = _literal_inputs(result.inputs)
        fingerprint = hashlib.sha256(key.encode()).hexdigest()
        checks[fingerprint] = result_data
        traces[key] = (fingerprint, result)
        footprint = result.native.get("footprint")
        if footprint is not None:
            stamp = footprint_evidence(footprint)
            footprints[json.dumps(footprint, sort_keys=True)] = footprint
            for path in footprint.get("files", {}):
                absolute = Path(path)
                if absolute.is_relative_to(root) and absolute.is_file():
                    reads.add(absolute.relative_to(root).as_posix())
            if stamp.status != "current":
                evidence["limits"].append("Native inputs are " + stamp.status + ": " + stamp.reason)
        else:
            evidence["limits"].append("Native input footprint is unavailable.")
        return fingerprint, result

    # Empty traces still validate construction, old-save restoration and operation inventory.
    construction_id, construction_run = compare(trace_calls(graph, ()))
    coverage = {"strategy": "first enabled witness per declared operation, otherwise one known refusal",
                "model_path": Path(graph.model.path).relative_to(root).as_posix() if graph.model.path else None,
                "witness_budget": len(graph.model.actions), "seed": None, "witnesses": [],
                "construction_check": construction_id}
    evidence["operation_coverage"] = coverage
    if construction_run.status == "conformant":
        for operation, selection, trace in _operation_witnesses(graph):
            if trace is None:
                evidence["limits"].append(operation + ": no known finite operation witness in the explored scope")
                coverage["witnesses"].append({"operation": operation, "selection": selection, "check": None})
                continue
            key, run = compare(trace)
            coverage["witnesses"].append({"operation": operation, "selection": selection,
                                          "model_steps": len(trace.steps), "check": key,
                                          "production_steps": len(run.native["steps"]) if "steps" in run.native else None})
    else:
        coverage["skipped"] = "native construction or inventory did not conform"
    for finding in report.findings:
        if finding.cls != "conflict" or finding.kind == "NEVER REACHED":
            continue
        try:
            calls = path_calls(graph, finding.path)
            if finding.kind == "CONTRADICTION":
                final = finding.detail.get("call")
                name = finding.detail.get("option")
                option = next((item for item in graph.model.options if item.name == name), None) if type(name) is str else None
                if type(final) is not str or option is None:
                    raise ModelError("the contradiction's offered/refused call is unavailable")
                last, = path_calls(graph, (final,))
                if graph.calls[last].action.name != option.action:
                    raise ModelError("the contradiction witness names another option's operation")
                calls = (*calls, last)
            targets = [trace_calls(graph, calls)]
            if finding.kind == "CONTRADICTION" and targets[0].steps[-1].label != "refusal":
                raise ModelError("the contradiction witness does not end with the model's refused call")
            if finding.kind == "STUCK":
                targets += [trace_calls(graph, (*calls, c)) for c in range(len(graph.calls))]
            results = [compare(trace) for trace in targets]
        except ModelError as error:
            evidence["limits"].append(str(error))
            continue
        if all(result.status == "conformant" for _, result in results):
            evidence["confirmed"][finding.id] = {"checks": [key for key, _ in results], "kind": finding.kind}

    full_results = None

    def full_correspondence():
        nonlocal full_results
        if construction_run.status != "conformant":
            return False
        if full_results is None:
            if not graph.complete or graph.errors:
                return False
            full_results = [compare(witness_trace(graph, i, c))
                            for i, row in enumerate(graph.out) for c in range(len(row))]
        return all(result.status == "conformant" for _, result in full_results)

    if any(f.kind == "NEVER REACHED" and f.cls == "conflict" for f in report.findings):
        if full_correspondence():
            for finding in report.findings:
                if finding.kind == "NEVER REACHED" and finding.cls == "conflict":
                    evidence["confirmed"][finding.id] = {"checks": [key for key, _ in full_results],
                                                          "kind": finding.kind, "complete_scope": True}
                    evidence["confirmed"][finding.id]["checks"].insert(0, construction_id)

    present = {finding.id for finding in report.findings}
    for entry in previous:
        if entry["id"] in present or not graph.complete or graph.errors:
            continue
        try:
            from .history import assess
            comparison = None if observation is None else assess(entry, observation, root=root)
            calibration = None if comparison is None else _model_calibration(root, graph, entry, observation, comparison)
            if calibration is not None:
                comparison = {**comparison, 'outcome':'model_absent', 'reasons':[]}
            if comparison is None or comparison['outcome'] not in {'model_absent','requirement_changed'}:
                continue
            changed_requirement = comparison['outcome'] == 'requirement_changed'
            if changed_requirement:
                if any(f.kind in {'STUCK','NEVER REACHED'} for f in report.findings):
                    raise ModelError('the replacement requirement still has a real dead end or unreachable promise')
                targets = requirement_traces(graph,comparison['resolution'])
                trace = targets[0]
            elif entry["kind"] == "MODEL DRIFT":
                origin = _retained_origin(root, entry)
                retained_origins[entry["id"]] = origin
                trace = _trace_from_inputs(graph, _read_inputs(origin))
            elif entry['kind'] == 'FILE CRASH' and graph.model.__dict__.get('_saved_sample_context'):
                trace = trace_calls(graph, ())
            elif entry["kind"] == "NEVER REACHED":
                target = entry.get("detail", {}).get("target")
                if target is None:
                    raise ModelError("the earlier reach target was not recorded")
                trace = target_trace(graph, target)
            else:
                if not entry.get("replay") or replay_conflict(graph.model, entry, Bounds())[0] != GONE:
                    raise ModelError("the original failure condition is still present or unknown")
                trace = repair_trace(graph, entry)
            witness_id, witness_run = compare(trace)
            if not full_correspondence() or witness_run.status != "conformant":
                continue
            if changed_requirement and any(compare(item)[1].status != 'conformant' for item in targets):
                continue
            additional = (tuple(targets[1:]) if changed_requirement else
                          tuple(item for _, _, item in _operation_witnesses(graph) if item is not None)
                          if calibration is not None else ())
            regression = write_regression(root, Path(graph.model.path).relative_to(root).as_posix(), entry["id"], trace,
                                          max_states=graph.max_states,
                                          requirement_entry=entry if changed_requirement else None,
                                          additional=additional)
            evidence["writes"].append(regression["path"])
            reads.add(regression["path"])
            if entry["kind"] == "MODEL DRIFT":
                from .native_finding import oracle_identity
                repair_oracles[entry["id"]] = oracle_identity(trace.to_dict())
            evidence["closures"][entry["id"]] = {"kind": "code_fixed", "complete_scope": True,
                "checks": sorted({construction_id, witness_id, *(key for key, _ in full_results)}), "regression": regression,
                "original_condition_gone": True}
            if calibration is not None:
                evidence['closures'][entry['id']]['model_correction'] = calibration
            if changed_requirement:
                resolution = comparison['resolution']
                evidence['closures'][entry['id']].update(kind='requirement_changed', resolution=resolution,
                    scope_preserved=resolution['scope']['before'] == resolution['scope']['after'])
                reads.update(resolution['paths'])
        except ModelError as error:
            evidence["limits"].append(entry["id"] + ": " + str(error))
    if full:
        # The declared budget follows the number of public calls; it is recorded, not a success threshold.
        from .adapter import walk
        sampled = walk(graph, steps=max(1, len(graph.calls)), seed=0)
        evidence["walk"] = sampled.to_dict()
        evidence["walk"]["native"] = sampled.native
        evidence["walk"]["replay_inputs_literal"] = _literal_inputs(sampled.inputs)
        extra_statuses.add(sampled.status)
        footprint = sampled.native.get("footprint")
        if footprint is not None:
            footprints[json.dumps(footprint, sort_keys=True)] = footprint
            if footprint_evidence(footprint).status != "current":
                evidence["limits"].append("The walk's native inputs are unavailable or changed.")
            reads.update(Path(path).relative_to(root).as_posix() for path in footprint.get("files", {})
                         if Path(path).is_relative_to(root) and Path(path).is_file())
        else:
            evidence["limits"].append("The walk's native input footprint is unavailable.")
    evidence["checks"] = checks
    evidence["footprints"] = list(footprints.values())
    evidence["reads"] = sorted(reads)
    statuses = {result.status for _, result in traces.values()} | extra_statuses
    from .project import file_digest
    evidence["code_inputs"] = {path: file_digest(root, path) for path in sorted(reads)
                               if not Path(path).parts[0] in {".flowguard", "tests", "test"}}
    for receipt in evidence["confirmed"].values():
        receipt["code_inputs"] = evidence["code_inputs"]
        receipt["status"] = "confirmed"
    for identifier, receipt in evidence["closures"].items():
        old = next(entry for entry in previous if entry["id"] == identifier)
        before = (retained_origins[identifier].get("code_inputs")
                  if old["kind"] == "MODEL DRIFT" else old.get("native_confirmation", {}).get("code_inputs"))
        receipt["code_inputs"] = evidence["code_inputs"]
        if receipt['kind'] == 'requirement_changed':
            continue
        if old["kind"] == "MODEL DRIFT":
            original_oracle = retained_origins[identifier].get("model_oracle_digest")
            same_code = before is not None and before == evidence["code_inputs"]
            same_oracle = original_oracle is not None and original_oracle == repair_oracles[identifier]
            corrected_model = receipt.get('model_correction') is not None or original_oracle is not None and not same_oracle
            receipt["kind"] = ("model_corrected" if same_code and corrected_model
                               else "code_fixed" if before is not None and not same_code and same_oracle
                               else "drift_resolved")
        elif before is None:
            receipt["kind"] = "native_validated"
        elif before == evidence["code_inputs"]:
            receipt["kind"] = "model_corrected"
    evidence["status"] = "drift" if "drift" in statuses else "unknown" if "unknown" in statuses or evidence["limits"] else "conformant"
    if evidence["status"] != "conformant":
        evidence["closures"].clear()
        evidence["confirmed"].clear()
    return evidence

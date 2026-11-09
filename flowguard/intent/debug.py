"""Optional views and experiments over the existing anchor runtime; no test runner."""
from __future__ import annotations

from collections import Counter
from contextlib import closing, contextmanager
import importlib
import inspect
import os
from pathlib import Path
import re
import reprlib
import runpy
import sys

from . import anchors, cells, config
from .flow import Capture, Event, Read, Unverified, _group_cases, _matching_nodes, _reading_source, runtime_check
from .runtime import Runtime, outcome_equal
from ..map.common import content_digest


def _result(status, lines, **data):
    return dict(status=status, lines=lines, **data)


def _index(cfg):
    from ..structure import build
    with closing(build(cfg.root, roots=cfg.roots, workers=1)) as graph:
        return anchors.collect(graph)


@contextmanager
def _process(cfg, arguments):
    path, entries, argv, cwd = sys.path, sys.path[:], sys.argv, Path.cwd()
    trace = sys.gettrace()
    inserted = config._INSERTED_PATHS.copy()
    try:
        os.chdir(cfg.root)
        config.setup_path(cfg)
        sys.argv = list(arguments)
        yield
    finally:
        if sys.gettrace() is not trace:
            sys.settrace(trace)
        sys.argv = argv
        path[:] = entries
        sys.path = path
        config._INSERTED_PATHS.clear()
        config._INSERTED_PATHS.update(inserted)
        os.chdir(cwd)


def _events(last_events):
    records = getattr(last_events, 'events', last_events)
    from .flow import _Opaque
    def restored(value):
        if type(value) is dict:
            if set(value) == {'unverified_type'}:
                return _Opaque('historical value was not recorded: ' + str(value['unverified_type']))
            return {key: restored(part) for key, part in value.items()}
        return [restored(part) for part in value] if type(value) is list else value
    events = []
    for record in records:
        if isinstance(record, dict):
            record = restored(record)
            record['parents'] = tuple(tuple(parent) for parent in record.get('parents', ()))
            record['caller'] = tuple(record.get('caller', ()))
            try:
                record = Event(**record)
            except TypeError as error:
                raise ValueError('historical anchor event is malformed; run tests to rebuild it') from error
        events.append(record)
    return events


def save_observation(cfg, events):
    """The optional watch view shares the test plugin's historical SQLite entry."""
    from dataclasses import fields
    import json
    import time
    from .cache import session_baseline
    from .plugin import observation_payload
    from ..structure.store import connect
    payload = observation_payload(dict(stamp=time.time(), baseline=session_baseline(cfg), items={}, paths=[],
        events=[{field.name: getattr(event, field.name) for field in fields(Event)} for event in events]))
    with closing(connect(cfg.cache / 'map.sqlite')) as con, con:
        con.execute('INSERT OR REPLACE INTO meta(k,v) VALUES(?,?)', ('runtime_observations', json.dumps(payload)))


def try_in_test(cfg, anchor, values, *, grid=False):
    """Ask the one ordinary test route to observe values in its real fixture context."""
    from . import plugin
    from .cli import _run_check_pytest
    if plugin._CURRENT is not None and not plugin._CURRENT.closed:
        return _result('grey', [anchor.name + ': use the current test session; a nested pytest session is unavailable'])
    if not anchor.calibrated_by:
        return _result('grey', [anchor.name + ': real context needs calibrated_by naming one ordinary test'])
    selector = anchor.calibrated_by
    file, separator, _ = selector.partition('::')
    path = (cfg.root / file).resolve()
    if not separator or not path.is_relative_to(cfg.root) or not path.is_file():
        return _result('grey', [anchor.name + ': calibrated_by does not identify a project test'])
    with plugin.try_reading(anchor.target, anchor.name, values, grid=grid) as request:
        process = _run_check_pytest(['-q', '-p', 'flowguard.intent.plugin', selector], cfg.root,
                                   cfg.cache / 'try-output.txt', False)
    if process.returncode:
        return _result('red', [f'{anchor.name}: ordinary test exited {process.returncode}; details: {cfg.cache / "try-output.txt"}'],
                       exit_code=process.returncode, reasons=request.get('reasons', []))
    readings = request['readings']
    if len(readings) != 1:
        return _result('grey', [f'{anchor.name}: test reached {len(readings)} readings; choose one unambiguous invocation'])
    reading = readings[0]
    requested = {**request.get('actual_inputs', {}), **values}
    rows = reading.rows if grid else [(inputs, value) for inputs, value in reading.rows
        if all(name in inputs and outcome_equal(inputs[name], expected) for name, expected in requested.items())]
    reasons = list(dict.fromkeys([*request.get('reasons', []), *reading.reasons]))
    if reading.status != 'ok' or reasons or not rows or not grid and len(rows) != 1:
        return _result(request.get('status', 'grey'), [anchor.name + ': ' + ('; '.join(reasons) or 'requested reading unavailable')],
                       rows=rows, reasons=reasons)
    reasons = list(dict.fromkeys(request.get('partition_reasons', []))) if grid else []
    lines = [f'{anchor.name}: {len(rows)} observed input classes in its real test context']
    lines.extend('grey: ' + reason for reason in reasons)
    lines.extend(f'{inputs!r} → {value!r}' for inputs, value in rows)
    return _result('grey' if reasons else 'ok', lines, rows=rows, tested=len(rows), value=rows[0][1] if not grid else None)


def show_observation(cfg, name, index, last_events=(), *, model=None):
    """History stays history; changed or unidentified source never becomes current evidence."""
    events = _events(last_events)
    found = index.named(name)
    fresh, stale = [], []
    for event in events:
        try:
            _reading_source(event, index, Read('view'))
        except Unverified as error:
            stale.append(str(error))
        else:
            fresh.append(event)
    if found:
        lines = [f'{name}: historical observations (not a new verification)']
        relevant = [event for event in fresh if event.anchor == name]
        fresh_ids = {id(event) for event in fresh}
        outdated = [event for event in events if event.anchor == name and id(event) not in fresh_ids]
        for anchor in found:
            changed = not (cfg.root / anchor.file).is_file() or content_digest(cfg.root / anchor.file) != anchor.source_digest
            roles = ', '.join(f'{p.name}: {p.role} ({p.unit or "unit unspecified"})' for p in anchor.parameters)
            own = [event for event in relevant if event.site == anchor.target]
            counts = Counter(event.phase for event in own)
            outcomes = Counter(reprlib.repr(event.result) if event.phase == 'return' else 'raises ' + reprlib.repr(event.error)
                               for event in own if event.phase in {'return', 'raise'})
            lines.append(f'{anchor.file}:{anchor.target_line} {anchor.kind}; {roles or "no inputs"}; {dict(counts)}' + ('; stale source' if changed else ''))
            lines.append(f'results: {dict(outcomes.most_common(5))}; {len(outcomes)} distinct observed outputs')
        rules = [rule.id for rule in getattr(model, 'rules', {}).values() if name in rule.anchors]
        lines.append('rules: ' + (', '.join(rules) if model is not None else 'model not supplied'))
        if outdated:
            lines.append(f'stale: {len(outdated)} historical events do not identify current source')
        return _result('grey' if outdated or not relevant or any(a.issues for a in found) else 'ok', lines,
                       events=relevant, stale=len(outdated))
    loaded = model
    if loaded is None:
        from .loader import load
        with _process(cfg, sys.argv):
            loaded = load(cfg, anchor_index=index)
    flow = loaded if getattr(loaded, 'id', None) == name else getattr(loaded, 'flows', {}).get(name)
    if getattr(loaded, 'errors', ()):
        return _result('red', [f'red load {error["file"]}:{error["line"]}: {error["msg"]}' for error in loaded.errors])
    if flow is None:
        return _result('grey', [f'{name}: no indexed anchor or model'])
    checked = runtime_check(flow, fresh, index, rules=getattr(loaded, 'rules', {}))
    node_counts, edge_counts = Counter(), Counter()
    cases, _, _, _ = _group_cases(flow, fresh, index)
    for case_events in cases.values():
        path = []
        for event in case_events:
            nodes = _matching_nodes(flow, event, case_events, index)
            if len(nodes) == 1:
                node_counts[nodes[0].name] += 1
                path.append(nodes[0].name)
        edge_counts.update(zip(path, path[1:]))
    lines = [f'{name}: historical model observations (not a new verification)']
    lines.extend(f'{node.name}: {node.reference}/{node.phase}, observed {node_counts[node.name]}' for node in flow.nodes)
    lines.extend(f'{a} → {b}: {edge_counts[a, b]}' + ('; unobserved' if not edge_counts[a, b] else '') for a, b in flow.edges)
    lines.extend('red: ' + reason for reason in checked['red'])
    lines.extend('grey: ' + reason for reason in checked['grey'])
    if stale:
        lines.append(f'stale: {len(stale)} historical events excluded')
    status = 'grey' if stale and checked['verdict'] != 'red' else checked['verdict']
    return _result(status, lines, check=checked, node_counts=dict(node_counts), edge_counts=dict(edge_counts), stale=len(stale))


def try_anchor(cfg, name, values, grid=False, runner=None, *, index=None):
    """Use the same replay boundary as tests; fixtures require their current session."""
    index = index or _index(cfg)
    found = index.named(name, 'sensor')
    if len(found) != 1:
        return _result('grey', [f'{name}: choose one unambiguous sensor (found {len(found)})'])
    anchor = found[0]
    if anchor.contexts or anchor.receiver:
        if runner is None:
            return _result('grey', [f'{name}: needs its real test context; no current-session runner supplied'])
        return runner(cfg, anchor, values, grid=grid)
    try:
        _, tree, function = anchors._source(cfg.root, anchor)
        with _process(cfg, sys.argv):
            reasons = anchors._import_reasons(cfg, anchor, tree, function)
            if reasons:
                return runner(cfg, anchor, values, grid=grid) if runner is not None else _result('grey', [f'{name}: ' + '; '.join(reasons)])
            from .imports import prepare
            prepare(cfg.root)
            module = importlib.import_module(anchor.module)
            fn = module
            for part in anchor.qual.split('.'):
                fn = getattr(fn, part)
            if (not inspect.isfunction(fn) or Path(fn.__code__.co_filename).resolve() != (cfg.root / anchor.file).resolve()
                    or fn.__qualname__.replace('.<locals>.', '.') != anchor.qual):
                return _result('grey', [f'{name}: loaded callable does not identify current source'])
            supplied = {p.name: values[p.name] for p in anchor.inputs if p.name in values}
            if set(values) - set(supplied):
                return _result('red', [f'{name}: undeclared or context inputs'])
            signature = inspect.signature(fn)
            positional = []
            for parameter in signature.parameters.values():
                if parameter.kind == parameter.POSITIONAL_ONLY:
                    positional.append(supplied.pop(parameter.name, parameter.default))
            bound = signature.bind(*positional, **supplied)
            bound.apply_defaults()
            for parameter in anchor.inputs:
                actual = bound.arguments[parameter.name]
                try:
                    accepted = anchors._accepts(parameter.source_type, actual)
                except (ValueError, SyntaxError):
                    kind = anchors.parameter_kind(parameter, actual)
                    accepted = kind is not None and kind.accepts(actual)
                if not accepted:
                    return _result('red', [f'{name}: {parameter.name} has the wrong source type'])
            runtime = Runtime(cfg.root)
            if not grid:
                reason = runtime.safety(fn, bound.arguments)
                if reason:
                    return _result('grey', [f'{name}: {reason}'])
                value, refused = runtime.guarded(fn, bound)
                if refused:
                    return _result('grey', [f'{name}: {refused}'])
                return _result('ok', [f'{name}: {dict(bound.arguments)!r} → {value!r}'], value=value,
                               rows=[(dict(bound.arguments), value)], tested=1, reasons=[])
            decision = anchors.decision_reading(cfg.root, anchor)
            space = cells.build_space(decision.kinds, decision.reading.consts, decision.reading.planes,
                                      decision.reading.links, decision.reading.reasons, decision.reading.hints)
            axes = space.pts
            complete = space.complete and set(axes) == {p.name for p in anchor.inputs} and not decision.issues
            for parameter in anchor.inputs:
                axes.setdefault(parameter.name, [bound.arguments[parameter.name]])
            try:
                value = runtime.observe(fn, bound, name=name, axes=axes, private=True)
            except Exception as error:
                value = cells.Raised(error)
            reading = runtime.readings[-1]
            rows = reading.rows if grid else [(dict(bound.arguments), value)]
            lines = [f'{name}: {len(reading.rows)} representatives evaluated' + ('; source partition incomplete' if not complete else '')]
            lines.extend(f'{inputs!r} → {outcome!r}' for inputs, outcome in rows)
            return _result(reading.status if complete else 'grey', lines, value=value, rows=rows,
                           tested=len(reading.rows), reasons=reading.reasons)
    except (OSError, ValueError, TypeError, ImportError, AttributeError) as error:
        return _result('grey', [f'{name}: unavailable: {type(error).__name__}: {error}'])


def watch(cfg, command, *, index=None, model=None):
    """Execute Python normally in this process, recording anchors without replay."""
    command = list(command)
    arguments = command
    if command and re.fullmatch(r'python(?:\d+(?:\.\d+)*)?(?:\.exe)?', Path(command[0]).name, re.IGNORECASE):
        arguments = command[1:]
    module = len(arguments) >= 2 and arguments[0] == '-m'
    script = bool(arguments) and arguments[0].endswith('.py')
    if not (module or script):
        return _result('grey', ['unsupported watch command: use a Python script or python -m module'], exit_code=2, events=[], executed=False)
    index = index or _index(cfg)
    exit_code, failure = 0, None
    with _process(cfg, arguments):
        if model is None:
            from .loader import load
            model = load(cfg, anchor_index=index)
        from .imports import prepare
        prepare(cfg.root)
        with Capture(cfg.root, index, 'watch', _ordinary=True, discover=True) as captured:
            if not captured._active:
                return _result('grey', captured.issues, exit_code=2, events=[], executed=False)
            try:
                if module:
                    sys.argv = arguments[1:]
                    runpy.run_module(arguments[1], run_name='__main__', alter_sys=True)
                else:
                    runpy.run_path(str(Path(arguments[0]).resolve()), run_name='__main__')
            except SystemExit as error:
                exit_code = error.code if isinstance(error.code, int) else 0 if error.code is None else 1
                if error.code is not None and not isinstance(error.code, int):
                    failure = str(error.code)
            except Exception as error:
                exit_code, failure = 1, f'{type(error).__name__}: {error}'
        checks = {name: runtime_check(flow, captured.events, index, rules=getattr(model, 'rules', {}))
                  for name, flow in getattr(model, 'flows', {}).items()}
        load_errors = getattr(model, 'errors', ())
        red = bool(load_errors) or any(check['verdict'] == 'red' for check in checks.values())
        grey = any(check['verdict'] == 'grey' for check in checks.values())
        status = 'red' if exit_code or red else 'grey' if grey or captured.issues or not captured.events else 'ok'
        lines = [f'watch: target exited {exit_code}; {len(captured.events)} anchor events']
        lines.extend(captured.issues)
        lines.extend(f'red load {error["file"]}:{error["line"]}: {error["msg"]}' for error in load_errors)
        for name, check in checks.items():
            lines.extend(f'{level} {name}: {reason}' for level in ('red', 'grey') for reason in check[level])
        if failure:
            lines.append(failure)
        return _result(status, lines, exit_code=exit_code, events=captured.events, executed=True, error=failure, checks=checks)

"""The historical observation view `show NAME` prints over the existing anchor runtime; no test runner."""
from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
import os
from pathlib import Path
import reprlib
import sys

from . import config
from .flow import Event, Read, Unverified, _group_cases, _matching_nodes, _reading_source, runtime_check
from ..map.common import content_digest


def _result(status, lines, **data):
    return dict(status=status, lines=lines, **data)


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
        lines = []
        relevant = [event for event in fresh if event.anchor == name]
        fresh_ids = {id(event) for event in fresh}
        outdated = [event for event in events if event.anchor == name and id(event) not in fresh_ids]
        for anchor in found:
            own = [event for event in relevant if event.site == anchor.target]
            if not own:                 # nothing observed there: no empty `{}` and `0 distinct observed outputs` lines
                continue
            changed = not (cfg.root / anchor.file).is_file() or content_digest(cfg.root / anchor.file) != anchor.source_digest
            roles = ', '.join(f'{p.name}: {p.role} ({p.unit or "unit unspecified"})' for p in anchor.parameters)
            counts = Counter(event.phase for event in own)
            outcomes = Counter(reprlib.repr(event.result) if event.phase == 'return' else 'raises ' + reprlib.repr(event.error)
                               for event in own if event.phase in {'return', 'raise'})
            lines.append(f'{anchor.file}:{anchor.target_line} {anchor.kind}; {roles or "no inputs"}; {dict(counts)}' + ('; stale source' if changed else ''))
            lines.append(f'results: {dict(outcomes.most_common(5))}; {len(outcomes)} distinct observed outputs')
        if outdated:
            lines.append(f'stale: {len(outdated)} historical events do not identify current source')
        if lines:
            lines.insert(0, f'{name}: historical observations (not a new verification)')
        rules = [rule.id for rule in getattr(model, 'rules', {}).values() if name in rule.anchors]
        if rules or model is None:          # no rule names it: no line (`show` says it is not referenced)
            lines.append('rules: ' + (', '.join(rules) if model is not None else 'model not supplied'))
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
    lines.extend(f'{a} -> {b}: {edge_counts[a, b]}' + ('; unobserved' if not edge_counts[a, b] else '') for a, b in flow.edges)
    lines.extend('red: ' + reason for reason in checked['red'])
    lines.extend('grey: ' + reason for reason in checked['grey'])
    if stale:
        lines.append(f'stale: {len(stale)} historical events excluded')
    status = 'grey' if stale and checked['verdict'] != 'red' else checked['verdict']
    return _result(status, lines, check=checked, node_counts=dict(node_counts), edge_counts=dict(edge_counts), stale=len(stale))

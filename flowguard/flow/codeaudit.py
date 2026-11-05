"""Project-wide recorded-code part; execution and route analysis belong to fallback.

This receipt covers selected native tests/invocations. It is not a flow Model or
an exhaustive claim about application states.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from ..map.common import content_digest
from .checks import CONFLICT, ERROR_CLS, Finding, make_finding
from .parts import PartResult, PartSpec, part_digest, register

KIND, PROJECT = 'code-audit', '@recorded-code'


def source_files(root):
    from .fallback import _project_files
    return sorted(name for name in _project_files(Path(root)) if name.endswith('.py') or
                  Path(name).name in {'pyproject.toml', 'pytest.ini', 'setup.cfg', 'tox.ini'})


def spec(root, nodeids):
    # The inventory invalidates newly added/deleted source, without scanning ASTs
    # or executing a test in the command/status process.
    return PartSpec(KIND, PROJECT, (('tests', tuple(sorted(set(nodeids)))),
                                   ('inventory', tuple(source_files(root)))))


def current(root, result):
    from ..native.inputs import footprint_evidence
    if result.info.get('inventory') != source_files(root):
        return False
    footprint = result.info.get('analysis', {}).get('recording', {}).get('footprint')
    return footprint_evidence(footprint).status == 'current'


def _site_source(root, site):
    source = (Path(root) / site['path']).read_text(encoding='utf-8')
    tree = ast.parse(source)
    node = next((n for n in ast.walk(tree) if (getattr(n, 'lineno', None), getattr(n, 'col_offset', None)) == tuple(site['node'])), None)
    if isinstance(node, ast.ExceptHandler):
        owner = next((parent for parent in ast.walk(tree) if isinstance(parent, (ast.Try, ast.TryStar))
                      and node in parent.handlers), None)
        if owner is not None:
            # Equal except bodies can hide different primary operations. Keep
            # both primary and selected handler semantics in the stable anchor.
            return ast.dump(owner, include_attributes=False) + '::' + ast.dump(node, include_attributes=False)
    return ast.dump(node, include_attributes=False) if node is not None else ''


def route_key(root, site):
    # A semantic source anchor survives unrelated line insertions. Invocation
    # tokens and the scanner's positional Site.id never become conflict identity.
    shape = _site_source(root, site)
    return f"{site['path']}#{site['function']}:{site['kind']}:" + hashlib.sha256(shape.encode()).hexdigest()[:16]


def _guard(root, references):
    """Retain the caller/alternate/signatures; only witnessed primary bodies may change."""
    from .fallback import _definitions
    by_file = {}
    for reference in references:
        path, _, name = reference.partition('#')
        by_file.setdefault(path, set()).add(name)
    guards = {}
    for path, names in by_file.items():
        tree = ast.parse((Path(root) / path).read_text(encoding='utf-8'))
        _, definitions = _definitions(tree)
        found = set()
        for node, name, _, _ in definitions:
            if name in names:
                found.add(name)
                node.body = [ast.Pass()]
        if found != names:
            return None
        guards[path] = hashlib.sha256(ast.dump(tree, include_attributes=False).encode()).hexdigest()
    return guards


def _primary_refs(route, recordings):
    refs = set(route['site']['primary_calls'])
    for failure in route['primary_failures']:
        for row in recordings:
            if row['test'] != failure['test']:
                continue
            for event in row['observer_events']:
                if (event.get('parent_call_token') == failure.get('site_call_token') and
                        event.get('kind') == 'return' and event.get('return_status') == 'raised'):
                    refs.add(event['path'] + '#' + event['function'])
    return sorted(refs)


def _closures(root, analysis, previous):
    """A deliberately finite primary-body repair, using the already executed original tests.

    No arbitrary Python implication claim: changed callers/alternates, test bytes,
    input stamps, signatures, or incomplete capture retain that exact observation.
    """
    if analysis['capture_status'] != 'current':
        return {}
    from ..native.inputs import footprint_evidence
    if footprint_evidence(analysis['recording'].get('footprint')).status != 'current':
        return {}
    current_rows = {row['test']: row for row in analysis['recording']['recordings']}
    routes = {route_key(root, row['site']): row for row in analysis['sites']}
    closures = {}
    for entry in (previous or {}).get('conflicts', []):
        if not is_entry(entry) or entry['kind'] != 'MASKING':
            continue
        old = entry['code_evidence']
        refs, guard = old.get('primary_refs'), old.get('primary_guard')
        if not refs or not guard or _guard(root, refs) != guard:
            continue
        route = routes.get(entry['subject'])
        if not route or route['classification'] != 'DEAD' or not route['negative_scope_complete']:
            continue
        if not set(old['route']['primary_failed']) <= set(route['primary']):
            continue
        if sorted(current_rows) != sorted(row['test'] for row in old['recordings']):
            continue
        if any(current_rows[row['test']]['digest'] != row['digest'] or
               current_rows[row['test']]['pytest_outcome'] != 'passed' for row in old['recordings']):
            continue
        original = old.get('footprint') or {}
        current_footprint = analysis['recording'].get('footprint') or {}
        allowed = {str((Path(root) / name).resolve()) for name in guard}
        if not original.get('reusable') or not current_footprint.get('reusable'):
            continue
        if ({name: stamp for name, stamp in original.get('files', {}).items() if name not in allowed} !=
                {name: stamp for name, stamp in current_footprint.get('files', {}).items() if name not in allowed} or
                original.get('directories') != current_footprint.get('directories') or
                original.get('directory_uses') != current_footprint.get('directory_uses')):
            continue
        # Also retain every unrelated project source/config/data checked originally.
        if any(name not in guard and analysis.get('checked_inputs', {}).get(name) != value
               for name, value in old['inputs'].items()):
            continue
        regressions = [{'path': Path(row['source']).resolve().relative_to(Path(root)).as_posix(),
                        'digest': row['digest'], 'nodeid': row['test'], 'passed': True}
                       for row in old['recordings']]
        closures[entry['id']] = {'kind': 'code_fixed', 'boundary': 'original recorded tests/invocations only',
                                'complete_scope': True, 'original_condition_gone': True,
                                'primary_refs': refs, 'source_guard': guard, 'regressions': regressions}
    return closures


def code_part(ctx):
    from .fallback import analyze
    from .descriptors import input_evidence
    from ..native.inputs import footprint_evidence
    root, options = Path(ctx.root), dict(ctx.spec.options)
    before = source_files(root)
    initial = {name: content_digest(root / name) for name in before}
    ctx.progress({'model': PROJECT, 'kind': KIND, 'phase': 'recording selected tests and classifying observed routes'})
    analysis = analyze(root, nodeids=list(options['tests']))
    findings = []
    for row in analysis['conflicts']:
        site = row['site']
        anchor = route_key(root, site)
        text = row['reason'] + f" ({site['path']}:{site['line']} {site['function']})"
        findings.append(make_finding(row['classification'], CONFLICT, PROJECT, anchor, text,
                                    detail={'code_audit': True, 'route': row, 'boundary': 'recorded tests/invocations only'},
                                    line=site['line']).to_json())
    failed_tests = [row['test'] for row in analysis['recording'].get('recordings', [])
                    if row.get('pytest_outcome') == 'failed']
    findings += [test_failure(nodeid).to_json() for nodeid in failed_tests]
    reads = sorted(set(before) | set(analysis['sources']))
    # The native owner supplies observed data/config dependencies as well.
    for name, stamp in analysis['recording'].get('footprint', {}).get('files', {}).items():
        path = Path(name)
        # Devices keep their typed native footprint, not fictitious Git file
        # bytes (Windows' null device can have a project-relative path).
        # A symlink itself remains an actual staged entry, even to a device.
        if (not stamp.get('directory') and (not stamp.get('opaque') or 'link' in stamp)
                and path.is_relative_to(root) and not path.relative_to(root).as_posix().startswith('.flowguard/')):
            reads.append(path.relative_to(root).as_posix())
    reads = sorted(set(reads))
    unchanged = before == source_files(root) and all(content_digest(root / name) == digest for name, digest in initial.items())
    if not unchanged:
        analysis['capture_status'] = 'unknown'
        analysis['errors'].append({'reason': 'project sources changed during code capture'})
    info = {'analysis': analysis, 'inventory': before, 'tests': list(options['tests']),
            'inputs': input_evidence(root, reads), 'boundary': 'recorded tests/invocations only'}
    from .project import read_conflicts
    analysis['checked_inputs'] = info['inputs']
    info['closures'] = _closures(root, analysis, read_conflicts(root)) if unchanged else {}
    inputs_current = footprint_evidence(analysis['recording'].get('footprint')).status == 'current'
    info.update(reusable=inputs_current, test_failures=failed_tests)
    return PartResult(KIND, PROJECT, part_digest(root, ctx.spec, reads),
                      analysis['capture_status'] == 'current' and unchanged, findings, info, reads)


register(KIND, code_part, on_request=True)


def is_entry(entry):
    return entry.get('model') == PROJECT and isinstance(entry.get('code_evidence'), dict)


def declared_entries(data):
    return [entry for entry in (data or {}).get('closed', [])
            if entry.get('closure', {}).get('kind') == 'owner_declared']


def apply_declared(root, data):
    """A projection of existing immutable decisions into the same conflict ledger."""
    if not data:
        return data
    from .decisions import evaluate_decision
    from ..map.mapfile import MapError
    conflicts, closed = [], list(data.get('closed', []))
    for entry in data['conflicts']:
        decision = None
        if entry['kind'] == 'BOTH' and is_entry(entry):
            for identifier in entry.get('history', {}).get('decision_refs', []):
                try:
                    state = evaluate_decision(root, entry, identifier)
                except MapError:
                    continue
                if state['outcome'] == 'routes_declared':
                    decision = identifier
                    break
        if decision is None:
            conflicts.append(entry)
        else:
            closed = [old for old in closed if old['id'] != entry['id']]
            closed.append(dict(entry, closure={'kind': 'owner_declared', 'decision': decision,
                                               'code_fixed': False, 'boundary': 'existing witnessed routes only'}))
    return dict(data, conflicts=conflicts, closed=closed)


def reopen_declared(root, data):
    if not data:
        return data
    from .decisions import evaluate_decision
    from ..map.mapfile import MapError
    conflicts, closed = list(data['conflicts']), []
    for entry in data.get('closed', []):
        kind = entry.get('closure', {}).get('kind')
        if kind not in {'owner_declared','requirement_changed'}:
            closed.append(entry)
            continue
        try:
            if kind == 'requirement_changed':
                from .history import resolution_current
                resolution_current(root, entry, entry['closure'].get('resolution'))
            else:
                state = evaluate_decision(root, entry, entry['closure']['decision'])
                if state['outcome'] != 'routes_declared':
                    raise MapError('existing route purpose is no longer declared')
        except MapError as error:
            restored = {key: value for key, value in entry.items() if key != 'closure'}
            restored['decision_reopened'] = str(error)
            if not any(row['id'] == restored['id'] for row in conflicts):
                conflicts.append(restored)
        else:
            closed.append(entry)
    return dict(data, conflicts=conflicts, closed=closed)


def declared_lines(data):
    return [f"DECLARED BOTH {entry['subject']} [{entry['id']}]: existing routes authorized by {entry['closure']['decision']}; no code-fixed claim"
            for entry in declared_entries(data)]


def result_of(assembled):
    return next((r for _, r, _, _ in assembled.code if r is not None), None)


def evidence(root, finding, result):
    row = finding.detail['route']
    recording = result.info['analysis']['recording']
    refs = _primary_refs(row, recording.get('recordings', []))
    return {'boundary': 'recorded tests/invocations only', 'receipt': result.digest,
            'route': row, 'route_shape': _site_source(root, row['site']),
            'primary_refs': refs, 'primary_guard': _guard(root, refs) if refs else None,
            'tests': result.info['tests'], 'inputs': result.info['inputs'],
            'recordings': recording.get('recordings', []), 'footprint': recording.get('footprint'),
            'source_facts': result.info['analysis']['sources']}


def closure(root, entry, result):
    proof = result.info.get('closures', {}).get(entry['id']) if result is not None else None
    if proof is None or not result.complete or not current(root, result):
        return None
    if any(content_digest(Path(root) / row['path']) != row['digest'] or row['passed'] is not True
           for row in proof['regressions']):
        return None
    return dict(proof, receipt=result.digest)


def kept(root, entry, result):
    # A finite regression/primary-repair owner may supply a verified closure.
    # Absence in new tests, a removed handler or an incomplete scope cannot do so.
    if result is None:
        why = 'recorded code finding retained; explicit --tests is required to retest its original scope'
    else:
        why = 'original recorded code observation not yet verified repaired; keep this exact scope UNKNOWN'
    return Finding(entry['kind'], CONFLICT, PROJECT, entry['subject'], entry['text'], (),
                   tuple(entry.get('sources', [])), (), '', {'entry': entry, 'kept': why, 'code_audit': True},
                   None, entry['id'])


def record(root, assembled, previous):
    result = result_of(assembled)
    if result is None:
        old = (previous or {}).get('code_audit')
        if old:
            return dict(old, stale=saved_result(root, old) is None)
        return None
    return {'boundary': 'recorded tests/invocations only', 'digest': result.digest,
            'planned': next(p.to_json() for p, r, _, _ in assembled.code if r is result),
            'finished': True, 'complete_observed_scope': result.complete,
            'reusable': result.info['reusable'], 'unknown': not result.complete or not result.info['reusable'],
            'test_failures': result.info['test_failures'],
            'tests': result.info['tests'], 'inputs': result.info['inputs'],
            'counts': result.info['analysis']['counts'], 'errors': result.info['analysis']['errors'],
            'witnesses': [row for row in result.info['analysis']['sites']
                          if row['classification'] in {'MASKING', 'BOTH', 'VISIBLE'}]}


def scope_unknown(record):
    return record is not None and (record.get('stale', False) or not record.get('complete_observed_scope') or not record.get('reusable', True))


def test_failure(nodeid):
    return make_finding('TEST FAILED', ERROR_CLS, PROJECT, nodeid,
                        'selected native pytest case failed: ' + nodeid,
                        detail={'code_audit': True, 'boundary': 'recorded tests/invocations only'})


def saved_result(root, record):
    from .jobs import Planned, lookup
    if not record:
        return None
    return lookup(root, Planned.from_json(record['planned']), recorded_digest=record['digest'])


def summary(root, record):
    if not record:
        return []
    available = saved_result(root, record)
    state = ('UNKNOWN observed scope; explicit retest required' if not record['complete_observed_scope'] else
             'recorded finite observation; non-reusable inputs; pending explicit retest' if not record.get('reusable', True) else
             'current' if available is not None else 'stale; pending explicit retest')
    counts = record.get('counts', {})
    lines = [f"recorded code: {state}; selected tests/invocations only; no flow-state exhaustiveness claim"]
    lines += ['  selected native test failed: ' + nodeid for nodeid in record.get('test_failures', [])]
    for row in record.get('witnesses', []):
        if row['classification'] == 'VISIBLE':
            lines += ['  witnessed VISIBLE: ' + row['reason'], *fact_lines(row)]
    return [*lines, '  observations: ' + ', '.join(f'{key}={value}' for key, value in counts.items()),
            '  retest: python -m flowguard check --tests ' + ' '.join(record['tests'])]


def question(entry):
    if entry['kind'] == 'MASKING':
        return 'repair the witnessed primary failure in code; retain the original regression and retest its recorded scope; owner choice cannot waive masking'
    return 'inspect the two witnessed implementations; consolidate duplicate behavior or use stored owner words to establish a genuinely intended route'


def fact_lines(route):
    site = route['site']
    lines = [f"  source: {site['path']}:{site['line']} {site['function']}; recorded tests/invocations only",
             '  cases: ' + ', '.join(route['reached'])]
    for failure in route.get('primary_failures', [])[:3]:
        detail = failure.get('exception') or failure.get('result') or {}
        lines.append('  witnessed primary failure: ' + str(detail) + ' in ' + failure.get('test', ''))
    return lines

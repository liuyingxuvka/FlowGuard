"""Read-only staged-content policy over existing finished check receipts.

The jobs owner supplies the actual index-affected model set and running parts.
This module neither discovers a second dependency graph nor starts computation.
"""
from __future__ import annotations

from pathlib import Path
import re

from ..map.common import git_blob, git_run, content_digest, sha256_bytes
from ..map.common import MapError
from .decisions import decision_paths, evaluate_decision, read_decision


def index_inputs(root, paths):
    """Read exact index entries, including mode; a removed checked input is None."""
    result = {}
    for path in sorted(set(paths)):
        if not isinstance(path, str) or not path or Path(path).is_absolute() or '..' in Path(path).parts:
            raise MapError('commit_input_invalid: checked inputs must be project-relative paths')
        rows = git_run(root, 'ls-files', '--stage', '-z', '--', path).stdout.split(b'\0')
        entries = [row.partition(b'\t')[0].split() for row in rows if row.partition(b'\t')[2].decode(errors='surrogateescape') == path]
        if any(len(row) != 3 or row[2] != b'0' for row in entries):
            raise MapError(f'commit_index_unmerged: {path}')
        data = git_blob(root, ':', path)
        result[path] = None if data is None else dict(mode=entries[0][0].decode('ascii'),
                                                    sha256=(sha256_bytes(data) if entries[0][0] == b'120000' else
                                                            content_digest(Path(path), data=data, source_only=True)))
    return result


def commit_ready(root, affected, receipt, conflicts, *, running=(), decisions=None, closed=()):
    """Decide whether existing evidence covers these staged model inputs.

    A receipt's inputs MUST be captured by the computation from the bytes it
    actually read, not taken from today's index after computation. It may contain
    finished UNKNOWN/capped models. Unknown is returned visibly, never as clean.
    Unaffected old conflicts are not a block; affected unresolved ones remain so.
    """
    affected = sorted(set(affected))
    reasons, unknown = [], []
    running = set(running)
    if not affected:
        return dict(ready=True, reasons=[], unknown=[], decisions=[])
    if not isinstance(receipt, dict) or not isinstance(receipt.get('models'), dict):
        return dict(ready=False, reasons=[dict(code='running' if m in running else 'missing_result', model=m) for m in affected], unknown=[], decisions=[])
    from .parts import ENGINE_DIGEST
    if receipt.get('engine') != ENGINE_DIGEST:
        reasons.append(dict(code='stale_engine'))
    for model in affected:
        if model in running:
            reasons.append(dict(code='running', model=model))
            continue
        from .codeaudit import PROJECT
        row = receipt.get('code_audit') if model == PROJECT else receipt['models'].get(model)
        if not isinstance(row, dict) or row.get('finished') is not True:
            reasons.append(dict(code='missing_finished_result', model=model))
            continue
        files = row.get('inputs')
        if not isinstance(files, dict) or not files:
            reasons.append(dict(code='missing_input_evidence', model=model))
            continue
        valid = all(value is None or isinstance(value, dict) and set(value) == {'mode', 'sha256'}
                    and value['mode'] in {'100644', '100755', '120000'} and
                    isinstance(value['sha256'], str) and re.fullmatch('[0-9a-f]{64}', value['sha256'])
                    for value in files.values())
        if not valid:
            reasons.append(dict(code='invalid_input_evidence', model=model))
            continue
        current = index_inputs(root, files)
        changed = [path for path in files if current[path] != files[path]]
        if changed:
            reasons.append(dict(code='stale_index', model=model, paths=changed))
        if model == PROJECT:
            from .codeaudit import source_files
            if row.get('test_failures'):
                reasons.append(dict(code='selected_tests_failed', model=model, tests=row['test_failures']))
            missing = [path for path in source_files(Path(root)) if path not in files and git_blob(root, ':', path) is not None]
            if missing:
                reasons.append(dict(code='unchecked_index_inputs', model=model, paths=missing))
        if type(row.get('unknown')) is not bool:
            reasons.append(dict(code='missing_completion_boundary', model=model))
        elif row['unknown']:
            unknown.append(model)
    applied = []
    for entry in closed:
        proof = entry.get('closure', {})
        if entry.get('model') not in affected or proof.get('kind') != 'requirement_changed':
            continue
        from . import history
        from .descriptors import input_evidence
        try:
            resolution = history.resolution_current(root, entry, proof.get('resolution'))
            row = receipt['models'].get(entry['model'], {})
            current = row.get('observation')
            if current is None:
                raise MapError('requirement_receipt_stale: the current result has no model observation')
            comparison = history.assess(entry, current, root=root)
            if comparison['outcome'] != 'requirement_changed':
                raise MapError('requirement_receipt_stale: the current result does not establish the replacement requirement')
            paths = resolution['paths']
            staged = index_inputs(root, paths)
            actual = input_evidence(root, paths)
            different = [path for path in paths if staged[path] != actual[path] or staged[path] is None
                         or staged[path]['mode'] not in {'100644','100755'}]
            if different:
                reasons.append(dict(code='requirement_evidence_not_staged', model=entry['model'],
                                    conflict=entry['id'], paths=different))
        except MapError as error:
            reasons.append(dict(code='invalid_requirement_resolution', model=entry['model'],
                                conflict=entry['id'], why=str(error)))
    for conflict in conflicts:
        if conflict.get('model') not in affected:
            continue
        permitted = False
        for identifier in (decisions or {}).get(conflict['id'], ()):
            try:
                decision = evaluate_decision(root, conflict, identifier)
            except MapError as error:
                reasons.append(dict(code='invalid_decision', model=conflict['model'], conflict=conflict['id'], why=str(error)))
                continue
            authority = index_inputs(root, decision_paths(read_decision(root, identifier)))
            missing = [path for path, value in authority.items() if value is None]
            wrong_kind = [path for path, value in authority.items() if value is not None and value['mode'] not in {'100644', '100755'}]
            if wrong_kind:
                reasons.append(dict(code='decision_index_kind', model=conflict['model'],
                                    conflict=conflict['id'], paths=wrong_kind))
                continue
            if missing:
                reasons.append(dict(code='decision_not_staged', model=conflict['model'],
                                    conflict=conflict['id'], paths=missing))
                continue
            applied.append(decision)
            permitted |= decision['commit_allowed']
        if not permitted:
            reasons.append(dict(code='unresolved_conflict', model=conflict['model'], conflict=conflict['id']))
    return dict(ready=not reasons, reasons=reasons, unknown=unknown, decisions=applied)

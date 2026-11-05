"""The public release owner: flow checks, explicitly requested suite, original-byte snapshot."""
from __future__ import annotations

import io
from pathlib import Path
import subprocess
import sys

from ..map.common import MapError, print_verdict


class ReleaseRuntimeError(RuntimeError):
    """The release could not form a check result."""


def _flow(root, as_json, codes):
    from .cli import internal_text, release
    from .project import ProjectError, model_files, read_conflicts, require_current_format
    from .jobs import require_supported

    try:
        require_current_format(root)
        prior = read_conflicts(root)
        declared = model_files(root)
        if declared:
            require_supported()
        if not declared and not prior:
            codes.append(dict(level='info', code='no_flow_models', subject='flow'))
        if not (root / '.flowguard').is_dir():
            if not as_json:
                print('flow: no flow models or recorded code checks')
            return True
        report = io.StringIO()
        observations = []
        def checked(data):
            observations.append(data)
            codes.extend(dict(level='warn', code='mutant_survives', subject=row['id'])
                         for row in data['warnings'] if row['kind'] == 'MUTANT SURVIVES')
            codes.extend(dict(level='error', code='setting_proposal', subject=row['model'])
                         for row in data['setting_proposals'])
        passed = release(root, out=report, err=sys.stderr, on_result=checked)
        if passed and any(not data['complete'] for data in observations):
            codes.append(dict(level='warn', code='flow_unknown', subject='recorded check scope'))
    except ProjectError as error:
        raise ReleaseRuntimeError(f'flow checks: {error}') from error
    except BrokenPipeError:
        raise
    except Exception as error:
        raise ReleaseRuntimeError(f'flow checks: {internal_text(error)}') from error
    if not as_json or not passed:
        for line in report.getvalue().splitlines():
            print('flow: ' + line, file=sys.stderr if as_json else sys.stdout)
    if not passed:
        codes.append(dict(level='error', code='flow_checks', subject='flow'))
    return passed


def run(root, *, shards=None, as_json=False):
    """One release route; pytest has exactly the existing shard-runner owner."""
    root = Path(root).resolve()
    codes = []
    try:
        passed = _flow(root, as_json, codes)
    except ReleaseRuntimeError as error:
        print(f'error: {error}', file=sys.stderr)
        if as_json:
            print_verdict('release', 2, [dict(level='error', code='runtime_error', subject='flow')])
        return 2
    suite_state = 'not requested' if shards is None else 'not run'
    if passed and shards is not None:
        suite = subprocess.run([sys.executable, '-m', 'flowguard.pytest_shards_cli',
                                '--root', str(root), '--shards', str(shards)],
                               capture_output=True, text=True)
        for line in suite.stdout.splitlines():
            print('suite: ' + line, file=sys.stderr if as_json else sys.stdout)
        for line in suite.stderr.splitlines():
            print('suite: ' + line, file=sys.stderr)
        passed = suite.returncode == 0
        suite_state = 'passed' if passed else 'failed'
        if not passed:
            codes.append(dict(level='error', code='suite_failed', subject='suite'))
    elif shards is not None and not as_json:
        print('suite: not run (repair the flow-check failures first)')
    if passed:
        from ..map.records import save_release_snapshot
        try:
            # This owner preserves independently known original digests. It never
            # creates an original-byte baseline from unverified current contents.
            save_release_snapshot(root)
        except (OSError, MapError) as error:
            passed = False
            codes.append(dict(level='error', code='release_snapshot_failed', subject='release'))
            print(f'error: {error}', file=sys.stderr)
    code = 0 if passed else 1
    if as_json:
        flow_scope = ('none declared' if any(row['code'] == 'no_flow_models' for row in codes) else
                      'failed' if any(row['code'] == 'flow_checks' for row in codes) else
                      'finished UNKNOWN' if any(row['code'] == 'flow_unknown' for row in codes) else 'passed')
        print_verdict('release', code, codes, scope={'flow_checks': flow_scope, 'suite': suite_state})
    else:
        verdict = ('MODELS PASS' if shards is None else 'PASS') if passed else 'FAIL'
        details = []
        if any(row['code'] == 'flow_unknown' for row in codes):
            details.append('flow check finished UNKNOWN')
        survivors = sum(row['code'] == 'mutant_survives' for row in codes)
        if survivors:
            details.append(f'{survivors} deliberate breakages not caught')
        if shards is None:
            details.append('tests not run (use --shards N for the whole suite)')
        print(f'release: {verdict}' + ''.join('; ' + detail for detail in details))
    return code

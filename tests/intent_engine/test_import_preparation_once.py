"""Import preparation is done once per test session on the rule path.

4.0 repeated the whole preparation (every loaded module classified again with
project_code) for each rule observation: 14 calls and 1.84 s in a small demo.
Later preparations in the same session now only look at modules that are new;
changed project sources are still detected every time.
"""
from pathlib import Path
import json
import subprocess
import sys
import textwrap


SOURCE = Path(__file__).resolve().parents[2]

COUNTER = '''import json, os, sys
from flowguard.intent import imports

calls, current = [], [None]
real = imports.project_code


def counted(filename, root):
    frame = sys._getframe(1)
    while frame is not None:
        if frame.f_code is imports.prepare.__code__:
            if frame is not current[0]:
                current[0] = frame  # Holding the frame keeps one invocation's identity unique.
                calls.append(0)
            calls[-1] += 1
            break
        frame = frame.f_back
    return real(filename, root)


imports.project_code = counted


def pytest_unconfigure(config):
    with open(os.environ['FG_COUNT'], 'w') as handle:
        json.dump(calls, handle)
'''


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                           *arguments], check=True, capture_output=True, text=True, timeout=60).stdout


def project(root):
    (root / 'tests/intent').mkdir(parents=True)
    (root / 'policy.py').write_text(textwrap.dedent('''
        # flowguard: sensor FEE(days: day, member: bool) -> fee: int
        def fee(days: int, member: bool) -> int:
            if days <= 2:
                return 0
            return (days - 2) * 3 // (2 if member else 1)
    ''').lstrip())
    (root / 'tests/test_policy.py').write_text('from policy import fee\ndef test_fee(): assert fee(5, False) == 9\n')
    (root / 'tests/intent/fees.py').write_text(textwrap.dedent('''
        from flowguard.intent import rule, row
        @rule('FEE', decides='late fee', fields={'days': int, 'member': bool}, anchor='FEE', source='assumed: 3 per day')
        def FEE(days, member):
            if days <= 2:
                return 0
            return (days - 2) * 3 // (2 if member else 1)
        FEE.rows(row(days=3, member=True, expect=1, why='half of 3 rounds down'))
    ''').lstrip())
    (root / 'tests/test_flowguard_intent.py').write_text(
        'def test_flowguard_intent(request):\n    from flowguard.intent.plugin import sentinel\n    sentinel(request.config)\n')
    # The counting plugin lives outside the project: project code may not load before verification.
    (root.parent / 'counter').mkdir()
    (root.parent / 'counter/fg_count.py').write_text(COUNTER)
    (root / '.gitignore').write_text('.flowguard/cache/\n__pycache__/\n.pytest_cache/\n')
    (root / 'pyproject.toml').write_text('[tool.flowguard]\n\n[tool.pytest.ini_options]\npythonpath = ["."]\n'
                                         'addopts = "-p flowguard.intent.plugin"\n')
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'rule baseline')
    return root


def run(root):
    counts = root / 'counts.json'
    bootstrap = ('import sys; sys.path.insert(0,sys.argv.pop(1)); sys.path.insert(0,sys.argv.pop(1)); '
                 'import pytest; raise SystemExit(pytest.main(sys.argv[1:]))')
    result = subprocess.run([sys.executable, '-c', bootstrap, str(root.parent / 'counter'), str(SOURCE), '-q', '-p', 'no:cacheprovider', '-p', 'fg_count'],
                            cwd=root, capture_output=True, text=True, timeout=300,
                            env={**__import__('os').environ, 'FG_COUNT': str(counts)})
    return result, json.loads(counts.read_text())


def test_rule_observations_reuse_one_import_preparation(tmp_path):
    root = project(tmp_path / 'rule')
    result, counts = run(root)
    assert result.returncode == 0, result.stdout + result.stderr
    assert len(counts) >= 3, f'the rule path prepares imports repeatedly: {counts}'
    first, later = counts[0], counts[1:]
    assert first > 20, counts
    # Later calls see only new modules and the digests of loaded project files.
    assert max(later) <= first // 4 and sum(later) < first, f'later preparations classified the loaded modules again: {counts}'


def test_changed_source_is_still_seen_by_a_later_preparation(tmp_path):
    (tmp_path / 'owned.py').write_text('VALUE = 3\n')
    program = '''
import sys
sys.path.insert(0, sys.argv[1])
from flowguard.intent.imports import prepare
prepare('.')
import owned
assert owned.VALUE == 3
prepare('.')
assert __import__('owned') is owned, 'an unchanged module is kept'
open('owned.py', 'w').write('VALUE = 40\\n')
prepare('.')
assert 'owned' not in sys.modules, 'a changed project module is forgotten'
import owned
assert owned.VALUE == 40
'''
    result = subprocess.run([sys.executable, '-c', program, str(SOURCE)], cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr

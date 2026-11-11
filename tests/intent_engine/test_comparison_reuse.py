"""A changed anchor's comparison is computed once and reused while its fingerprint stays the same.

Design section 5: a changed large anchor (6144 classes) was compared again by every ordinary pytest run.
The first run still computes it; a later run with the same fingerprint (FlowGuard's own code, the baseline,
the anchor's file, the bodies of the function and of the project functions it calls, the values of the
constants they read, the call's arguments) keeps the stored result. Any change of these computes it again,
and a function whose inputs the map cannot read completely (here: a file it reads) is never reused.

Each run is a real pytest process. The project's conftest can forbid the replay of one anchor: a reused
comparison never replays, a recomputed one fails that test.
"""
from pathlib import Path
import os
import sqlite3
import subprocess
import sys
import textwrap

from tests.intent_engine._cli_fixture import display_text


SOURCE = str(Path(__file__).resolve().parents[2])

TABLE = '''from pathlib import Path
from shop.helper import never

LIMIT = 10


# flowguard: sensor TABLE
def table(a: bool, b: bool, c: bool, n: int) -> bool:
    return (a and not b) or (c and n > LIMIT) or never(a)


# flowguard: sensor FILED
def filed(n: int) -> bool:
    return n > int(Path(__file__).with_name('limit.txt').read_text())
'''

CONFTEST = '''import os
from flowguard.intent import runtime


_replay = runtime.Runtime._replay_rows


def _forbidden(self, original, bound, *, owner, name, axes):
    if name in os.environ.get('FG_FORBID_REPLAY', '').split(','):
        raise AssertionError('replayed ' + name)
    return _replay(self, original, bound, owner=owner, name=name, axes=axes)


runtime.Runtime._replay_rows = _forbidden
'''


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                           *arguments], check=True, capture_output=True, text=True, timeout=30).stdout


def project(tmp_path):
    root = tmp_path / 'shop_project'
    (root / 'shop').mkdir(parents=True)
    (root / 'tests').mkdir()
    (root / 'shop/__init__.py').write_text('')
    (root / 'shop/helper.py').write_text('def never(a):\n    return False\n')
    (root / 'shop/table.py').write_text(TABLE)
    (root / 'shop/limit.txt').write_text('3\n')
    (root / 'tests/conftest.py').write_text(CONFTEST)
    (root / 'tests/test_table.py').write_text(textwrap.dedent('''
        import os
        import shop.table
        from shop.table import filed, table


        def test_table():
            shop.table.LIMIT = int(os.environ['FG_LIMIT'])      # a constant's value the source does not show
            assert table(True, False, False, 0)
            assert filed(9)
    ''').lstrip())
    (root / '.gitignore').write_text('.flowguard/cache/\n__pycache__/\n')
    (root / 'pyproject.toml').write_text('[tool.flowguard]\n\n[tool.pytest.ini_options]\npythonpath = ["."]\n'
                                         'addopts = "-p flowguard.intent.plugin"\n')
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'baseline')
    table = root / 'shop/table.py'
    table.write_text(table.read_text().replace('n > LIMIT', 'n >= LIMIT'))
    filed = root / 'shop/table.py'
    filed.write_text(filed.read_text().replace("n > int(", "n >= int("))
    return root


def pytest_run(root, *, forbid='', limit='10'):
    environment = {**os.environ, 'FG_FORBID_REPLAY': forbid, 'FG_LIMIT': limit}
    environment.pop('PYTHONDONTWRITEBYTECODE', None)
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    result = subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '-q', '-p', 'no:cacheprovider'],
                            cwd=root, capture_output=True, text=True, timeout=180, env=environment)
    return result, display_text(result)


def changes(text):
    return [line for line in text.splitlines() if line.startswith('changed: ')]


def stored(root):
    with sqlite3.connect(root / '.flowguard/cache/map.sqlite') as con:
        return con.execute('SELECT key, baseline FROM comparison').fetchall()


def test_an_unchanged_fingerprint_reuses_the_comparison_with_the_same_report(tmp_path):
    root = project(tmp_path)
    first, text = pytest_run(root)
    assert first.returncode == 0, text
    reported = changes(text)
    assert any(line.startswith('changed: TABLE') for line in reported), text
    assert len(stored(root)) == 1, 'only TABLE has a fingerprint: FILED reads a file'
    again, repeated = pytest_run(root, forbid='TABLE')
    assert again.returncode == 0, repeated
    assert changes(repeated) == reported
    assert len(stored(root)) == 1


def test_a_changed_body_callee_or_constant_value_computes_the_comparison_again(tmp_path):
    root = project(tmp_path)
    assert pytest_run(root)[0].returncode == 0
    # The value of a constant the function reads: the same source, another value set by the test.
    result, text = pytest_run(root, forbid='TABLE', limit='12')
    assert result.returncode == 1 and 'replayed TABLE' in text, text
    # The body of a project function it calls.
    assert pytest_run(root)[0].returncode == 0
    helper = root / 'shop/helper.py'
    helper.write_text(helper.read_text().replace('return False', 'return a and False'))
    result, text = pytest_run(root, forbid='TABLE')
    assert result.returncode == 1 and 'replayed TABLE' in text, text
    # Its own body.
    assert pytest_run(root)[0].returncode == 0
    table = root / 'shop/table.py'
    table.write_text(table.read_text().replace('(a and not b)', '(not b and a)'))
    result, text = pytest_run(root, forbid='TABLE')
    assert result.returncode == 1 and 'replayed TABLE' in text, text


def test_a_function_reading_a_file_is_never_reused(tmp_path):
    root = project(tmp_path)
    assert pytest_run(root)[0].returncode == 0
    result, text = pytest_run(root, forbid='FILED')
    assert result.returncode == 1 and 'replayed FILED' in text, text
    (root / 'shop/limit.txt').write_text('20\n')
    result, text = pytest_run(root)
    assert result.returncode == 1 and 'assert False' in text, text


def test_a_new_baseline_drops_the_stored_comparisons(tmp_path):
    root = project(tmp_path)
    assert pytest_run(root)[0].returncode == 0
    (old, baseline), = stored(root)
    _git(root, 'commit', '-qam', 'accept the change')
    # The first run recorded the task baseline and a commit keeps it; the next task's baseline is HEAD.
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); from flowguard.__main__ import main; raise SystemExit(main(sys.argv[1:]))'
    started = subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '--root', str(root), 'new-task'],
                             cwd=root, capture_output=True, text=True, timeout=120)
    assert started.returncode == 0, started.stdout + started.stderr
    table = root / 'shop/table.py'
    table.write_text(table.read_text().replace('(a and not b)', '(not b and a)'))
    result, text = pytest_run(root)
    assert result.returncode == 0, text
    rows = stored(root)
    assert len(rows) == 1 and rows[0][0] != old and rows[0][1] != baseline

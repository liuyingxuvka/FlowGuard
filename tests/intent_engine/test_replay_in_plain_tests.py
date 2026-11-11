"""Ordinary tests pass with the plugin as they pass without it, however the changed code they call treats
the objects it is given (round 20 review of the call-site replay guard).

Each changed function would, if replayed on the test's own objects, leave the test something other than
its one real call left: a consumed generator, extra callback events or log records, a random state moved
on, extra rows, a module counter raised, a closed connection. Recording makes no extra live calls;
post-session source-only comparisons refuse unsupported names and non-JSON context.
"""
import subprocess
import sys
import textwrap
from pathlib import Path

from tests.intent_engine._cli_fixture import display_text

SOURCE = Path(__file__).resolve().parents[2]

BASELINE = {
    'app/__init__.py': '',
    'app/vstate.py': 'COUNTER = 0\n',
    'app/dice.py': 'import random\n\n\ndef roll(bonus: int):\n    return random.randint(1, 6)\n',
    'app/lg.py': 'import logging\n\n\ndef checked(x: int):\n    return x <= 3\n',
    'app/gen.py': '# flowguard: sensor RG_GEN\ndef first(items, x: int):\n    return x <= 3\n',
    'app/ev.py': 'def notify(on_event, x: int):\n    return x <= 3\n',
    'app/db.py': 'def insert(db, x: int):\n    return x <= 3\n\n\ndef finish(db, x: int):\n    return x <= 3\n',
    'app/state.py': 'from app import vstate\n\n\ndef count(x: int):\n    return x <= 3\n',
}
CHANGED = {
    'app/dice.py': 'import random\n\n\ndef roll(bonus: int):\n    return random.randint(1, 6) + bonus\n',
    'app/lg.py': "import logging\n\n\ndef checked(x: int):\n    logging.getLogger('app').warning('checked %s', x)\n    return x <= 3\n",
    'app/gen.py': '# flowguard: sensor RG_GEN\ndef first(items, x: int):\n    next(items)\n    return x <= 3\n',
    'app/ev.py': 'def notify(on_event, x: int):\n    on_event(x)\n    return x <= 3\n',
    'app/db.py': ('def insert(db, x: int):\n    db.set_authorizer(None)\n    db.execute("INSERT INTO t VALUES (1)")\n'
                  '    db.commit()\n    return x <= 3\n\n\ndef finish(db, x: int):\n'
                  '    n = db.execute("SELECT count(*) FROM t").fetchone()[0]\n    db.close()\n    return x <= 3\n'),
    'app/state.py': 'from app import vstate\n\n\ndef count(x: int):\n    vstate.COUNTER += 1\n    return x <= 3\n',
}
TESTS = textwrap.dedent('''
    import logging
    import random
    import sqlite3

    from app import vstate
    from app.db import finish, insert
    from app.dice import roll
    from app.ev import notify
    from app.gen import first
    from app.lg import checked
    from app.state import count


    def test_a_seeded_roll_is_reproducible():
        random.seed(3)
        expected = 1 + random.randint(1, 6)
        random.seed(3)
        assert roll(1) == expected


    def test_one_warning(caplog):
        caplog.set_level(logging.WARNING)
        assert checked(1) is True
        assert [record.getMessage() for record in caplog.records] == ['checked 1']


    def test_one_item_is_consumed():
        items = (i for i in range(100))
        assert first(items, 1) is True
        assert next(items) == 1


    def test_one_event():
        events = []
        assert notify(events.append, 1) is True
        assert events == [1]


    def test_one_row(tmp_path):
        db = sqlite3.connect(tmp_path / 'x.db')
        db.execute('CREATE TABLE t(n)')
        db.commit()
        assert insert(db, 1) is True
        assert db.execute('SELECT count(*) FROM t').fetchone()[0] == 1


    def test_the_connection_is_open_for_the_real_call():
        db = sqlite3.connect(':memory:')
        db.execute('CREATE TABLE t(n)')
        assert finish(db, 1) is True


    def test_one_count():
        assert count(1) is True
        assert vstate.COUNTER == 1
''')


def _git(root, *arguments):
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', *arguments],
                   check=True, capture_output=True, timeout=60)


def _write(root, files):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')


def test_changed_code_leaves_ordinary_tests_as_their_real_calls_leave_them(tmp_path):
    root = tmp_path / 'plain'
    _write(root, {**BASELINE, 'tests/__init__.py': '', 'tests/test_app.py': TESTS,
                  '.gitignore': '.flowguard/cache/\n__pycache__/\n',
                  'pyproject.toml': '[tool.flowguard]\n\n[tool.pytest.ini_options]\npythonpath = ["."]\n'
                                    'testpaths = ["tests"]\naddopts = "-p flowguard.intent.plugin"\n'})
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'baseline')
    _write(root, CHANGED)
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    outputs = {}
    for label, options in (('plugin', []), ('plain', ['-o', 'addopts='])):
        result = subprocess.run([sys.executable, '-c', bootstrap, str(SOURCE), '-q', '-p', 'no:cacheprovider', *options],
                                cwd=root, capture_output=True, text=True, encoding='utf-8', timeout=300)
        outputs[label] = text = display_text(result)
        assert result.returncode == 0, text
        assert '7 passed' in text and 'failed' not in text, text
    # With the plugin the changed points are reported as unverified, never as agreement.
    assert 'FlowGuard（since task start' in outputs['plugin'] and 'unverified' in outputs['plugin'], outputs['plugin']

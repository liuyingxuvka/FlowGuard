"""With a working-tree change, only observation points are monitored.

4.0 switched on process-wide PY_START/PY_RESUME monitoring as soon as any
project file changed: anchor captures and event paths used dynamic predicates,
so every function call of every test went through the observer (a 400 000-call
test went from 0.03 s to 1.01 s). Observation points are now the code objects of
anchored functions (and functions included for comparison), monitored with
local events; an unrelated hot loop is not seen at all.

Run this file directly to print the measured call-phase times::

    python tests/intent_engine/test_hot_observation_scope.py
"""
from pathlib import Path
import json
import os
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import textwrap


SOURCE = Path(__file__).resolve().parents[2]

HOT = '''def step(x):
    return x + 1


def work(n):
    total = 0
    for _ in range(n):
        total = step(total)
    return total
'''

POLICY = '''from shop.settings import GRACE


# flowguard: sensor STANDING(days: day) -> allowed: bool
def standing(days: int) -> bool:
    return days <= GRACE


# flowguard: event SAVED(x: int)
def save(x: int) -> int:
    return x


# flowguard: event PUBLISHED(x: int)
def publish(x: int) -> int:
    return save(x) + 1
'''

TEST_HOT = '''import json, os, sys, time
from shop.hot import step, work


def test_hot():
    started = time.perf_counter()
    assert work(400000) == 400000
    elapsed = time.perf_counter() - started
    state = dict(seconds=elapsed)
    monitoring = getattr(sys, 'monitoring', None)
    if monitoring is not None:
        tool = next((n for n in range(6) if monitoring.get_tool(n) == 'flowguard-runtime'), None)
        state['tool'] = tool
        if tool is not None:
            state['global'] = monitoring.get_events(tool)
            state['start'] = monitoring.events.PY_START | monitoring.events.PY_RESUME
            state['local_step'] = monitoring.get_local_events(tool, step.__code__)
    else:
        state['trace'] = sys.gettrace() is not None
    with open(os.environ['HOT_RESULT'], 'w') as handle:
        json.dump(state, handle)
'''

TEST_POLICY = '''from shop.policy import publish, standing


def test_publish():
    assert publish(2) == 3


def test_standing():
    assert standing(2) is True
'''


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                           *arguments], check=True, capture_output=True, text=True, timeout=60).stdout


def project(root):
    (root / 'shop').mkdir(parents=True)
    (root / 'tests').mkdir()
    (root / 'shop/__init__.py').write_text('')
    (root / 'shop/settings.py').write_text('GRACE = 3\n')
    (root / 'shop/hot.py').write_text(HOT)
    (root / 'shop/policy.py').write_text(POLICY)
    (root / 'tests/test_hot.py').write_text(TEST_HOT)
    (root / 'tests/test_policy.py').write_text(TEST_POLICY)
    (root / '.gitignore').write_text('.flowguard/cache/\n__pycache__/\n.pytest_cache/\n')
    (root / 'pyproject.toml').write_text('[tool.flowguard]\n\n[tool.pytest.ini_options]\npythonpath = ["."]\n'
                                         'addopts = "-p flowguard.intent.plugin"\n')
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'hot loop baseline')
    return root


def run(root, *, plugin=True):
    result = root / 'hot.json'
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    options = [] if plugin else ['-o', 'addopts=']
    completed = subprocess.run([sys.executable, '-c', bootstrap, str(SOURCE), '-q', '-p', 'no:cacheprovider', *options],
                               cwd=root, capture_output=True, text=True, timeout=300, env=dict(os.environ, HOT_RESULT=str(result)))
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(result.read_text()), completed


def change(root):
    (root / 'shop/settings.py').write_text('GRACE = 4\n')


def test_unrelated_hot_loop_is_not_monitored_when_the_tree_has_a_change(tmp_path):
    root = project(tmp_path / 'hot')
    change(root)
    state, completed = run(root)
    if 'tool' in state:
        assert state['tool'] is not None, 'the anchored functions are observed with the shared monitoring tool'
        assert not state['global'] & state['start'], f'process-wide call monitoring is on: {state}'
        assert state['local_step'] == 0, f'an unanchored unchanged function is monitored: {state}'
    # Observation points still work: the changed constant is reported at its sensor
    # and the event path of the ordinary test is recorded.
    assert 'STANDING' in completed.stdout, completed.stdout
    with sqlite3.connect(root / '.flowguard/cache/map.sqlite') as connection:
        payload = json.loads(connection.execute("SELECT v FROM meta WHERE k='runtime_observations'").fetchone()[0])
    entered = [event['anchor'] for event in payload['events'] if event['phase'] == 'call']
    assert 'PUBLISHED' in entered and 'SAVED' in entered, payload['events']


def measure(repeat=5):
    """Median call-phase seconds of the 400 000-call test: no plugin, no change, one unrelated change."""
    with tempfile.TemporaryDirectory() as folder:
        root = project(Path(folder) / 'hot')
        numbers = {}
        for label, plugin, changed in (('without plugin', False, False), ('plugin, no change', True, False),
                                       ('plugin, unrelated change', True, True)):
            if changed:
                change(root)
            numbers[label] = round(statistics.median(run(root, plugin=plugin)[0]['seconds'] for _ in range(repeat)), 4)
        return numbers


if __name__ == '__main__':
    print(json.dumps(dict(python=sys.version.split()[0], **measure()), ensure_ascii=False))

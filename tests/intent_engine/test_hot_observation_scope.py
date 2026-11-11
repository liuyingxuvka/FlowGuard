"""With a working-tree change, only observation points are monitored.

4.0 switched on process-wide PY_START/PY_RESUME monitoring as soon as any
project file changed: anchor captures and event paths used dynamic predicates,
so every function call of every test went through the observer (a 400 000-call
test went from 0.03 s to 1.01 s). Observation points are now the code objects of
anchored functions (and functions included for comparison), monitored with
local events; an unrelated hot loop is not seen at all.

The sealed environment's audit hook is installed only when a comparison runs after the tests (4.5), so
no test's loop runs under it; plain calls raise no audit event in any case.

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
    started, used = time.perf_counter(), time.thread_time()
    assert work(400000) == 400000
    elapsed, cpu = time.perf_counter() - started, time.thread_time() - used
    warm = []                           # the same loop again: a load spike on a shared machine hits one run, not all
    for _ in range(5):
        again = time.thread_time()
        work(400000)
        warm.append(time.thread_time() - again)
    events, counting = [], [True]       # counted in a separate short loop, so counting costs the timing nothing
    sys.addaudithook(lambda event, args: events.append(event) if counting[0] else None)
    assert work(1000) == 1000
    counting[0] = False
    runtime = sys.modules.get('flowguard.intent.runtime')
    state = dict(seconds=elapsed, cpu=cpu, warm=min(warm), audit_events=len(events), hooked=bool(runtime and runtime._HOOKED))
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

TEST_REPLAY = '''from shop.policy import standing


def test_a_replay_first():
    assert standing(1) is True
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
    (root / 'tests/test_a_replay.py').write_text(TEST_REPLAY)    # runs before test_hot.py
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
    # No comparison runs during the tests, so the sealed audit hook is not installed while the loop runs;
    # the loop's 1 001 calls raised (almost) no audit event. On Python 3.11 the trace fallback reads f_code
    # (an audit event) only for a call that starts on the first line of an observed function.
    assert state['hooked'] is False and state['audit_events'] < 10, state
    # Observation points still work: the event path of the ordinary test is recorded. The changed constant
    # lives in another module that the sealed environment does not load, and `standing` itself did not
    # change, so no change is claimed for it (4.5: before/after only for the changed functions).
    assert 'changed:' not in completed.stdout, completed.stdout
    with sqlite3.connect(root / '.flowguard/cache/map.sqlite') as connection:
        payload = json.loads(connection.execute("SELECT v FROM meta WHERE k='runtime_observations'").fetchone()[0])
    entered = [event['anchor'] for event in payload['events'] if event['phase'] == 'call']
    assert 'PUBLISHED' in entered and 'SAVED' in entered, payload['events']


def measure(repeat=5):
    """Median call-phase seconds of the 400 000-call test: no plugin, no change, and one unrelated change
    (with which an earlier test's replay has installed the audit hook before the loop runs). The loop
    takes about 0.02 s, so one wall-clock reading moves by tens of percent on a loaded machine: the
    thread CPU time of the first loop and the fastest of five more loops are printed beside it."""
    with tempfile.TemporaryDirectory() as folder:
        root = project(Path(folder) / 'hot')
        numbers = {}
        for label, plugin, changed in (('without plugin', False, False), ('plugin, no change', True, False),
                                       ('plugin, unrelated change, audit hook installed', True, True)):
            if changed:
                change(root)
            states = [run(root, plugin=plugin)[0] for _ in range(repeat)]
            numbers[label] = round(statistics.median(state['seconds'] for state in states), 4)
            numbers[label + ' (cpu, warm)'] = (round(statistics.median(state['cpu'] for state in states), 4),
                                               round(statistics.median(state['warm'] for state in states), 4))
            if changed:
                numbers['audit hook installed'] = all(state['hooked'] for state in states)
                numbers['audit events in the loop'] = max(state['audit_events'] for state in states)
        base = numbers['without plugin']
        numbers['extra with the hook'] = f"{100 * (numbers['plugin, unrelated change, audit hook installed'] - base) / base:+.1f}%"
        cpu, warm = numbers['without plugin (cpu, warm)']
        hooked_cpu, hooked_warm = numbers['plugin, unrelated change, audit hook installed (cpu, warm)']
        numbers['extra with the hook (cpu, warm)'] = f"{100 * (hooked_cpu - cpu) / cpu:+.1f}%, {100 * (hooked_warm - warm) / warm:+.1f}%"
        return numbers


if __name__ == '__main__':
    print(json.dumps(dict(python=sys.version.split()[0], **measure()), ensure_ascii=False))

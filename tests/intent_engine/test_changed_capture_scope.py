"""A source change does not widen what the anchor capture keeps (design 6.5).

Up to stage 2 a working-tree change switched the Flow models' test-entry filter off, so that the event
path of a changed run could be run again on the old code. That rerun is gone (4.3 records real paths
only), but the switch stayed: with any source change every call of every anchored function was kept,
with its arguments, and FlowGuard's own suite ended in `sqlite3.DataError: string or blob too big` while
saving them (or was killed for memory). A changed run now keeps what an unchanged run keeps: the events
the Flow models read.
"""
from pathlib import Path
import json
import sqlite3
import subprocess
import sys
import textwrap


SOURCE = str(Path(__file__).resolve().parents[2])

FILES = {
    'shop/__init__.py': '',
    'shop/settings.py': 'GRACE = 3\n',
    'shop/policy.py': '''
        # flowguard: event PUBLISHED(x: int)
        def publish(x: int) -> int:
            return x + 1


        # flowguard: event NOTED(text: str)
        def note(text: str) -> int:
            return len(text)
    ''',
    'tests/test_shop.py': '''
        from shop.policy import note, publish


        # flowguard: event RELEASE_CASE(x: int)
        def release_case(x):
            return publish(x)


        def test_release():
            assert release_case(2) == 3


        def test_notes():
            for number in range(400):
                assert note('x' * 1000 + str(number)) > 1000
    ''',
    'tests/intent/flows.py': '''
        from flowguard.intent import flow, Node
        flow('RELEASE', source='assumed: a release publishes once',
             nodes=[Node('case', 'RELEASE_CASE'), Node('published', 'PUBLISHED', phase='return'),
                    Node('done', 'RELEASE_CASE', phase='return')],
             edges=[('case', 'published'), ('published', 'done')])
    ''',
}


def _git(root, *arguments):
    return subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                           *arguments], check=True, capture_output=True, text=True, timeout=60).stdout


def _project(root):
    for name, text in FILES.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip(), encoding='utf-8')
    (root / '.gitignore').write_text('.flowguard/cache/\n__pycache__/\n.pytest_cache/\n')
    (root / 'pyproject.toml').write_text('[tool.flowguard]\n\n[tool.pytest.ini_options]\npythonpath = ["."]\n'
                                         'testpaths = ["tests"]\naddopts = "-p flowguard.intent.plugin"\n')
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', '.')
    _git(root, 'commit', '-qm', 'baseline')
    return root


def _saved(root):
    bootstrap = 'import sys; sys.path.insert(0,sys.argv.pop(1)); import pytest; raise SystemExit(pytest.main(sys.argv[1:]))'
    result = subprocess.run([sys.executable, '-c', bootstrap, SOURCE, '-q', '-p', 'no:cacheprovider'],
                            cwd=root, capture_output=True, text=True, timeout=180)
    assert '2 passed' in result.stdout, result.stdout + result.stderr
    with sqlite3.connect(root / '.flowguard/cache/map.sqlite') as connection:
        text = connection.execute("SELECT v FROM meta WHERE k='runtime_observations'").fetchone()[0]
    return json.loads(text)['events'], len(text.encode())


def test_a_changed_run_keeps_only_the_events_its_flows_read(tmp_path):
    root = _project(tmp_path / 'shop')
    unchanged, unchanged_size = _saved(root)
    (root / 'shop/settings.py').write_text('GRACE = 4\n')        # a one-line source change
    changed, changed_size = _saved(root)
    # The release case is the Flow's test entry: its own call and the publish inside it are kept, the
    # 400 notes outside every Flow are not, with or without a change.
    for events in (unchanged, changed):
        assert sorted((event['anchor'], event['phase']) for event in events) == [
            ('PUBLISHED', 'call'), ('PUBLISHED', 'return'), ('RELEASE_CASE', 'call'), ('RELEASE_CASE', 'return')], events
    # Bounded by what the Flows read, not by the number of anchored calls: 800 note events with their
    # 1 000-character arguments alone would be over 800 000 bytes.
    assert changed_size < 20_000 and abs(changed_size - unchanged_size) < 2_000, (unchanged_size, changed_size)

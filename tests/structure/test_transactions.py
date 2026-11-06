"""A map is one committed source snapshot, also after interruption or concurrent access."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from flowguard.map.common import MapError
from flowguard.structure import build, store

PACKAGE_ROOT = str(Path(__file__).resolve().parents[2])


def snapshot(path):
    with sqlite3.connect(path) as con:
        assert con.execute('PRAGMA quick_check').fetchall() == [('ok',)]
        return (con.execute("SELECT v FROM meta WHERE k='build'").fetchone()[0],
                con.execute('SELECT path,sha FROM file ORDER BY path').fetchall(),
                con.execute('SELECT id,fp FROM node ORDER BY id').fetchall())


def project(tmp_path, count=1):
    root = tmp_path / 'subject'
    root.mkdir()
    for name in ('a', 'b'):
        (root / (name + '.py')).write_text(''.join(
            f'def f{i}(value):\n    return {{"value": value + 1, "row": {i}}}\n' for i in range(count)))
    return root, tmp_path / 'map.sqlite'


def changed(root):
    for path in root.glob('*.py'):
        path.write_text(path.read_text().replace('value + 1', 'value + 2'))


def test_unchanged_reopen_and_write_exception_preserve_the_last_complete_map(tmp_path, monkeypatch):
    root, path = project(tmp_path)
    with closing(build(root, path)) as graph:
        assert graph.con.execute('PRAGMA journal_mode').fetchone()[0] == 'delete'
        assert graph.con.execute('PRAGMA synchronous').fetchone()[0] == 2
    before = snapshot(path)
    with closing(build(root, path)) as graph:
        assert not graph.stats['changed']
    assert snapshot(path) == before
    changed(root)
    original = store._link_file
    def broken(*args):
        original(*args)
        raise RuntimeError('stop after source and edges were written')
    with monkeypatch.context() as patch:
        patch.setattr(store, '_link_file', broken)
        with pytest.raises(RuntimeError, match='stop after source'):
            build(root, path)
    assert snapshot(path) == before
    with closing(build(root, path)) as graph:
        assert graph.stats['parsed'] == 2
    assert snapshot(path) != before


def start(root, path, pause):
    code = f'''import sys,json
sys.path.insert(0,{PACKAGE_ROOT!r})
from flowguard.structure import build,store
from pathlib import Path
original=store._link_file
paused=False
def pending(*args):
    global paused
    original(*args)
    if not paused:
        paused=True
        print("WRITTEN",flush=True)
        sys.stdin.read(1)
if {pause!r}:
    store._link_file=pending
else:
    print("STARTING",flush=True)
graph=build(Path({str(root)!r}),Path({str(path)!r}),workers=1)
print(json.dumps(graph.stats),flush=True)
graph.close()
'''
    return subprocess.Popen([sys.executable, '-u', '-c', code], cwd=root,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def finish(child):
    if child.poll() is None:
        child.kill()
    child.communicate(timeout=10)


def test_terminated_writer_rolls_back_before_the_next_process_reads(tmp_path):
    # A nontrivial two-file map exercises interrupted writes. State equality,
    # rather than assumptions about a platform's page-cache spill, is the contract.
    root, path = project(tmp_path, count=2400)
    with closing(build(root, path, workers=1)):
        pass
    before = snapshot(path)
    changed(root)
    child = start(root, path, True)
    try:
        assert child.stdout.readline().strip() == 'WRITTEN'
        child.kill()
        child.communicate(timeout=10)
        assert snapshot(path) == before
        with closing(build(root, path, workers=1)) as graph:
            assert graph.stats['parsed'] == 2
        assert snapshot(path) != before
    finally:
        finish(child)


def test_two_processes_observe_only_complete_builds(tmp_path):
    root, path = project(tmp_path)
    with closing(build(root, path)):
        pass
    before = snapshot(path)
    changed(root)
    first = start(root, path, True)
    second = None
    try:
        assert first.stdout.readline().strip() == 'WRITTEN'
        # An ordinary reader sees the previous committed snapshot during a write.
        assert snapshot(path) == before
        second = start(root, path, False)
        assert second.stdout.readline().strip() == 'STARTING'
        first_out, first_err = first.communicate('x', timeout=15)
        second_out, second_err = second.communicate(timeout=15)
        assert first.returncode == 0, first_err
        assert second.returncode == 0, second_err
        first_stats = json.loads(first_out)
        second_stats = json.loads(second_out)
        assert first_stats['changed']
        assert not second_stats['changed']
        assert first_stats['build'] == second_stats['build']
        assert snapshot(path) != before
    finally:
        finish(first)
        if second is not None:
            finish(second)


def test_corrupt_database_is_an_error_not_an_empty_success(tmp_path):
    root, path = project(tmp_path)
    path.write_bytes(b'this is not a SQLite database')
    with pytest.raises(MapError, match='no cache result was accepted'):
        build(root, path)
    assert path.read_bytes() == b'this is not a SQLite database'

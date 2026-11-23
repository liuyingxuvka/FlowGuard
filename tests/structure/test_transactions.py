"""A map is one committed source snapshot, also after interruption or concurrent access."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

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


# ---- one run waits for another's write, never for its parse (R85; Planning Tool ran its web/ and api/ checks in
# parallel and one ended `database is locked` with no result) ----------------------------------------------------

def tree(folder, count=1):
    """`project` under its own folder, so two trees map to the same relative paths."""
    folder.mkdir()
    return project(folder, count)


def saved_again(root):
    for path in root.glob('*.py'):
        path.write_text(path.read_text().replace('value + 2', 'value + 3'))


def contents(path):
    """Every row of every table of a map, the clock time of its last build aside."""
    with closing(sqlite3.connect(path)) as con:
        tables = [name for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {table: sorted(con.execute(f'SELECT * FROM "{table}"' + (" WHERE k != 'built_at'" if table == 'meta' else ''))
                              .fetchall(), key=repr) for table in tables}


def parsing(root, path):
    """A build in another process that stops in its first parse (it prints PARSING) until a line arrives on stdin."""
    code = f'''import sys,json
sys.path.insert(0,{PACKAGE_ROOT!r})
from flowguard.structure import store
from pathlib import Path
original=store.extract_all
paused=False
def pausing(root, tasks, **options):
    global paused
    if tasks and not paused:
        paused=True
        print("PARSING",flush=True)
        sys.stdin.readline()
    return original(root, tasks, **options)
store.extract_all=pausing
print(json.dumps(store.build(Path({str(root)!r}),Path({str(path)!r}),workers=1)),flush=True)
'''
    return subprocess.Popen([sys.executable, '-u', '-c', code], cwd=root,
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def holding(path, mode, seconds):
    """Another process holding the cache's lock: IMMEDIATE as a build's write holds it, EXCLUSIVE as its commit does."""
    code = f'''import sqlite3,time
con=sqlite3.connect({str(path)!r},isolation_level=None)
con.execute("BEGIN {mode}")
print("HELD",flush=True)
time.sleep({seconds})
con.execute("ROLLBACK")
'''
    child = subprocess.Popen([sys.executable, '-u', '-c', code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert child.stdout.readline().strip() == 'HELD', child.stderr.read()
    return child


def test_another_run_writes_the_cache_while_a_build_parses(tmp_path):
    root, path = project(tmp_path)
    with closing(build(root, path)):
        pass
    changed(root)
    child = parsing(root, path)
    try:
        assert child.stdout.readline().strip() == 'PARSING'
        with closing(sqlite3.connect(path, timeout=1)) as con, con:
            con.execute('BEGIN IMMEDIATE')       # what another run's build or its last lines take
            con.execute("INSERT OR REPLACE INTO meta VALUES('other_run', 'written')")
        out, err = child.communicate('go\n', timeout=30)
        assert child.returncode == 0, err
        stats = json.loads(out)
        assert stats['changed'] and stats['parsed'] == 2
    finally:
        finish(child)
    with closing(sqlite3.connect(path)) as con:
        assert con.execute("SELECT v FROM meta WHERE k='other_run'").fetchone() == ('written',)


def test_opening_the_cache_and_an_unchanged_build_take_no_write_lock(tmp_path):
    root, path = project(tmp_path)
    with closing(build(root, path)):
        pass
    holder = holding(path, 'IMMEDIATE', 4)        # another run's build is writing
    try:
        started = time.perf_counter()
        store.connect(path).close()
        with closing(build(root, path)) as graph:
            assert not graph.stats['changed']
        assert time.perf_counter() - started < 2
    finally:
        holder.kill()
        holder.communicate(timeout=30)


def test_two_builds_of_one_change_give_the_map_of_one_serial_build(tmp_path):
    serial_root, serial_path = tree(tmp_path / 'serial')
    root, path = tree(tmp_path / 'parallel')
    for here, there in ((serial_root, serial_path), (root, path)):
        with closing(build(here, there, workers=1)):
            pass
        changed(here)
    for _ in range(2):                           # the second build of the same files finds nothing to write
        with closing(build(serial_root, serial_path, workers=1)):
            pass
    children = [parsing(root, path), parsing(root, path)]
    try:
        assert [child.stdout.readline().strip() for child in children] == ['PARSING', 'PARSING']
        results = [child.communicate('go\n', timeout=30) for child in children]
        assert [child.returncode for child in children] == [0, 0], results
        stats = [json.loads(out) for out, _ in results]
        assert sorted(item['changed'] for item in stats) == [False, True]
        assert stats[0]['build'] == stats[1]['build']
    finally:
        for child in children:
            finish(child)
    assert contents(path) == contents(serial_path)


def test_a_file_saved_while_a_build_parses_is_mapped_as_it_is_when_the_build_writes(tmp_path):
    serial_root, serial_path = tree(tmp_path / 'serial')
    root, path = tree(tmp_path / 'parallel')
    for here, there in ((serial_root, serial_path), (root, path)):
        with closing(build(here, there, workers=1)):
            pass
        changed(here)
    child = parsing(root, path)
    try:
        assert child.stdout.readline().strip() == 'PARSING'
        saved_again(root)                        # the editor saves again while the build parses the first save
        out, err = child.communicate('go\n', timeout=30)
        assert child.returncode == 0, err
        assert json.loads(out)['parsed'] == 2
    finally:
        finish(child)
    saved_again(serial_root)
    with closing(build(serial_root, serial_path, workers=1)):
        pass
    assert contents(path) == contents(serial_path)


def test_a_build_leaves_alone_what_another_run_wrote_while_it_parsed(tmp_path):
    serial_root, serial_path = tree(tmp_path / 'serial')
    root, path = tree(tmp_path / 'parallel')
    for here, there in ((serial_root, serial_path), (root, path)):
        with closing(build(here, there, workers=1)):
            pass
        changed(here)
    child = parsing(root, path)
    try:
        assert child.stdout.readline().strip() == 'PARSING'
        saved_again(root)
        with closing(build(root, path, workers=1)) as graph:   # another run maps the newer save and commits first
            assert graph.stats['changed']
        out, err = child.communicate('go\n', timeout=30)
        assert child.returncode == 0, err
        assert json.loads(out)['changed'] is False
    finally:
        finish(child)
    saved_again(serial_root)
    with closing(build(serial_root, serial_path, workers=1)):
        pass
    assert contents(path) == contents(serial_path)


def test_a_write_that_waits_for_another_run_says_so_once(tmp_path, monkeypatch, capsys):
    from flowguard.map import common
    root, path = project(tmp_path)
    with closing(build(root, path)):
        pass
    assert capsys.readouterr().err == ''          # nothing to wait for: nothing said
    monkeypatch.setattr(common, 'CACHE_NOTICE', 0.5)
    changed(root)
    holder = holding(path, 'IMMEDIATE', 2)
    try:
        with closing(build(root, path)) as graph:
            assert graph.stats['changed'] and graph.stats['parsed'] == 2
    finally:
        holder.communicate(timeout=30)
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 1 and lines[0].startswith('flowguard: waiting for '), lines
    shown, _, rest = lines[0].removeprefix('flowguard: waiting for ').partition(' (')
    assert Path(shown).name == 'map.sqlite' and Path(shown).samefile(path), lines
    assert rest == 'another FlowGuard run is writing it; 0.5 s so far, at most 30 s)'


def fixture_packages(root):
    """Two packages of one repository, as Planning Tool's web/ and api/, with a recorded ledger and one committed
    baseline; then each package gains a handler the ledger does not list (one red line each)."""
    root.mkdir()
    for package in ('web', 'api'):
        (root / package / 'src').mkdir(parents=True)
        (root / package / 'package.json').write_text(f'{{"name":"{package}","private":true,"type":"module"}}\n')
        for i in range(1, 4):
            (root / package / 'src' / f'm{i}.ts').write_text(
                f'export function label{i}(name: string): string {{\n  return name.trim() + ":{i}";\n}}\n')
    (root / '.flowguard').mkdir()
    (root / '.flowguard' / 'ledger.toml').write_text('# ledger\n')
    (root / '.gitignore').write_text('.flowguard/cache/\n')
    for command in (['init', '-q'], ['add', '-A'], ['-c', 'user.email=t@t', '-c', 'user.name=t', 'commit', '-qm', 'two packages']):
        subprocess.run(['git', '-C', str(root), *command], check=True, capture_output=True)
    assert cli(root, 'check', '--static').returncode == 0          # the map and the task baseline exist
    for package in ('web', 'api'):
        (root / package / 'src' / 'm1.ts').write_text(
            'export function label1(name: string): string {\n  try {\n    return name.trim() + ":1";\n'
            '  } catch {\n    return "";\n  }\n}\n')


def cli(root, *argv, module='flowguard', slow=None):
    """`python -m flowguard ARGV` in `root`; with `slow` (parse seconds, lock timeout seconds) its parse sleeps and
    every cache connection waits at most that long: a first build of a large project parses longer than a lock wait
    lasts, here scaled down."""
    code = f'''import runpy,sqlite3,sys,time
sys.path.insert(0,{PACKAGE_ROOT!r})
slow={slow!r}
if slow:
    connect=sqlite3.connect
    def scaled(*args,**options):
        options['timeout']=slow[1]
        return connect(*args,**options)
    sqlite3.connect=scaled
    from flowguard.structure import store
    original=store.extract_all
    def parse(root,tasks,**options):
        if tasks:
            time.sleep(slow[0])
        return original(root,tasks,**options)
    store.extract_all=parse
sys.argv=[{module!r},*{list(argv)!r}]
runpy.run_module({module!r},run_name='__main__')
'''
    return subprocess.Popen([sys.executable, '-c', code], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding='utf-8') if slow else \
        subprocess.run([sys.executable, '-c', code], cwd=root, capture_output=True, text=True, encoding='utf-8', timeout=120)


def without_time(text):
    import re
    return re.sub(r'; [0-9.]+ s\b', '; T s', text)


def test_parallel_static_checks_of_two_packages_both_finish(tmp_path):
    root = tmp_path / 'pt'
    fixture_packages(root)
    runs = [cli(root, 'check', '--static', slow=(4, 3)) for _ in ('web', 'api')]
    results = [run.communicate(timeout=120) for run in runs]
    assert [run.returncode for run in runs] == [1, 1], results       # each its two red lines, not a lock error
    alone = cli(root, 'check', '--static')
    assert alone.returncode == 1, alone.stdout + alone.stderr
    reds = [line for line in alone.stdout.splitlines() if line.startswith('red: ')]
    assert len(reds) == 2 and any('api/src/m1.ts' in line for line in reds) and any('web/src/m1.ts' in line for line in reds)
    for out, err in results:
        assert 'database is locked' not in out + err
        assert without_time(out) == without_time(alone.stdout)


def test_a_vitest_preparation_and_a_static_check_started_together_both_finish(tmp_path):
    root = tmp_path / 'pt'
    fixture_packages(root)
    prepare = cli(root, 'prepare', '--root', str(root), '--package', str(root / 'web'), module='flowguard.intent.vitest',
                  slow=(4, 3))
    check = cli(root, 'check', '--static', slow=(4, 3))
    prepared, checked = prepare.communicate(timeout=120), check.communicate(timeout=120)
    assert prepare.returncode == 0, prepared
    assert json.loads(prepared[0].splitlines()[-1])['status'] in ('on', 'off')
    assert check.returncode == 1, checked
    assert sum(line.startswith('red: ') for line in checked[0].splitlines()) == 2


def test_reading_the_cache_waits_for_another_runs_commit(tmp_path):
    """sqlite waits 5 s by default; a reader of the cache waits as long as a writer (30 s), so a check started while
    another run commits waits for the commit instead of stopping with `task baseline could not be read`."""
    root = tmp_path / 'pt'
    fixture_packages(root)
    holder = holding(root / '.flowguard' / 'cache' / 'map.sqlite', 'EXCLUSIVE', 6.5)
    try:
        last = subprocess.Popen([sys.executable, '-c', f'import sys,runpy\nsys.path.insert(0,{PACKAGE_ROOT!r})\n'
                                 "sys.argv=['flowguard','show','--last']\nrunpy.run_module('flowguard',run_name='__main__')"],
                                cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        checked = cli(root, 'check', '--static')
        shown = last.communicate(timeout=60)
    finally:
        holder.communicate(timeout=30)
    assert checked.returncode == 1, checked.stdout + checked.stderr
    assert sum(line.startswith('red: ') for line in checked.stdout.splitlines()) == 2
    assert last.returncode == 0, shown
    assert shown[0].startswith('FlowGuard last run: check --static')

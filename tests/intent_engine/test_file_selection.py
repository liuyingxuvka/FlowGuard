"""File selection keeps real outcomes, without a second per-call trace ledger."""
import json
import sqlite3
from contextlib import closing

from flowguard.intent import cache, cli, deps
from flowguard.structure import build
from tests.intent_engine import _cli_fixture as cli_fixture
from tests.intent_engine.test_cli import project


def test_complete_check_records_outcomes_without_profiling_ordinary_functions(tmp_path):
    root, cfg = project(tmp_path)
    (root / 'tests/test_plain.py').write_text(f'from {root.name} import accept\ndef test_plain(): assert accept(4) is False\n')
    cli.init(cfg)
    assert cli_fixture.check(cfg, everything=True, before_main='''
from flowguard.intent import plugin
class ForbiddenOrdinaryFootprint:
    def __init__(self, *args, **kwargs):
        raise AssertionError('ordinary tests must not create a dynamic footprint')
plugin.Footprint = ForbiddenOrdinaryFootprint
''') == 0
    with sqlite3.connect(cfg.cache / 'map.sqlite') as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert not {'footprint', 'trace_value', 'trace_group', 'trace_test'} & tables
        assert connection.execute("SELECT outcome FROM reading WHERE test='tests/test_plain.py::test_plain'").fetchone() == ('passed',)
        full = json.loads(connection.execute("SELECT v FROM meta WHERE k='ordinary_collection'").fetchone()[0])
        assert full['tests/test_plain.py']['tests'] == ['tests/test_plain.py::test_plain']


def test_new_source_and_failing_test_cannot_borrow_the_old_collection(tmp_path, monkeypatch):
    root, cfg = project(tmp_path)
    cli.init(cfg)
    assert cli_fixture.check(cfg) == 0
    previous = cache.read(cfg)['attempt']['stamp']
    observed = cli_fixture.calls(monkeypatch)
    (root / 'new_source.py').write_text('def added(value: int): return value + 1\n')
    assert cli_fixture.check(cfg) == 0
    assert len(observed) == 1 and cache.read(cfg)['attempt']['stamp'] > previous
    observed.clear()
    (root / 'tests/test_new.py').write_text('def test_new(): assert False, "new failing node must actually run"\n')
    assert cli_fixture.check(cfg) == 1
    assert len(observed) == 1 and 'tests/test_new.py' in observed[0]
    assert cache.read(cfg)['tests']['tests/test_new.py::test_new']['outcome'] == 'failed'


def test_retired_trace_group_cannot_lend_a_new_file_digest_its_old_success(tmp_path, monkeypatch):
    root, cfg = project(tmp_path)
    test = root / 'tests/test_plain.py'
    test.write_text('def test_plain(): assert True\n')
    cli.init(cfg)
    assert cli_fixture.check(cfg, everything=True) == 0
    with sqlite3.connect(cfg.cache / 'map.sqlite') as connection:
        old = connection.execute("SELECT group_id FROM test_dependency WHERE file='tests/test_plain.py'").fetchone()[0]
        connection.executescript('CREATE TABLE trace_group(id TEXT PRIMARY KEY,refs TEXT); CREATE TABLE trace_test(test TEXT PRIMARY KEY,static_group TEXT,observed_group TEXT,unknown INT);')
        connection.execute('INSERT INTO trace_group VALUES(?,?)', (old, 'invalid old trace JSON'))
        connection.execute('INSERT INTO trace_test VALUES(?,?,?,?)', ('tests/test_plain.py::test_plain', old, old, 0))
    assert cache.read(cfg)['traces'] == {}
    observed = cli_fixture.calls(monkeypatch)
    test.write_text('def test_plain(): assert 2 + 2 == 4\n')
    assert cli_fixture.check(cfg) == 0 and len(observed) == 1
    with sqlite3.connect(cfg.cache / 'map.sqlite') as connection:
        fresh = connection.execute("SELECT group_id FROM test_dependency WHERE file='tests/test_plain.py'").fetchone()[0]
        assert fresh != old
    observed.clear()
    test.write_text('def test_plain(): assert False, "old success is not current evidence"\n')
    assert cli_fixture.check(cfg) == 1 and len(observed) == 1
    assert cache.read(cfg)['tests']['tests/test_plain.py::test_plain']['outcome'] == 'failed'


def test_a_stale_map_never_certifies_imports_from_newer_source_bytes(tmp_path):
    root, cfg = project(tmp_path)
    test = root / 'tests/test_plain.py'
    test.write_text(f'from {root.name} import accept\ndef test_plain(): assert accept(3) is True\n')
    cli.init(cfg)
    assert cli_fixture.check(cfg) == 0
    with closing(build(root)) as graph:
        (root / 'fresh_helper.py').write_text('OFFSET = 0\n')
        test.write_text(f'from {root.name} import accept\nfrom fresh_helper import OFFSET\ndef test_plain(): assert accept(3 + OFFSET) is True\n')
        stale = deps.test_dependencies(cfg, graph)['tests/test_plain.py']
        assert any('Map source identity changed: tests/test_plain.py' in reason for reason in stale['<unresolved>'])
    with closing(build(root)) as graph:
        fresh = deps.test_dependencies(cfg, graph)['tests/test_plain.py']
        assert '<unresolved>' not in fresh and 'fresh_helper.py' in fresh
    assert cli_fixture.check(cfg) == 0
    (root / 'fresh_helper.py').write_text('OFFSET = 1\n')
    assert cli_fixture.check(cfg) == 1
    assert cache.read(cfg)['tests']['tests/test_plain.py::test_plain']['outcome'] == 'failed'

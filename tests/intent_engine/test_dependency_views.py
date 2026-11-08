"""The one coarse dependency reader is stable and never executes source code."""
from contextlib import closing
import os

from flowguard.intent import deps
from flowguard.intent.config import load_config
from flowguard.structure import build
from flowguard.structure import store


def test_dependency_reads_keep_map_and_sources_unchanged_in_either_scope_order(tmp_path):
    (tmp_path / 'tests').mkdir()
    owner = tmp_path / 'owner.py'
    owner.write_text('import os\ndef pure(): return 3\ndef read(): return os.getenv("FG_AST_VALUE", "alpha")\n')
    (tmp_path / 'tests/test_a.py').write_text('from owner import pure\ndef test_a(): assert pure()==3\n')
    (tmp_path / 'tests/test_b.py').write_text('from owner import read\ndef test_b(): assert read()=="alpha"\n')
    cfg = load_config(tmp_path)
    with closing(build(tmp_path)) as graph:
        before = owner.read_bytes()
        stored = graph.con.execute('SELECT path,sha,data FROM file ORDER BY path').fetchall()
        first = deps.test_dependencies(cfg, graph)
        later = deps.test_dependencies(cfg, graph)
        assert first == later
        assert '<unresolved>' in later['tests/test_b.py']
        assert '<unresolved>' in first['tests/test_a.py'], 'the whole imported file keeps its opaque input boundary'
        assert owner.read_bytes() == before
        assert graph.con.execute('SELECT path,sha,data FROM file ORDER BY path').fetchall() == stored


def test_initializer_and_registered_lambda_inputs_stay_unknown_without_execution(tmp_path):
    (tmp_path / 'tests').mkdir()
    marker = tmp_path / 'must-not-execute'
    (tmp_path / 'owner.py').write_text('import os\nTABLE={"f":lambda: os.getenv("VALUE")}\n'
        + f'def read_default():\n    open({str(marker)!r},"w").write("bad")\n    return 3\n'
        + 'def unused(x=read_default()): return x\n')
    (tmp_path / 'tests/test_a.py').write_text('from owner import unused\ndef test_a(): assert unused()==3\n')
    with closing(build(tmp_path)) as graph:
        record = deps.test_dependencies(load_config(tmp_path), graph)['tests/test_a.py']
        assert '<unresolved>' in record
    assert not marker.exists()


def test_one_analysis_decodes_map_facts_once_for_all_test_files(tmp_path, monkeypatch):
    (tmp_path / 'tests').mkdir()
    for name in ('a', 'b', 'c'):
        (tmp_path / f'tests/test_{name}.py').write_text(f'def test_{name}(): assert True\n')
    cfg = load_config(tmp_path)
    with closing(build(tmp_path)) as graph:
        graph.nodes()  # Populate the Map's existing node-detail cache first.
        file_count = graph.con.execute('SELECT count(*) FROM file').fetchone()[0]
        unpack, decoded = store.unpack, []
        def measured(blob):
            decoded.append(blob)
            return unpack(blob)
        monkeypatch.setattr(store, 'unpack', measured)
        first = deps.test_dependencies(cfg, graph)
        assert len(first) == 3
        # Facts and source declarations each read the Map once, rather than
        # once for each ordinary test file. A later analysis must read afresh.
        assert len(decoded) == 2 * file_count
        decoded.clear()
        assert deps.test_dependencies(cfg, graph) == first
        assert len(decoded) == 2 * file_count


def test_shared_index_keeps_live_data_and_source_identity_checks(tmp_path):
    (tmp_path / 'tests').mkdir()
    owner = tmp_path / 'owner.py'
    owner.write_text('from pathlib import Path\ndef value(): return (Path(__file__).parent / "data.txt").read_text()\n')
    data = tmp_path / 'data.txt'
    data.write_text('old')
    for name in ('a', 'b'):
        (tmp_path / f'tests/test_{name}.py').write_text(f'from owner import value\ndef test_{name}(): assert value()=="old"\n')
    cfg = load_config(tmp_path)
    with closing(build(tmp_path)) as graph:
        original = deps.test_dependencies(cfg, graph)
        assert all('<unresolved>' not in record for record in original.values())
        stamp = data.stat()
        data.write_text('new')
        os.utime(data, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        changed = deps.test_dependencies(cfg, graph)
        assert all(changed[name]['data.txt'] != record['data.txt'] for name, record in original.items())
        stamp = owner.stat()
        owner.write_text(owner.read_text().replace('read_text()', 'read_bytes()'))
        os.utime(owner, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        stale = deps.test_dependencies(cfg, graph)
        assert all(any('Map source identity changed: owner.py' in reason for reason in record['<unresolved>'])
                   for record in stale.values())
        graph.refresh()
        rebuilt = deps.test_dependencies(cfg, graph)
        assert all('<unresolved>' not in record for record in rebuilt.values())
        assert all(rebuilt[name]['owner.py'] != record['owner.py'] for name, record in original.items())

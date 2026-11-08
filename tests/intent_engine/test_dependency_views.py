"""The one coarse dependency reader is stable and never executes source code."""
from contextlib import closing

from flowguard.intent import deps
from flowguard.intent.config import load_config
from flowguard.structure import build


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

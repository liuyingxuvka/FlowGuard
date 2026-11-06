"""Shared source ASTs must survive checks in either scope order unchanged."""
import ast
from contextlib import closing

from flowguard.intent import deps
from flowguard.intent.config import load_config
from flowguard.structure import build


def test_initialization_view_never_erases_a_later_reached_body(tmp_path):
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'owner.py').write_text('import os\ndef pure(): return 3\ndef read(): return os.getenv("FG_AST_VALUE", "alpha")\n')
    (tmp_path / 'tests/test_a.py').write_text('from owner import pure\ndef test_a(): assert pure()==3\n')
    (tmp_path / 'tests/test_b.py').write_text('from owner import read\ndef test_b(): assert read()=="alpha"\n')
    cfg = load_config(tmp_path)
    with closing(build(tmp_path)) as graph:
        context = deps._TestDependencies(cfg, graph, deps.Now(cfg, graph))
        tree = context.file('owner.py')[0]
        source = ast.dump(tree, include_attributes=True)
        first = context.record('tests/test_a.py')
        later = context.record('tests/test_b.py')
        assert '<unresolved>' not in first
        assert any('dynamic input/execution' in why for why in later['<unresolved>'])
        assert ast.dump(tree, include_attributes=True) == source
        fresh = deps._TestDependencies(cfg, graph, deps.Now(cfg, graph)).record('tests/test_b.py')
        assert later == fresh


def test_legacy_module_identity_and_execution_view_keep_separate_lambda_meanings():
    text = 'import os\nTABLE={"f":lambda: os.getenv("VALUE")}\ndef unused(x=read_default()): return read_body()\n'
    tree = ast.parse(text)
    before = ast.dump(tree, include_attributes=True)
    identity = deps._Module(set()).visit(tree)
    execution = deps._Module(set(), calls_only=True).visit(tree)
    def names(view):
        return {ast.unparse(node.func) for node in ast.walk(view) if isinstance(node, ast.Call)}
    assert names(identity) == {'os.getenv', 'read_default'}
    assert names(execution) == {'read_default'}
    assert ast.dump(tree, include_attributes=True) == before

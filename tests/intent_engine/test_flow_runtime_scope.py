"""Default flow verdicts cover observations and the finite model, not unseen code."""
import importlib
import uuid

from flowguard.intent.anchors import collect_sources
from flowguard.intent.engine import Engine
from flowguard.intent.flow import Capture, Flow, Node
from flowguard.intent.loader import load


BODY = '''# flowguard: event ENTRY(skip: bool)
def entry(skip: bool):
    if not skip:
        save()
    return publish()
# flowguard: event SAVED()
def save(): return None
# flowguard: event PUBLISHED()
def publish(): return True
'''


def project(tmp_path, *, skip=False, optional_edge=False):
    name = 'flow_scope_' + uuid.uuid4().hex
    (tmp_path / (name + '.py')).write_text(BODY)
    (tmp_path / 'SPEC.txt').write_text('Always save before publishing.\n')
    (tmp_path / 'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["SPEC.txt"]\n')
    model = load(root=tmp_path)
    assert not model.errors, model.errors
    index = collect_sources(tmp_path, [(name + '.py', name)])
    app = importlib.import_module(name)
    edges = (('entry', 'save'), ('save', 'publish'))
    if optional_edge:
        edges += (('entry', 'publish'),)
    flow = Flow('SAVE_FIRST', 'doc SPEC.txt "Always save before publishing."',
                (Node('entry', 'ENTRY'), Node('save', 'SAVED', phase='return'),
                 Node('publish', 'PUBLISHED', phase='return', end=True)), edges)
    model.anchor_index = index
    model.flows[flow.id] = flow
    with Capture(tmp_path, index, 'actual') as captured:
        assert app.entry(skip) is True
    return Engine(model), flow, captured.events


def test_default_flow_does_not_build_or_run_a_static_path_proof(tmp_path, monkeypatch):
    import flowguard.structure as structure
    engine, flow, events = project(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('a flow verdict must not build the map for a static path proof')
    monkeypatch.setattr(structure, 'build', forbidden)
    result = engine.run_flow(flow, events)
    assert result['verdict'] == 'ok' and result['runtime']['verdict'] == 'ok', result
    assert 'static' not in result
    assert result['files'] == [next(engine.m.cfg.root.glob('flow_scope_*.py')).name]


def test_unexecuted_source_bypass_has_an_explicit_unverified_source_scope(tmp_path):
    engine, flow, events = project(tmp_path, skip=False)
    result = engine.run_flow(flow, events)
    assert result['verdict'] == 'ok', result
    assert result['finite']['exhausted'] and result['runtime']['verdict'] == 'ok'
    assert 'static' not in result
    assert any('unexecuted source routes remain unverified' in note for note in result['info']), result


def test_unwalked_declared_edge_still_stays_grey(tmp_path):
    engine, flow, events = project(tmp_path, optional_edge=True)
    result = engine.run_flow(flow, events)
    assert result['verdict'] == 'grey' and not result['red'], result
    assert 'unobserved edge entry -> publish' in result['grey']


def test_an_executed_save_bypass_still_stays_red(tmp_path):
    engine, flow, events = project(tmp_path, skip=True)
    result = engine.run_flow(flow, events)
    assert result['verdict'] == 'red', result
    assert any('runtime path entry -> publish is not allowed' in reason for reason in result['red']), result

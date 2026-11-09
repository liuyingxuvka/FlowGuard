"""Selected child contracts calibrate before the selected item's probe runs."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from flowguard.intent import calibration
from flowguard.intent.api import Rule
from flowguard.intent.flow import Flow, Node, Read, Relation
from flowguard.intent.plugin import IntentItem, Session


def preparation(tmp_path, monkeypatch, *, probing=False):
    def make_rule(identifier, *, decides=None, uses=(), direct=False):
        item = Rule(identifier, decides or identifier, 'assumed: calibration order',
                    {'flag': bool}, lambda flag: flag, uses=uses)
        anchor = SimpleNamespace(calibrated_by='tests/test_native.py::test_case', name=identifier, fields=())
        item.homes = [SimpleNamespace(anchor=anchor) if direct else SimpleNamespace(scenario=object(), name=identifier)]
        return item

    leaf = make_rule('LEAF', direct=True)
    done = make_rule('DONE', decides='done', uses=[leaf])
    peer = make_rule('PEER', decides='done')
    extra = make_rule('EXTRA')
    outside = make_rule('OUTSIDE')
    child = Flow('CHILD', 'assumed: selected child',
                 (Node('entry', 'ENTRY'), Node('output', 'OUTPUT', phase='return', end=True)),
                 (('entry', 'output'),),
                 relations=(Relation(done, {'flag': Read('entry', 'arg.flag')}, Read('output'), 'output'),
                            Relation(extra, {'flag': Read('entry', 'arg.flag')}, on='entry')))
    parent = Flow('PARENT', 'assumed: selected parent',
                  (Node('entry', 'PARENT_ENTRY'), Node('child', 'OUTPUT', phase='return', model=child, end=True)),
                  (('entry', 'child'),))
    rules = {item.id: item for item in (leaf, done, peer, extra, outside)}
    model = SimpleNamespace(errors=[], flows={item.id: item for item in (child, parent)}, rules=rules,
                            states={}, structures={}, anchor_distincts={},
                            key=lambda decides: [item for item in rules.values() if item.decides == decides])
    state = Session.__new__(Session)
    state.config = SimpleNamespace()
    state.config._flowguard_intent = state
    state.cfg = SimpleNamespace(root=tmp_path)
    state.model = model
    state.get_model = lambda: model
    state.results = {}
    state.events, state.anchor_issues = [object()], ['anchor issue']   # the session's observed events
    calls = []
    installed = False

    def prepare(root, binding):
        assert root == tmp_path and not installed
        calls.append(('prepare', binding.name))

    def probe(declaration, events, issues):
        nonlocal installed
        assert declaration is parent
        # The Flow item is judged on the session's events, not on an empty stand-in.
        assert events is state.events and issues is state.anchor_issues
        installed = True
        calls.append(('probe', declaration.id))
        return dict(kind='flow', verdict='ok', red=[], grey=[], info=[])

    monkeypatch.setattr(calibration, '_prepare_scenario', prepare)
    monkeypatch.setattr(calibration, '_prepare', prepare)
    monkeypatch.setattr(calibration, 'probe_context', lambda config: probing)
    state.engine = SimpleNamespace(run_flow=probe)
    return state, parent, child, calls


def test_selected_child_relations_and_rule_closures_prepare_before_probe(tmp_path, monkeypatch):
    state, parent, _, calls = preparation(tmp_path, monkeypatch)
    item = SimpleNamespace(config=state.config, rule_id=parent.id, kind='flow', target=None,
                           nodeid='tests/intent/policy.py::PARENT[flow]')
    item.evaluate_verified = lambda: IntentItem.evaluate_verified(item)
    IntentItem.run_verified(item)
    assert calls[-1] == ('probe', 'PARENT')
    assert sorted(calls[:-1]) == [('prepare', name) for name in ('DONE', 'EXTRA', 'LEAF', 'PEER')]


def test_active_calibration_probe_does_not_prepare_child_contracts(tmp_path, monkeypatch):
    state, parent, _, calls = preparation(tmp_path, monkeypatch, probing=True)
    state.prepare_declaration(parent)
    assert calls == []


def test_flow_ids_and_cycles_prepare_each_rule_only_once(tmp_path, monkeypatch):
    state, parent, child, calls = preparation(tmp_path, monkeypatch)
    child.nodes = (*child.nodes, Node('recursive', 'OUTPUT', model='PARENT'))
    parent.nodes = tuple(replace(node, model='CHILD') if node.model else node for node in parent.nodes)
    state.prepare_declaration(parent)
    assert sorted(calls) == [('prepare', name) for name in ('DONE', 'EXTRA', 'LEAF', 'PEER')]


def test_unregistered_same_named_flow_does_not_prepare_registered_child(tmp_path, monkeypatch):
    state, parent, child, calls = preparation(tmp_path, monkeypatch)
    parent.nodes = tuple(replace(node, model=replace(child)) if node.model else node for node in parent.nodes)
    state.prepare_declaration(parent)
    assert calls == []


def test_selected_rule_still_prepares_uses_and_same_key_contracts(tmp_path, monkeypatch):
    state, _, _, calls = preparation(tmp_path, monkeypatch)
    state.prepare_declaration(state.model.rules['DONE'])
    assert sorted(calls) == [('prepare', name) for name in ('DONE', 'LEAF', 'PEER')]

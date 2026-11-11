"""Removal notices leave the retained SDK declarations and their errors intact."""
import pytest

from flowguard.intent import api
from flowguard.intent.flow import Flow, Transition


@pytest.mark.parametrize('name,args,kwargs', [
    ('precedes', ('SAVED', 'PUBLISHED'), {}),
    ('guarded_by', ('PERMITTED', 'UPDATED'), {}),
    ('transitions', ('Job.status',), {'new': {'saved'}}),
    ('checks', ('FEE', 'FEE_CASE'), {'days': 'arg.days'}),
])
def test_deprecated_templates_still_register_real_flow_declarations(name, args, kwargs, capsys, monkeypatch):
    monkeypatch.setattr(api, 'DECLARED', [])
    declared = getattr(api, name)(*args, source='assumed: retained source contract', **kwargs)
    assert isinstance(declared, Flow) and api.DECLARED == [declared]
    assert declared.source == 'assumed: retained source contract'
    if name == 'transitions':
        assert [(step.state, step.before, step.after, step.on) for step in declared.transitions] == [
            ('Job.status', 'new', 'saved', '*')]
    else:
        assert {node.anchor for node in declared.nodes} == set(args)
    output = capsys.readouterr()
    assert output.out == ''
    assert f'deprecated: {name} will be removed in 5.0' in output.err.splitlines()


def test_deprecated_sdk_declarations_keep_their_values_and_predicate(capsys, monkeypatch):
    monkeypatch.setattr(api, 'DECLARED', [])
    def violations(graph):
        return ['one violation'] if graph else []
    structural = api.structure_rule('ONE_SOURCE', source='assumed: one violation')(violations)
    separate = api.distinct('LEFT', 'RIGHT', why='independent answers', source='assumed: keep both')
    step = Transition('Job.status', 'new', 'saved', 'SAVE', initial=True)
    assert structural.pred is violations and structural.pred(True) == ['one violation']
    assert (separate.a, separate.b, separate.why) == ('LEFT', 'RIGHT', 'independent answers')
    assert api.DECLARED == [structural, separate]
    assert (step.state, step.before, step.after, step.on, step.initial) == (
        'Job.status', 'new', 'saved', 'SAVE', True)
    output = capsys.readouterr()
    assert output.out == ''
    for feature in ('structure_rule', 'distinct', 'Transition'):
        assert f'deprecated: {feature} will be removed in 5.0' in output.err.splitlines()


@pytest.mark.parametrize('feature,args,kwargs,error', [
    ('transitions', ('Job.status',), {}, 'needs before='),
    ('distinct', ('LEFT', 'RIGHT'), {'why': '', 'source': 'assumed: retained'}, 'needs why='),
])
def test_deprecation_notice_does_not_accept_an_invalid_old_call(feature, args, kwargs, error, capsys):
    with pytest.raises(api.IntentError, match=error):
        getattr(api, feature)(*args, **kwargs)
    output = capsys.readouterr()
    assert output.out == ''
    assert f'deprecated: {feature} will be removed in 5.0' in output.err.splitlines()

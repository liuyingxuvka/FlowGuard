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
    assert f'deprecated: {name} goes in 5.0 -> do not use it' in output.err.splitlines()


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
        assert f'deprecated: {feature} goes in 5.0 -> do not use it' in output.err.splitlines()


@pytest.mark.parametrize('feature,args,kwargs,error', [
    ('transitions', ('Job.status',), {}, 'needs before='),
    ('distinct', ('LEFT', 'RIGHT'), {'why': '', 'source': 'assumed: retained'}, 'needs why='),
])
def test_deprecation_notice_does_not_accept_an_invalid_old_call(feature, args, kwargs, error, capsys):
    with pytest.raises(api.IntentError, match=error):
        getattr(api, feature)(*args, **kwargs)
    output = capsys.readouterr()
    assert output.out == ''
    assert f'deprecated: {feature} goes in 5.0 -> do not use it' in output.err.splitlines()


COPIES = {
    'orders.py': '''
        # flowguard: same ACCEPT ref
        def accept(days: int) -> bool:
            return days <= 3


        # flowguard: same ACCEPT
        def preview_accept(days: int) -> bool:
            return days <= 3


        def quote_accept(days: int) -> bool:
            return days <= 3
    ''',
    'tests/test_orders.py': '''
        from orders import accept, preview_accept, quote_accept

        def test_accept():
            assert accept(3) and preview_accept(2) and quote_accept(1)
    ''',
}


def test_no_deprecation_notice_for_the_leads_and_the_copy_discovery_flowguard_makes_itself(tmp_path):
    """A notice says that the project's own input uses a feature that goes in 5.0. Old-value and
    similar-implementation leads and copy discovery are FlowGuard's own work: a project that writes only 4.3
    spellings sees no notice in pytest, check or check --static, while show --last still keeps the leads."""
    from tests.intent_engine.test_unverified_outcome import _cli, _pytest, _project
    root = _project(tmp_path / 'p', COPIES)
    path = root / 'orders.py'
    path.write_text(path.read_text(encoding='utf-8').replace(
        'def preview_accept(days: int) -> bool:\n    return days <= 3', 'def preview_accept(days: int) -> bool:\n    return days <= 4'),
        encoding='utf-8')
    # the sealed comparison of the copies is red; check --static runs no code and compares none
    for run, red, (result, text) in (('pytest', 1, _pytest(root, '-q')), ('check', 1, _cli(root, 'check')),
                                     ('check --static', 0, _cli(root, 'check', '--static'))):
        assert result.returncode == red and ('red: same ACCEPT: ' in text) == bool(red), (run, text)
        assert 'deprecated:' not in result.stderr, (run, result.stderr)
    result, text = _cli(root, 'show', '--last')
    assert 'deprecated features used' not in text, text

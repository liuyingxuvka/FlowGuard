"""Empty literal-row items do not require implicit probe side effects."""
from tests.intent_engine.test_joint_composition import native, project, source_sessions


def test_empty_rows_do_not_invent_or_require_a_verified_parent_call(tmp_path, monkeypatch):
    model, engine = project(tmp_path, coupled=True, nested=True)
    assert not model.deep
    def forbidden_probe(*args, **kwargs):
        raise AssertionError('ordinary empty rows must not start a decision probe')
    monkeypatch.setattr(engine, 'probe', forbidden_probe)
    rule = model.rules['FIRST']
    with native(engine):
        result = engine.run_home(rule, rule.homes[0], 'rows')
    assert result['verdict'] == 'ok', result
    assert result['n'] == result['composition']['parent_calls'] == 0
    assert not result['entered']
    assert not engine._used_witnesses.get('FIRST')
    assert result['contracts']['LEFT']['verdict'] == 'ok'


def test_empty_rows_keep_a_rejected_lower_contract_unavailable(tmp_path):
    model, engine = project(tmp_path, nested=True, unreadable=True)
    rule = model.rules['FIRST']
    with native(engine):
        result = engine.run_home(rule, rule.homes[0], 'rows')
    assert result['n'] == result['composition']['parent_calls'] == 0
    assert result['verdict'] == 'grey', result
    # This real fixture's nonlinear rule rejects detail >= 2, while its code
    # returns flag unchanged: the lower contract is red, never reusable.
    assert result['contracts']['LEFT']['verdict'] == 'red'
    assert any('LEFT lower contract is red' in reason for reason in result['grey'])

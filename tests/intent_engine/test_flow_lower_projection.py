"""Lower exports consume the model's actual fixed reading, never its predicate."""
from pathlib import Path
import importlib
import uuid
from dataclasses import replace
import pytest

from tests.intent_engine._cli_fixture import check as run_check

from flowguard.intent import calibration
from flowguard.intent.anchors import _execution_session
from flowguard.intent.engine import Engine
from flowguard.intent.flow import Capture, check_flow
from flowguard.intent.loader import load


def project(tmp_path, *, supersedes=False):
    root = tmp_path / ('projection_' + uuid.uuid4().hex)
    (root / 'tests/intent').mkdir(parents=True)
    module = 'projection_app_' + uuid.uuid4().hex
    native = 'test_native_' + module
    testnode = 'tests/' + native + '.py::test_case'
    (root / 'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["SPEC.txt"]\n')
    (root / 'SPEC.txt').write_text('Lower allows flag, detail is incidental.\nUpper requires lower and stock.\n')
    (root / (module + '.py')).write_text('''# flowguard: sensor LOWER_CALL(flag: bool, detail: bool) -> refusal: str | None
def lower(flag: bool, detail: bool) -> str | None:
    if flag:
        return None
    return 'blocked'
# flowguard: sensor UPPER_CALL(flag: bool, detail: bool, stock: bool) -> accepted: bool
def upper(flag: bool, detail: bool, stock: bool) -> bool:
    reason = lower(flag, detail)
    return reason is None and stock
''')
    (root / ('tests/' + native + '.py')).write_text('import pytest\nimport ' + module + ' as app\n'+'''@pytest.fixture
def flag(): return True
@pytest.fixture
def detail(): return False
@pytest.fixture
def stock(): return True
# flowguard: event CASE(flag: bool, detail: bool, stock: bool) calibrated_by=''' + testnode + '''
def test_case(flag: bool, detail: bool, stock: bool):
    app.lower(flag, detail)
    result = app.upper(flag, detail, stock)
    assert type(result) is bool
''')
    (root / 'tests/intent/policy.py').write_text('''from flowguard.intent import rule,row,flow,Node,Read,Relation
@rule('LOWER',decides='allowed',fields={'flag':bool,'detail':bool},source='doc SPEC.txt "Lower allows flag, detail is incidental."')
def LOWER(flag,detail): return flag
LOWER.rows(row(flag=True,detail=False,expect=True,why='flag permits'),row(flag=False,detail=False,expect=False,why='flag blocks'))
@rule('TOP',decides='top',fields={'allowed':bool,'stock':bool},uses=[LOWER],source='doc SPEC.txt "Upper requires lower and stock."')
def TOP(allowed,stock): return allowed and stock
TOP.rows(row(allowed=True,stock=True,expect=True,why='both are necessary'))
flow('GATES',source='doc SPEC.txt "Upper requires lower and stock."',
 nodes=[Node('case','CASE'),Node('lower','LOWER_CALL',phase='return',model='LOWER',caller='case'),Node('upper','UPPER_CALL',phase='return',caller='case',end=True)],
 edges=[('case','lower'),('lower','upper')],
 relations=[Relation('LOWER',{'flag':Read('case','arg.flag'),'detail':Read('case','arg.detail')},Read('lower',equals=None),on='lower'),
            Relation('TOP',{'allowed':Read('lower',equals=None),'stock':Read('case','arg.stock')},Read('upper'),on='upper')])
''')
    if supersedes:
        path = root / 'tests/intent/policy.py'
        path.write_text(path.read_text() + """
@rule('CURRENT',decides='allowed',fields={'flag':bool,'detail':bool},supersedes=[LOWER],source='doc SPEC.txt \"Lower allows flag, detail is incidental.\"')
def CURRENT(flag,detail): return flag
""")
    model = load(root=root)
    assert not model.errors, model.errors
    return model, Engine(model), module, native


def verified(tmp_path, *, flag=True, detail=False, stock=True, supersedes=False):
    model, engine, module, native = project(tmp_path, supersedes=supersedes)
    with _execution_session(model.cfg.root), calibration._execution_session(model.cfg.root):
        for rule in model.rules.values():
            for home in rule.homes:
                assert calibration._prepare_scenario(model.cfg.root, home)['status'] == 'ok'
        for rule in model.rules.values():
            if rule not in model.active(rule.decides):
                continue
            home = rule.homes[0]
            parts = [engine.run_rules(rule), *(dict(engine.run_home(rule, home, part), target=home.target)
                       for part in ('rows', 'cells')), dict(engine.run_live(rule, home), target=home.target)]
            assert all(p['verdict'] == 'ok' for p in parts), parts
            engine.contract_summary(rule.id, parts=parts)
    scenario = importlib.import_module('tests.' + native)
    with Capture(model.cfg.root, model.anchor_index, 'one') as captured:
        scenario.test_case(flag, detail, stock)
    return model, engine, captured


@pytest.fixture(scope='module')
def verified_projection(tmp_path_factory):
    return verified(tmp_path_factory.mktemp('verified-projection'))


def test_projected_lower_outcome_matches_its_verified_contract(verified_projection):
    model, engine, captured = verified_projection
    assert engine.contract_summary('LOWER')['complete']
    assert len(engine._verified_witnesses(model.rules['LOWER'], True)) == 2
    assert len(engine._verified_witnesses(model.rules['LOWER'], False)) == 2
    result = check_flow(model.flows['GATES'], model.anchor_index, captured.events, engine=engine)
    assert result['verdict'] == 'ok', result


def captured_case(model, *, flag=True, detail=False, stock=True):
    from flowguard.intent import sites
    fn = sites.resolve_loaded(model.rules['LOWER'].homes[0].scenario.target)
    with Capture(model.cfg.root, model.anchor_index, 'other') as captured:
        fn(flag, detail, stock)
    assert not captured.issues, captured.issues
    return captured


def test_the_projected_string_refusal_is_false_with_a_real_second_witness(verified_projection):
    model, engine, _ = verified_projection
    captured = captured_case(model, flag=False, detail=True)
    assert any(e.anchor == 'LOWER_CALL' and e.phase == 'return' and e.result == 'blocked' for e in captured.events)
    result = check_flow(model.flows['GATES'], model.anchor_index, captured.events, engine=engine)
    assert result['verdict'] == 'ok', result


def test_wrong_actual_projection_is_red_instead_of_using_the_expected_bool(verified_projection):
    model, engine, captured = verified_projection
    changed = [replace(e, result='blocked') if e.anchor == 'LOWER_CALL' and e.phase == 'return' and e.caller[1] == 'test_case' else e
               for e in captured.events]
    result = check_flow(model.flows['GATES'], model.anchor_index, changed, engine=engine)
    assert result['verdict'] == 'red' and any('actual lower result False' in why for why in result['red']), result


@pytest.mark.parametrize('actual', ['other-node', 'input-field', 'call-default', 'raise-default'])
def test_unrelated_or_incomplete_lower_outputs_cannot_borrow_a_verified_contract(verified_projection, actual):
    from flowguard.intent.flow import Read
    model, engine, captured = verified_projection
    original = model.flows['GATES']
    nodes, relations, events = original.nodes, original.relations, captured.events
    if actual == 'other-node':
        relations = (replace(relations[0], actual=Read('upper')), *relations[1:])
    elif actual == 'input-field':
        relations = (replace(relations[0], actual=Read('lower', 'arg.flag')), *relations[1:])
    else:
        phase = 'call' if actual == 'call-default' else 'raise'
        nodes = tuple(replace(n, phase=phase) if n.name == 'lower' else n for n in nodes)
        if phase == 'raise':
            events = [replace(e, phase='raise', error=ValueError('real refusal'), result=None)
                      if e.anchor == 'LOWER_CALL' and e.phase == 'return' and e.caller[1] == 'test_case' else e
                      for e in events]
    changed = replace(original, nodes=nodes, relations=relations)
    result = check_flow(changed, model.anchor_index, events, engine=engine)
    assert result['verdict'] == 'grey' and not result['red'], result
    assert any('lower output' in why or 'lower reading' in why for why in result['grey']), result


def test_duplicate_lower_relations_stay_ambiguous(verified_projection):
    model, engine, captured = verified_projection
    original = model.flows['GATES']
    changed = replace(original, relations=(original.relations[0], *original.relations))
    result = check_flow(changed, model.anchor_index, captured.events, engine=engine)
    assert result['verdict'] == 'grey' and any('2 actual readings' in why for why in result['grey']), result


def test_projected_lower_keeps_actual_native_parameter_domain_validation(verified_projection):
    model, engine, _ = verified_projection
    captured = captured_case(model, flag=42)
    result = check_flow(model.flows['GATES'], model.anchor_index, captured.events, engine=engine)
    assert result['verdict'] == 'red' and any('flag' in why and 'bool' in why for why in result['red']), result


def test_old_projection_relation_uses_the_legitimate_current_lower_owner(tmp_path):
    model, engine, captured = verified(tmp_path, supersedes=True)
    assert model.superseded_by['LOWER'] == 'CURRENT'
    assert engine.contract_summary('CURRENT')['verdict'] == 'ok'
    result = check_flow(model.flows['GATES'], model.anchor_index, captured.events, engine=engine)
    assert result['verdict'] == 'ok', result


def test_complete_cli_checks_the_same_projected_lower_flow(tmp_path):
    from flowguard.intent import cli
    model, _, _, _ = project(tmp_path)
    (model.cfg.root / 'tests/test_flowguard_intent.py').write_text(
        'def test_flowguard_intent(request):\n from flowguard.intent.plugin import sentinel\n sentinel(request.config)\n')
    assert run_check(model.cfg, everything=True) == 0

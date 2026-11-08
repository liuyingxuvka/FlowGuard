"""The observation bridge must preserve identities and fail as a tool, not as policy."""
import uuid
import pytest

from tests.intent_engine._source_fixture import source_engine, source_sessions

from flowguard.intent.anchors import Observation
from flowguard.intent import calibration
from flowguard.intent.api import Refused
from flowguard.intent.cells import same
from flowguard.intent.engine import Engine
from flowguard.intent.loader import ScenarioBinding, load
from flowguard.intent import probe


def project(tmp_path, *, refused=False, branches=False, repeated=False):
    root = tmp_path / ('scenario_' + uuid.uuid4().hex)
    root.mkdir()
    name = 'app_' + uuid.uuid4().hex
    (root / 'tests/intent').mkdir(parents=True)
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    code = '''# flowguard: sensor ACCEPT(days: days) -> accepted: bool calibrated_by=tests/test_case.py::test_case
def accept(days: int) -> bool:
    return days <= 3
'''
    native = f'''from {name} import accept
# flowguard: event CASE(days: int)
def test_case(days: int):
    answer = accept(days)
    assert type(answer) is bool
'''
    predicate = "Refused('ValueError')" if refused else 'age <= 3'
    expectation = "Refused('ValueError')" if refused else 'False'
    intent = f'''from flowguard.intent import rule,row,Refused,flow,Node,Read,Relation
@rule('LIMIT',decides='limit',source='assumed: original regression',fields={{'age':int}})
def LIMIT(age): return {predicate}
LIMIT.rows(row(age=4,expect={expectation},why='the original case stays literal'))
flow('CHECK',source='assumed: actual observation',
 nodes=[Node('case','CASE'),Node('answer','ACCEPT',phase='return',caller='case'),Node('done','CASE',phase='return')],
 edges=[('case','answer'),('answer','done')],
 relations=[Relation('LIMIT',{{'age':Read('case','arg.days')}},Read('answer'),on='answer')])
'''
    if branches:
        code += '''# flowguard: event WRITE(days: int) calibrated_by=tests/test_case.py::test_case
def write(days: int) -> None:
    if days < 0:
        raise ValueError('negative input')
'''
        intent += '''flow('BRANCHED',source='assumed: return and refusal are distinct actual readings',
 nodes=[Node('case','CASE'),Node('write','WRITE'),Node('error','WRITE',phase='raise'),
        Node('answer','ACCEPT',phase='return'),Node('done','CASE',phase='return')],
 edges=[('case','write'),('write','error'),('error','done'),('write','answer'),('answer','done')],
 relations=[Relation('LIMIT',{'age':Read('case','arg.days')},Read('answer'),on='answer'),
            Relation('LIMIT',{'age':Read('case','arg.days')},Read('error','error'),on='error')])
'''
        # Only the branched model is the requested binding in this control.
        first = intent.index("flow('CHECK'")
        last = intent.index("flow('BRANCHED'")
        intent = intent[:first] + intent[last:]
    if repeated:
        native += '''# flowguard: event OTHER(days: int)
def test_other(days: int):
    answer = accept(days)
    assert type(answer) is bool
'''
        intent += '''flow('OTHER_CHECK',source='assumed: separate test scope',
 nodes=[Node('case','OTHER'),Node('answer','ACCEPT',phase='return',caller='case'),Node('done','OTHER',phase='return')],
 edges=[('case','answer'),('answer','done')],
 relations=[Relation('LIMIT',{'age':Read('case','arg.days')},Read('answer'),on='answer')])
'''
    (root / (name + '.py')).write_text(code)
    (root / 'tests/test_case.py').write_text(native)
    (root / 'tests/intent/rules.py').write_text(intent)
    model = load(root=root)
    assert not model.errors, model.errors
    return model, Engine(model), name


def test_the_bridge_uses_one_index_and_maps_only_named_scenario_arguments(tmp_path):
    model, _, name = project(tmp_path)
    binding, = model.rules['LIMIT'].homes
    assert isinstance(binding, ScenarioBinding)
    assert binding.target == name + ':accept'
    assert binding.field_map == {'age': 'days'}
    assert binding.scenario.name == 'CASE'
    assert binding.anchor_index is model.anchor_index
    assert binding.relation_indices == (0,)


def test_return_and_error_branches_are_one_binding_without_losing_the_reader(tmp_path):
    model, _, name = project(tmp_path, branches=True)
    binding, = model.rules['LIMIT'].homes
    assert binding.target == name + ':write'
    assert binding.relation_indices == (0, 1)
    assert set(binding.actual_targets) == {name + ':write', name + ':accept'}
    assert set(binding.targets) == set(binding.actual_targets)


def test_shared_target_scenarios_are_explicitly_unknown_instead_of_silently_conflated(tmp_path):
    model, _, _ = project(tmp_path, repeated=True)
    assert len(model.rules['LIMIT'].homes) == 1
    assert any('not conflated' in text for text in model.scenario_issues['LIMIT'])


def test_backend_value_error_cannot_satisfy_an_expected_business_refusal(tmp_path, monkeypatch):
    model, engine, _ = project(tmp_path, refused=True)
    rule = model.rules['LIMIT']
    binding, = rule.homes
    fn = engine.home_sites(binding.target)[0]
    def broken_backend(root, actual_binding, values):
        fn(values['days'])
        raise ValueError('projection failed after the actual call')
    monkeypatch.setattr(calibration, '_observe_scenario_current', broken_backend, raising=False)
    result = engine.run_home(rule, binding, 'rows')
    assert result['verdict'] == 'grey', result
    assert result['entered']
    got = engine.call(binding, {'age': 4}, fn)
    assert not same(Refused('ValueError'), got)


def test_red_source_observation_is_not_downgraded_to_a_grey_lower_contract(tmp_path, monkeypatch):
    model, engine, _ = project(tmp_path)
    binding, = model.rules['LIMIT'].homes
    monkeypatch.setattr(calibration, '_observe_scenario_current',
        lambda *_: Observation('red', reasons=('actual source changed',)), raising=False)
    result = engine.run_home(model.rules['LIMIT'], binding, 'rows')
    assert result['verdict'] == 'red' and 'actual source changed' in result['red'], result


def test_unobserved_mutants_do_not_count_as_killed(tmp_path, monkeypatch):
    model, engine, _ = project(tmp_path)
    rule = model.rules['LIMIT']
    binding, = rule.homes
    fn = engine.home_sites(binding.target)[0]
    original = fn.__code__
    def fails_only_while_mutated(root, actual_binding, values):
        if fn.__code__ is not original and probe.CASE is None:
            raise ValueError('driver failed before the mutant produced an actual reading')
        return Observation('ok', value=fn(values['days']))
    monkeypatch.setattr(calibration, '_observe_scenario_current', fails_only_while_mutated, raising=False)
    result = engine.run_live(rule, binding)
    assert result['verdict'] == 'grey' and result['n'] > 0 and result['k'] == 0, result
    mutants = [mutation for site in result['sites'] for mutation in site['mutants']]
    assert mutants and all(mutation['killed'] is None for mutation in mutants)
    assert any('not measured' in reason for reason in result['grey'])


def joint_project(tmp_path, children=2, *, coupled=False):
    root = tmp_path / ('joint_scenario_' + uuid.uuid4().hex)
    root.mkdir()
    name = 'joint_' + uuid.uuid4().hex
    (root / 'tests/intent').mkdir(parents=True)
    (root / 'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["SPEC.txt"]\n')
    (root / 'SPEC.txt').write_text('Gates return flag, detail is incidental.\nApproval is their conjunction.\n')
    members = ('left', 'right', 'third')[:children]
    fields = [part + '_' + field for part in members for field in ('flag', 'detail')]
    params = ', '.join(field + ': bool' for field in fields)
    source = 'from __future__ import annotations\n'
    intent = 'from flowguard.intent import rule,row,flow,Node,Read,Relation\n'
    native = f'import pytest\nfrom types import SimpleNamespace\nimport {name} as app\n'
    for part in members:
        source += f'# flowguard: sensor {part.upper()}(flag: flag, detail: detail) -> accepted: bool\ndef {part}_gate(flag: bool, detail: bool) -> bool:\n    if flag:\n        return True\n    return False\n'
        identifier = part.upper()
        intent += f'''@rule('{identifier}',decides='{part}_ok',fields={{'flag':bool,'detail':bool}},anchor='{identifier}',source='doc SPEC.txt "Gates return flag, detail is incidental."')
def {identifier}(flag,detail): return flag
{identifier}.rows(row(flag=True,detail=False,expect=True,why='flag licenses the output'),row(flag=False,detail=False,expect=False,why='false flag refuses it'))
'''
    gates = ' and '.join(f'{part}_gate({part}.flag,{part}.detail)' for part in members)
    details = ' and '.join(part + '.detail' for part in members)
    value = 'not (' + details + ')' if coupled else 'True'
    source += '# flowguard: sensor APPROVAL(' + ', '.join(part + ': data' for part in members) + ') -> approved: bool calibrated_by=tests/test_case.py::test_case\n'
    source += 'def approve(' + ', '.join(part + ': object' for part in members) + ') -> bool:\n'
    source += f'    if not ({gates}):\n        return False\n    return {value}\n'
    for field in fields:
        native += f'@pytest.fixture\ndef {field}(): return {field.endswith("_flag")}\n'
    native += '# flowguard: event CASE(' + params + ') calibrated_by=tests/test_case.py::test_case\n'
    native += 'def test_case(' + params + '):\n'
    for part in members:
        native += f'    {part}=SimpleNamespace(flag={part}_flag,detail={part}_detail)\n'
        native += f'    app.{part}_gate({part}_flag,{part}_detail)\n'
    native += '    assert type(app.approve(' + ','.join(members) + ')) is bool\n'
    outcomes = ','.join(part + '_ok' for part in members)
    schema = ','.join(repr(part + '_ok') + ':bool' for part in members)
    intent += f"@rule('TOP',decides='approved',fields={{{schema}}},uses=[" + ','.join(part.upper() for part in members) + '],source=\'doc SPEC.txt "Approval is their conjunction."\')\n'
    intent += 'def TOP(' + outcomes + '): return ' + ' and '.join(part + '_ok' for part in members) + '\n'
    intent += 'TOP.rows(row(' + ','.join(part + '_ok=True' for part in members) + ',expect=True,why="all true outcomes license approval"))\n'
    nodes = ["Node('case','CASE')"] + [f"Node('{part}','{part.upper()}',phase='return',model='{part.upper()}',caller='case')" for part in members] + ["Node('approval','APPROVAL',phase='return',caller='case')", "Node('done','CASE',phase='return')"]
    chain = ['case', *members, 'approval', 'done']
    edges = list(zip(chain, chain[1:]))
    relations = [f"Relation('{part.upper()}',{{'flag':Read('case','arg.{part}_flag'),'detail':Read('case','arg.{part}_detail')}},Read('{part}'),on='{part}')" for part in members]
    relations += ["Relation('TOP',{" + ','.join(repr(part + '_ok') + f":Read('{part}')" for part in members) + "},Read('approval'),on='approval')"]
    intent += "flow('JOINT',source='doc SPEC.txt \"Approval is their conjunction.\"',nodes=[" + ','.join(nodes) + '],edges=' + repr(edges) + ',relations=[' + ','.join(relations) + '])\n'
    (root / (name + '.py')).write_text(source)
    (root / 'tests/test_case.py').write_text(native)
    (root / 'tests/intent/policy.py').write_text(intent)
    model = load(root=root)
    assert not model.errors, model.errors
    return model, source_engine(model)


@pytest.mark.parametrize('children', [2, 3])
def test_joint_mapping_comes_from_the_existing_lower_relations(tmp_path, children):
    model, _ = joint_project(tmp_path, children)
    binding, = model.rules['TOP'].homes
    assert isinstance(binding, ScenarioBinding)
    assert binding.field_map == {}
    assert set(binding.argument_plan['children']) == set(('LEFT', 'RIGHT', 'THIRD')[:children])
    for identifier, nested in binding.argument_plan['children'].items():
        assert nested['plan']['fields'] == {'flag': identifier.lower() + '_flag', 'detail': identifier.lower() + '_detail'}
    assert binding.targets == (binding.target,)


@pytest.mark.parametrize('children', [2, 3])
@pytest.mark.parametrize('coupled', [False, True])
def test_real_scenario_preserves_every_joint_witness(tmp_path, children, coupled):
    from flowguard.intent.anchors import _execution_session as actual_session
    from flowguard.intent.calibration import _execution_session, _prepare_scenario
    model, engine = joint_project(tmp_path, children, coupled=coupled)
    top = model.rules['TOP']
    binding, = top.homes
    with actual_session(model.cfg.root), _execution_session(model.cfg.root):
        prepared = _prepare_scenario(model.cfg.root, binding)
        assert prepared['status'] == 'ok', prepared
        result = engine.run_home(top, binding, 'cells')
    assert result['verdict'] == ('red' if coupled else 'ok'), result
    assert result['n'] == 2 ** children
    assert result['composition'] == dict(scope='finite', parent_calls=4 ** children,
                                        checked_all_witnesses=True, finite_domain=True)
    if coupled:
        assert any('depends on more' in reason for reason in result['red'])

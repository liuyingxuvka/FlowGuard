"""All three native Enum details must remain in the Scenario witness product."""
from tests.intent_engine._source_fixture import source_engine, source_sessions
import uuid


def enum_joint_project(tmp_path):
    from flowguard.intent.engine import Engine
    from flowguard.intent.loader import load
    root = tmp_path / ('enum_joint_' + uuid.uuid4().hex)
    (root / 'tests/intent').mkdir(parents=True)
    (root / 'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["SPEC.txt"]\n')
    (root / 'SPEC.txt').write_text('Gates return flag, detail is incidental.\nApproval is their conjunction.\n')
    (root / 'helpers.py').write_text('from enum import IntEnum\nclass Detail(IntEnum):\n    ZERO=0\n    ONE=1\n    TWO=2\n')
    source = ''
    intent = 'from flowguard.intent import rule,row,flow,Node,Read,Relation\nfrom helpers import Detail\n'
    native = 'import pytest\nfrom types import SimpleNamespace\nfrom helpers import Detail\nimport app\n'
    for part in ('left', 'right'):
        identifier = part.upper()
        source += f'''# flowguard: sensor {identifier}(flag: flag, detail: detail) -> accepted: bool
def {part}_gate(flag: bool, detail: int) -> bool:
    if flag:
        return True
    return False
'''
        intent += f'''@rule('{identifier}',decides='{part}_ok',fields={{'flag':bool,'detail':Detail}},source='doc SPEC.txt "Gates return flag, detail is incidental."')
def {identifier}(flag,detail): return flag
{identifier}.rows(row(flag=True,detail=Detail.ZERO,expect=True,why='flag licenses the output'),row(flag=False,detail=Detail.ZERO,expect=False,why='false flag refuses it'))
'''
        native += f'''@pytest.fixture
def {part}_flag(): return True
@pytest.fixture
def {part}_detail(): return Detail.ZERO
'''
    source += '''# flowguard: sensor APPROVAL(left: data, right: data) -> approved: bool
def approve(left: object, right: object) -> bool:
    approved = left_gate(left.flag,left.detail) and right_gate(right.flag,right.detail)
    if not approved:
        return False
    return not (left.detail == 2 and right.detail == 2)
'''
    native += '''# flowguard: event CASE(left_flag: bool, left_detail: Detail, right_flag: bool, right_detail: Detail) calibrated_by=tests/test_case.py::test_case
def test_case(left_flag: bool, left_detail: Detail, right_flag: bool, right_detail: Detail):
    left=SimpleNamespace(flag=left_flag,detail=int(left_detail))
    right=SimpleNamespace(flag=right_flag,detail=int(right_detail))
    app.left_gate(left_flag,int(left_detail))
    app.right_gate(right_flag,int(right_detail))
    assert type(app.approve(left,right)) is bool
'''
    intent += '''@rule('TOP',decides='approved',fields={'left_ok':bool,'right_ok':bool},uses=[LEFT,RIGHT],source='doc SPEC.txt "Approval is their conjunction."')
def TOP(left_ok,right_ok): return left_ok and right_ok
TOP.rows(row(left_ok=True,right_ok=True,expect=True,why='all true outcomes license approval'))
flow('JOINT',source='doc SPEC.txt "Approval is their conjunction."',
 nodes=[Node('case','CASE'),Node('left','LEFT',phase='return',model='LEFT',caller='case'),
        Node('right','RIGHT',phase='return',model='RIGHT',caller='case'),
        Node('approval','APPROVAL',phase='return',caller='case'),Node('done','CASE',phase='return')],
 edges=[('case','left'),('left','right'),('right','approval'),('approval','done')],
 relations=[Relation('LEFT',{'flag':Read('case','arg.left_flag'),'detail':Read('case','arg.left_detail')},Read('left'),on='left'),
            Relation('RIGHT',{'flag':Read('case','arg.right_flag'),'detail':Read('case','arg.right_detail')},Read('right'),on='right'),
            Relation('TOP',{'left_ok':Read('left'),'right_ok':Read('right')},Read('approval'),on='approval')])
'''
    (root / 'app.py').write_text(source)
    (root / 'tests/test_case.py').write_text(native)
    (root / 'tests/intent/policy.py').write_text(intent)
    model = load(root=root)
    assert not model.errors, model.errors
    return model, Engine(model)


def test_the_third_native_enum_scenario_witness_is_not_discarded(tmp_path):
    from flowguard.intent.anchors import _execution_session as actual_session
    from flowguard.intent import calibration
    from flowguard.intent.loader import ScenarioBinding
    model, _ = enum_joint_project(tmp_path)
    engine = source_engine(model)
    assert all(isinstance(h, ScenarioBinding) for r in model.rules.values() for h in r.homes)
    assert all(len(r.homes) == 1 for r in model.rules.values())
    with actual_session(model.cfg.root), calibration._execution_session(model.cfg.root):
        for rule in model.rules.values():
            prepared = calibration._prepare_scenario(model.cfg.root, rule.homes[0])
            assert prepared['status'] == 'ok', (rule.id, prepared)
        top = model.rules['TOP']
        result = engine.run_home(top, top.homes[0], 'cells')
    assert result['verdict'] == 'red', result
    assert any('depends on more' in reason for reason in result['red']), result
    assert result['composition'] == dict(scope='finite', parent_calls=36,
                                         checked_all_witnesses=True, finite_domain=True), result
    assert result['bad'] == 1 and result['n'] == 4, result

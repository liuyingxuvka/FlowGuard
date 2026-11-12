"""Lower exports consume the model's actual fixed reading, never its predicate."""
from pathlib import Path
import importlib
import uuid
from dataclasses import replace
import pytest

from tests.intent_engine._cli_fixture import check as run_check
from tests.intent_engine._source_fixture import source_engine, source_sessions

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
    model, _, module, native = project(tmp_path, supersedes=supersedes)
    engine = source_engine(model)
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


@pytest.fixture
def verified_projection(tmp_path, source_sessions):
    return verified(tmp_path)




def captured_case(model, *, flag=True, detail=False, stock=True):
    from flowguard.intent import sites
    fn = sites.resolve_loaded(model.rules['LOWER'].homes[0].scenario.target)
    with Capture(model.cfg.root, model.anchor_index, 'other') as captured:
        fn(flag, detail, stock)
    assert not captured.issues, captured.issues
    return captured














def test_complete_cli_checks_the_same_projected_lower_flow(tmp_path):
    from flowguard.intent import cli
    model, _, _, _ = project(tmp_path)
    (model.cfg.root / 'tests/test_flowguard_intent.py').write_text(
        'def test_flowguard_intent(request):\n from flowguard.intent.plugin import sentinel\n sentinel(request.config)\n')
    assert run_check(model.cfg, everything=True) == 0


def test_complete_cli_keeps_a_real_wrong_projected_lower_result_red(tmp_path):
    from flowguard.intent import cache
    model, _, module, _ = project(tmp_path)
    path = model.cfg.root / (module + '.py')
    path.write_text(path.read_text().replace('return None', "return 'blocked'", 1))
    (model.cfg.root / 'tests/test_flowguard_intent.py').write_text(
        'def test_flowguard_intent(request):\n from flowguard.intent.plugin import sentinel\n sentinel(request.config)\n')
    assert run_check(model.cfg, everything=True) == 1
    results = cache.read(model.cfg)['results']
    flow = results['GATES']['items']['tests/intent/policy.py::GATES[flow]']
    assert flow['verdict'] == 'red' and any('LOWER' in why for why in flow['red']), flow


def test_complete_cli_without_actual_projected_readings_stays_grey(tmp_path):
    from flowguard.intent import cache
    model, _, _, _ = project(tmp_path)
    path = model.cfg.root / 'tests/intent/policy.py'
    path.write_text(path.read_text().replace("Read('lower',equals=None)",
                                            "Read('lower','arg.missing',equals=None)"))
    (model.cfg.root / 'tests/test_flowguard_intent.py').write_text(
        'def test_flowguard_intent(request):\n from flowguard.intent.plugin import sentinel\n sentinel(request.config)\n')
    assert run_check(model.cfg, everything=True) == 0
    results = cache.read(model.cfg)['results']
    flow = results['GATES']['items']['tests/intent/policy.py::GATES[flow]']
    assert flow['verdict'] == 'grey' and flow['grey'] and not flow['red'], flow


def test_projected_rules_keep_the_raw_sensor_behavior_difference(tmp_path):
    from flowguard.intent import cache
    from tests.intent_engine.test_default_runtime_signals import _git
    model, _, module, native = project(tmp_path)
    root = model.cfg.root
    (root / 'tests/test_flowguard_intent.py').write_text(
        'def test_flowguard_intent(request):\n from flowguard.intent.plugin import sentinel\n sentinel(request.config)\n')
    # Inputs come only from the tests' calls (4.5): one ordinary test reaches the refusing branch.
    test = root / ('tests/' + native + '.py')
    test.write_text(test.read_text() + 'def test_blocked():\n    assert app.lower(False, False) is not None\n')
    _git(root, 'init', '-q', '-b', 'main')
    _git(root, 'add', module + '.py', 'tests', 'pyproject.toml', 'SPEC.txt')
    _git(root, '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
         'commit', '-qm', 'original projected rule fixture')
    path = root / (module + '.py')
    path.write_text(path.read_text().replace("return 'blocked'", "return 'denied'"))
    assert run_check(model.cfg, everything=True) == 0
    report = cache.observations(model.cfg)['items']
    assert not report['red'], report
    readings = [item for item in report['items'] if item['name'] == 'LOWER_CALL']
    # The recorded call's sealed outcome before and after the edit (JSON values, 4.5).
    assert [change for reading in readings for change in reading['changed']] == [
        [{'flag': False, 'detail': False}, 'blocked', 'denied']], readings

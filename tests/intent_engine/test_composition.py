"""Lower outcome contracts still execute real lower inputs, including a second witness."""
from contextlib import closing
import importlib
from pathlib import Path
import subprocess
import sys
import textwrap
import uuid

from flowguard.intent.config import load_config
from flowguard.intent.engine import Engine
from flowguard.intent.loader import load
from flowguard.intent import cache, deps
from flowguard.structure import build
from tests.intent_engine._source_fixture import annotate, source_engine, source_sessions


CODE = '''
def refusal(ended, suspended, owed):
    if suspended:
        return 'blocked'
    if ended > 3:
        return 'blocked'
    if owed > 50:
        return 'blocked'
    return None

def checkout(ended, suspended, owed, stock):
    reason = refusal(ended, suspended, owed)
    return stock and reason is None

def checkout_reads_reason(ended, suspended, owed, stock):
    reason = refusal(ended, suspended, owed)
    return stock and (reason is None or reason == 'allowed')
'''

INTENT = '''
from flowguard.intent import rule, row
@rule('STANDING', decides='good_standing', fields={'ended': int, 'suspended': bool, 'owed': int},
      source='doc policy.txt "May buy when standing and stock remains"')
def STANDING(ended, suspended, owed):
    return ended <= 3 and not suspended and owed <= 50
STANDING.rows(
    row(ended=4, suspended=False, owed=0, expect=False, why='expired'),
    row(ended=0, suspended=True, owed=0, expect=False, why='suspended'),
    row(ended=0, suspended=False, owed=0, expect=True, why='standing'))

@rule('CHECKOUT', decides='may_buy', fields={'standing': bool, 'stock': bool}, uses=[STANDING],
      source='doc policy.txt "May buy when standing and stock remains"')
def CHECKOUT(standing, stock):
    return standing and stock
from flowguard.intent import flow,Node,Read,Relation
flow('STANDING_CHECKOUT',source='doc policy.txt "May buy when standing and stock remains"',
 nodes=[Node('case','CASE',start=True),Node('standing','REFUSAL',phase='return',model='STANDING',caller='case'),Node('checkout','CHECKOUT_RESULT',phase='return',caller='case',end=True)],
 edges=[('case','standing'),('standing','checkout')],
 relations=[Relation('STANDING',{'ended':Read('case','arg.ended'),'suspended':Read('case','arg.suspended'),'owed':Read('case','arg.owed')},Read('standing',equals=None),on='standing'),
            Relation('CHECKOUT',{'standing':Read('standing',equals=None),'stock':Read('case','arg.stock')},Read('checkout'),on='checkout')])
'''


def git(root, *args):
    return subprocess.run(['git', '-c', 'user.name=fixture', '-c', 'user.email=fixture@example.invalid',
                           '-C', str(root), *args], check=True, capture_output=True).stdout


def project(tmp_path, *, home='checkout', code=CODE, intent=INTENT, lower_types=None):
    root = tmp_path / ('project_' + uuid.uuid4().hex)
    root.mkdir()
    module = 'policy_' + uuid.uuid4().hex
    (root / 'policy.txt').write_text('May buy when standing and stock remains\n')
    (root / 'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["policy.txt"]\n')
    lower_types=lower_types or {'ended':'int','suspended':'bool','owed':'int'}
    testnode='tests/test_case.py::test_case'
    code=annotate(code,'refusal','REFUSAL',lower_types,output='str | None',calibrated_by=testnode)
    code=annotate(code,home,'CHECKOUT_RESULT',{**lower_types,'stock':'bool'},calibrated_by=testnode)
    (root / (module + '.py')).write_text(code)
    git(root, 'init', '-q')
    git(root, 'add', 'policy.txt', 'pyproject.toml', module + '.py')
    git(root, 'commit', '-qm', 'Existing policy')
    (root / 'tests/intent').mkdir(parents=True)
    (root / 'tests/intent/policy.py').write_text(textwrap.dedent(intent).replace('PKG', module).replace('HOME', home))
    case='import '+module+' as app\n'
    if lower_types['ended']=='End':case+='from '+module+' import End,Flag,Money\n'
    values={'ended':'End.ZERO' if lower_types['ended']=='End'else'0','suspended':'Flag.NO' if lower_types['suspended']=='Flag'else'False','owed':'Money.ZERO' if lower_types['owed']=='Money'else'0','stock':'False'}
    params={**lower_types,'stock':'bool'}
    signature=', '.join(key+': '+kind for key,kind in params.items())
    definition=', '.join(key+': '+kind+'='+values[key] for key,kind in params.items())
    case+='# flowguard: event CASE('+signature+')\n'
    case+='def test_case('+definition+'):\n    app.refusal(ended,suspended,owed)\n    result=app.'+home+'(ended,suspended,owed,stock)\n    assert type(result) is bool\n'
    (root/'tests/test_case.py').write_text(case)
    git(root, 'add', '.')
    git(root, 'commit', '-qm', 'Implement the existing policy')
    model = load(load_config(root))
    assert not model.errors, model.errors
    return model, source_engine(model), module


def test_parent_uses_only_outcomes_but_its_home_runs_lower_code(tmp_path):
    model, engine, module = project(tmp_path)
    rule = model.rules['CHECKOUT']
    result = engine.run_home(rule, rule.homes[0], 'cells')
    assert result['verdict'] == 'ok', result
    assert result['n'] == 4
    assert module + ':refusal' in result['footprint']
    assert result['contracts']['STANDING']['verdict'] == 'ok'
    assert result['contracts']['STANDING']['outcomes'] == [['bool', 'False'], ['bool', 'True']]
    first, second = engine.witnesses(model.rules['STANDING'], False)
    assert first != second
    assert not model.rules['STANDING'].eval(first) and not model.rules['STANDING'].eval(second)


def test_two_equal_outcomes_expose_an_upper_dependency_on_the_refusal_words(tmp_path):
    code = CODE.replace("if suspended:\n        return 'blocked'", "if suspended:\n        return 'allowed'")
    model, engine, _ = project(tmp_path, home='checkout_reads_reason', code=code)
    parent = model.rules['CHECKOUT']
    result = engine.run_home(parent, parent.homes[0], 'cells')
    assert result['verdict'] == 'red', result
    assert any('depends on more of STANDING than its outcome' in line for line in result['red'])
    assert result['contracts']['STANDING']['verdict'] == 'ok'


def test_only_one_verified_input_cannot_claim_adequacy(tmp_path):
    enums = 'from enum import IntEnum\nclass End(IntEnum):\n    ZERO = 0\nclass Flag(IntEnum):\n    NO = 0\nclass Money(IntEnum):\n    ZERO = 0\n'
    intent = 'from PKG import End,Flag,Money\n' + INTENT.replace("fields={'ended': int, 'suspended': bool, 'owed': int}", "fields={'ended': End, 'suspended': Flag, 'owed': Money}")
    intent = intent.replace("row(ended=4, suspended=False, owed=0, expect=False, why='expired'),", '')
    intent = intent.replace("row(ended=0, suspended=True, owed=0, expect=False, why='suspended'),", '')
    intent = intent.replace('row(ended=0, suspended=False, owed=0, expect=True', 'row(ended=End.ZERO, suspended=Flag.NO, owed=Money.ZERO, expect=True')
    model, engine, _ = project(tmp_path, intent=intent, code=enums+CODE,lower_types={'ended':'End','suspended':'Flag','owed':'Money'})
    parent = model.rules['CHECKOUT']
    result = engine.run_home(parent, parent.homes[0], 'cells')
    assert result['verdict'] == 'grey', result
    assert any('only 1 different verified inputs' in line for line in result['grey'])
    assert not result['red']


def test_uses_and_witness_follow_a_two_step_supersede(tmp_path):
    intent = INTENT + '''
@rule('MIDDLE', decides='good_standing', fields={'ended': int, 'suspended': bool, 'owed': int},
      source='doc policy.txt "May buy when standing and stock remains"', supersedes=[STANDING])
def MIDDLE(ended,suspended,owed):
    return ended <= 3 and not suspended and owed <= 50
@rule('LATEST', decides='good_standing', fields={'ended': int, 'suspended': bool, 'owed': int},
      source='doc policy.txt "May buy when standing and stock remains"', supersedes=[MIDDLE])
def LATEST(ended,suspended,owed):
    return ended <= 3 and not suspended and owed <= 50
'''
    model, engine, _ = project(tmp_path, intent=intent)
    parent = model.rules['CHECKOUT']
    assert parent.uses == ('LATEST',)
    assert len(model.rules['LATEST'].homes) == 1
    result = engine.run_home(parent, parent.homes[0], 'cells')
    assert result['verdict'] == 'ok', result
    assert result['contracts']['LATEST']['verdict'] == 'ok'


def _saved(model, engine, graph):
    results, records = {}, {}
    for rule in model.rules.values():
        parts = [engine.run_rules(rule)]
        for home in rule.homes:
            parts += [engine.run_home(rule, home, 'rows'), engine.run_home(rule, home, 'cells'), engine.run_live(rule, home)]
        assert all(part['verdict'] == 'ok' for part in parts), parts
        results[rule.id] = {'items': {str(index): part for index, part in enumerate(parts)}}
        records[rule.id] = deps.record(model.cfg, model, rule, parts, graph)
    return dict(results=results, deps=records, summary=cache.scan(model.cfg))


def _changed(model, module, source):
    path = model.cfg.root / (module + '.py')
    home='checkout_reads_reason' if model.rules['CHECKOUT'].homes[0].target.endswith(':checkout_reads_reason') else 'checkout'
    source=annotate(source,'refusal','REFUSAL',{'ended':'int','suspended':'bool','owed':'int'},output='str | None',calibrated_by='tests/test_case.py::test_case')
    source=annotate(source,home,'CHECKOUT_RESULT',{'ended':'int','suspended':'bool','owed':'int','stock':'bool'},calibrated_by='tests/test_case.py::test_case')
    path.write_text(source + '\n# a distinct source version\n')
    sys.modules.pop(module, None)
    importlib.invalidate_caches()
    current = load(model.cfg)
    return current, source_engine(current)


def test_same_lower_contract_does_not_cut_the_upper_dependency_recheck(tmp_path):
    model, engine, module = project(tmp_path)
    with closing(build(model.cfg.root)) as graph:
        saved = _saved(model, engine, graph)
        old_lower = engine.contract_summary('STANDING')
        new_code = CODE.replace("if ended > 3:", "if not ended <= 3:")
        current, changed = _changed(model, module, new_code)
        graph.refresh()
        now = deps.Now(current.cfg, graph)
        picked = deps.affected(saved, current, now)
        assert set(picked) == {'STANDING', 'CHECKOUT'}
        lower = changed.contract_summary('STANDING')
        assert lower['verdict'] == 'ok', lower
        assert lower['outcomes'] == old_lower['outcomes']
        # Equal lower outcomes do not erase a changed real input of the upper.
        dependency = 'file:' + module + '.py'
        assert saved['deps']['CHECKOUT']['dependencies'][dependency] != now(dependency)
        parent = current.rules['CHECKOUT']
        assert changed.run_home(parent, parent.homes[0], 'cells')['verdict'] == 'ok'


def test_an_undeclared_detail_can_miss_locally_but_all_recheck_catches_it(tmp_path):
    model, engine, module = project(tmp_path, home='checkout_reads_reason')
    with closing(build(model.cfg.root)) as graph:
        saved = _saved(model, engine, graph)
        old_lower = engine.contract_summary('STANDING')
        new_code = CODE.replace("if suspended:\n        return 'blocked'", "if suspended:\n        return 'allowed'")
        current, changed = _changed(model, module, new_code)
        graph.refresh()
        now = deps.Now(current.cfg, graph)
        lower = changed.contract_summary('STANDING')
        assert lower['verdict'] == 'ok', lower
        assert lower['outcomes'] == old_lower['outcomes']
        picked = deps.affected(saved, current, now)
        assert {'STANDING', 'CHECKOUT'} <= set(picked)
        dependency = 'file:' + module + '.py'
        assert saved['deps']['CHECKOUT']['dependencies'][dependency] != now(dependency)
        parent = current.rules['CHECKOUT']
        full_result = changed.run_home(parent, parent.homes[0], 'cells')
        assert full_result['verdict'] == 'red'
        assert any('depends on more' in line for line in full_result['red'])

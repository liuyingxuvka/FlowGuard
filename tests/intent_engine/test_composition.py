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





def _recorded_events():
    from flowguard.intent import calibration
    return calibration._CURRENT.get().events


def test_sealed_points_complete_both_lower_contracts_and_the_flow_from_one_recorded_run(tmp_path):
    # The scenario test ran once, with ended=0, suspended=False, owed=0, stock=False. Every other point of the
    # finite domains is that recorded call with the point's inputs put in place, evaluated sealed (design 4.5).
    model, engine, _ = project(tmp_path)
    # The ordinary check, as `flowguard check` runs it: the --deep live item installs mutants, which the one
    # recorded run never executed, so it is not part of this contract.
    model.deep = False
    for identifier in ('STANDING', 'CHECKOUT'):
        # A pytest session gives each lower contract its items' actual results (Engine.contract_summary),
        # each with its rule and target as the plugin stores them.
        rule = model.rules[identifier]
        parts = [dict(engine.run_rules(rule), rule=identifier, target=None),
                 *(dict(engine.run_home(rule, home, part), rule=identifier, target=home.target)
                   for home in rule.homes for part in ('rows', 'cells'))]
        assert all(part['verdict'] == 'ok' for part in parts), (identifier, parts)
        contract = engine.contract_summary(rule, parts=parts)
        assert contract['verdict'] == 'ok' and contract['complete'] and not contract['reasons'], (identifier, contract)
    flow = engine.run_flow(model.flows['STANDING_CHECKOUT'], _recorded_events())
    assert flow['verdict'] == 'ok' and not flow['grey'] and not flow['red'], flow
    assert flow['finite']['exhausted'] and flow['runtime']['checked_relations'] == 2


def test_a_lower_contract_the_sealed_environment_cannot_run_stays_grey_with_its_reason(tmp_path):
    # refusal reads a module value the sealed environment does not have: only the recorded input is compared.
    code = CODE.replace('def refusal(', "MAXIMUM = int('3')\n\ndef refusal(", 1).replace('if ended > 3:', 'if ended > MAXIMUM:')
    model, engine, _ = project(tmp_path, code=code)
    model.deep = False
    standing = model.rules['STANDING']
    home, = standing.homes
    cells = engine.run_home(standing, home, 'cells')
    assert cells['verdict'] == 'grey' and not cells['red'], cells
    assert any('uses unavailable binding MAXIMUM' in reason for reason in cells['grey']), cells['grey']
    contract = engine.contract_summary(standing)
    assert contract['verdict'] == 'grey', contract
    flow = engine.run_flow(model.flows['STANDING_CHECKOUT'], _recorded_events())
    assert flow['verdict'] == 'grey' and not flow['red'], flow
    assert 'lower model STANDING: real contract is not a complete verified finite contract' in flow['grey'], flow['grey']

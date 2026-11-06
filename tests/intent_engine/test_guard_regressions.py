"""The actual adapter/refusal reproductions from the supplied dogfood reports."""
from pathlib import Path
import textwrap
import uuid
import json
import subprocess

import pytest

from flowguard.intent.config import load_config
from flowguard.intent.engine import Engine
from flowguard.intent.loader import load
from tests.intent_engine._source_fixture import annotate, scenario, source_engine, source_sessions


def make(tmp_path, code, intent, helper='', *, scenario_case=None, bindings=None, retired=False):
    root = tmp_path / ('p' + uuid.uuid4().hex)
    root.mkdir()
    name = 'subject_' + uuid.uuid4().hex
    code=textwrap.dedent(code).replace('PKG',name)
    intent=textwrap.dedent(intent).replace('PKG',name)
    (root / 'tests/intent').mkdir(parents=True)
    if scenario_case:
        data=dict(scenario_case)
        data['body']=data['body'].replace('PKG',name)
        code,intent=scenario(root,name,code,intent,**data)
    for target,(anchor,parameters) in (bindings or {}).items():
        code=annotate(code,target,anchor,parameters)
    (root / (name + '.py')).write_text(code)
    (root / 'tests/intent/rules.py').write_text(intent)
    if helper:
        (root / ('tests/world_' + name + '.py')).write_text(textwrap.dedent(helper).replace('PKG', name))
    (root / 'pyproject.toml').write_text('[tool.flowguard]\nroots=[".","tests"]\n')
    model = load(load_config(root))
    if not retired:assert not model.errors, model.errors
    return model, source_engine(model)


STORE = '''
def open_store(): return {'members': [], 'next': 1}
def add_member(store, ended):
    identifier = store['next']
    store['next'] += 1
    store['members'].append({'id': identifier, 'ended': ended})
    return identifier
def lapse_notices(store):
    return [{'member_id': m['id']} for m in store['members'] if m['ended'] > 3]
'''
MEMBERS = '''
import PKG
def world(c):
    store = PKG.open_store()
    member = PKG.add_member(store, c.ended)
    return store, member
'''
NOTICE = '''
from flowguard.intent import rule,row
@rule('LAPSE',decides='lapse',fields={'ended':int},source='assumed: after grace')
def LAPSE(ended): return ended > 3
LAPSE.rows(row(ended=4,expect=True,why='the first lapsed day'))
'''


@pytest.mark.parametrize('selection', [
    "member in [n['member_id'] for n in notices]",
    "any(n['member_id']==member for n in notices)",
    "len([n for n in notices if n['member_id']==member])>0",
])
def test_selecting_the_real_member_from_the_result_is_honest(tmp_path, selection):
    body="from world_PKG import world\nfrom types import SimpleNamespace\nstore,member=world(SimpleNamespace(ended=ended))\nnotices=app.lapse_notices(store)\nselected="+selection+"\nassert type(selected) is bool"
    model,engine=make(tmp_path,STORE,NOTICE,MEMBERS,scenario_case=dict(rule='LAPSE',target='lapse_notices',parameters={'ended':'int'},source_parameters={'store':'dict'},output='list',body=body,read="Read('answer',view='empty',equals=False)"))
    rule=model.rules['LAPSE']
    result=engine.run_home(rule,rule.homes[0],'cells')
    assert result['verdict']=='ok',result


@pytest.mark.parametrize('body', [
    "store,member=world(c)\n    return c.ended in [n['member_id'] for n in fn(store)]",
    "store,member=world(c)\n    answer=c.ended>3\n    fn(store)\n    return answer",
])
def test_a_case_mirror_still_cannot_replace_the_result(tmp_path, body):
    old=NOTICE+"\n@LAPSE.home('PKG:lapse_notices')\ndef mirror(c,fn):\n    "+body+"\n"
    model,_=make(tmp_path,STORE,old,MEMBERS,retired=True)
    assert any('call adapters were removed' in e['msg']and'rebuild'in e['msg']for e in model.errors)


WORKSHOPS = '''
from datetime import date,timedelta
def open_store(): return {'workshops':{},'next':1}
def add_workshop(store,when,fee):
    identifier=store['next']
    store['next']+=1
    store['workshops'][identifier]={'when':when,'fee':fee}
    return identifier
def withdraw(store,identifier,today):
    workshop=store['workshops'][identifier]
    refund=workshop['when']-timedelta(days=2)>=today
    return refund and workshop['fee']!='0'
'''
WORKSHOP_WORLD = '''
from datetime import date,timedelta
import PKG
TODAY=date(2026,5,20)
def setup(days):
    store=PKG.open_store()
    return store,PKG.add_workshop(store,TODAY+timedelta(days=days),'10')
def rigged(c):
    store=PKG.open_store()
    return store,PKG.add_workshop(store,TODAY+timedelta(days=10),'10' if c.days_before>=2 else '0')
'''
WAIVE = '''
from flowguard.intent import rule,row
@rule('WAIVE',decides='waived',fields={'days_before':int},source='assumed: refund threshold')
def WAIVE(days_before): return None if days_before<0 else days_before>=2
WAIVE.rows(row(days_before=2,expect=True,why='two days is early enough'))
'''


def test_a_builder_cannot_encode_the_policy_in_a_fee(tmp_path):
    old=WAIVE+"\n@WAIVE.home('PKG:withdraw')\ndef rigged_builder(c,fn):\n    store,workshop=rigged(c)\n    return fn(store,workshop,TODAY)\n"
    model,_=make(tmp_path,WORKSHOPS,old,WORKSHOP_WORLD,retired=True)
    assert any('call adapters were removed' in e['msg']and'rebuild'in e['msg']for e in model.errors)


def test_an_honest_date_builder_remains_accepted(tmp_path):
    body='from world_PKG import TODAY,setup\nstore,workshop=setup(days_before)\nanswer=app.withdraw(store,workshop,TODAY)\nassert type(answer) is bool'
    model,engine=make(tmp_path,WORKSHOPS,WAIVE,WORKSHOP_WORLD,scenario_case=dict(rule='WAIVE',target='withdraw',parameters={'days_before':'int'},source_parameters={'store':'dict','identifier':'int','today':'date'},body=body))
    rule=model.rules['WAIVE'];result=engine.run_home(rule,rule.homes[0],'cells')
    assert result['verdict']=='ok',result


def test_a_refusal_is_the_observed_result_even_after_return_true(tmp_path):
    code = '''
    class Contract:
        @classmethod
        def from_dict(cls,data):
            if set(data)-{'known'}:
                raise ValueError('unknown field')
            return cls()
    '''
    intent = '''
    from flowguard.intent import rule,row,Refused
    @rule('FIELDS',decides='field',fields={'key':('known','unknown')},source='assumed: only known field')
    def FIELDS(key):
        return True if key=='known' else Refused(ValueError,contains='unknown field')
    FIELDS.rows(row(key='unknown',expect=Refused(ValueError,contains='unknown field'),why='unknown field refused'))
    '''
    model, engine = make(tmp_path, code, intent, scenario_case=dict(rule='FIELDS',target='Contract.from_dict',parameters={'key':'str'},source_parameters={'data':'dict'},output='object',defaults={'key':repr('known')},body='contract=app.Contract.from_dict({key:None})\nassert isinstance(contract,app.Contract)',read="Read('answer','error',equals=None)"))
    rule = model.rules['FIELDS']
    result = engine.run_home(rule, rule.homes[0], 'cells')
    assert result['verdict'] == 'ok' and result['entered'], result


def test_a_field_named_boolean_site_cannot_disappear_from_liveness(tmp_path):
    code = '''
    def validate(unique):
        if not isinstance(unique,list) or any(not isinstance(item,str) or not item for item in unique):
            raise ValueError('invalid ids')
    '''
    intent = '''
    from flowguard.intent import rule,row
    @rule('VALID',decides='accept_valid_ids',fields={'unique':((),('red',))},source='assumed: the currently checked valid-input range')
    def VALID(unique):return True if unique in ((),('red',)) else None
    VALID.rows(row(unique=(),expect=True,why='valid empty list'))
    '''
    model, engine = make(tmp_path, code, intent, scenario_case=dict(rule='VALID',target='validate',parameters={'unique':'tuple'},source_parameters={'unique':'list'},output='None',body='answer=app.validate(list(unique))\nassert answer is None',read="Read('answer','error',equals=None)"))
    rule = model.rules['VALID']
    result = engine.run_live(rule, rule.homes[0])
    site = next(site for site in result['sites'] if site['text'].startswith('not isinstance(unique, list) or'))
    assert result['verdict'] == 'grey'
    assert site['realized'] and site['mutable'] and site['live'] is False
    assert any('or becomes and' in reason for reason in result['grey'])


@pytest.mark.parametrize('redefined', [False, True])
def test_superseding_a_rule_keeps_its_distinct_adapter_without_copying_it(tmp_path, redefined):
    code='def access(days):return days<=7\ndef workshop(days):return days<=3\n'
    intent="""from flowguard.intent import rule,row,distinct
@rule('OLD',decides='grace',fields={'days':int},anchor='ACCESS',source='assumed: old rule')
def OLD(days):return days<=3
OLD.rows(row(days=4,expect=False,why='old fourth-day lesson',retired='new decision has seven days'))
distinct('ACCESS','WORKSHOP',why='workshops have their own three days',source='assumed: independent workshops')
@rule('NEW',decides='grace',fields={'days':int},supersedes=[OLD],source='assumed: new seven-day rule')
def NEW(days):return days<=7
NEW.rows(row(days=7,expect=True,why='new last grace day'))
"""
    if redefined:intent=intent.replace('workshops have their own three days','explicit replacement reason')
    model,engine=make(tmp_path,code,intent,bindings={'access':('ACCESS',{'days':'int'}),'workshop':('WORKSHOP',{'days':'int'})})
    new=model.rules['NEW']
    assert len(new.homes)==1
    assert new.homes[0].target.endswith(':access')
    distincts=list(model.anchor_distincts.values())
    assert len(distincts)==1
    assert not hasattr(distincts[0],'adapter')
    assert distincts[0].why==('explicit replacement reason'if redefined else'workshops have their own three days')
    from flowguard.intent.differences import anchor_distinct
    result=anchor_distinct(model.cfg.root,distincts[0],index=model.anchor_index)
    assert result['status']=='ok'and result['changed']>0,result


@pytest.mark.parametrize('calls_business_method', [False, True])
def test_selfuse_refusal_syntax_does_not_whitelist_its_business_methods(tmp_path, calls_business_method):
    intent = '''
    from flowguard.intent import Refused, rule
    @rule('REFUSAL',decides='refusal',fields={'refuse':bool},source='assumed: one refusal value')
    def REFUSAL(refuse):
        return BODY
    '''
    body = "Refused(ValueError, contains='unknown').matches(ValueError('unknown'))" if calls_business_method else "Refused(ValueError, contains='unknown') if refuse else True"
    model, engine = make(tmp_path, '', intent.replace('BODY', body))
    from flowguard.intent import Refused
    sdk_file = Refused.__init__.__code__.co_filename
    # This is exactly the self-hosting boundary: DSL implementation belongs to
    # the maintained project, while the declarations remain test-side code.
    engine.is_project = lambda filename: filename == sdk_file
    reasons = engine.independence(model.rules['REFUSAL'])
    assert bool(reasons) == calls_business_method, reasons
    if calls_business_method:
        assert any('circular' in reason for reason in reasons)


def test_a_real_proven_row_clears_and_preserves_the_display_star(tmp_path):
    from flowguard.intent import history
    from flowguard.structure import build
    from contextlib import closing

    root = tmp_path / ('proof_' + uuid.uuid4().hex)
    root.mkdir()
    module = root.name

    def git(*args):
        return subprocess.run(['git', '-C', str(root), '-c', 'user.name=proof', '-c', 'user.email=proof@example.invalid', *args],
                              check=True, capture_output=True).stdout.decode().strip()

    (root / 'pyproject.toml').write_text('[tool.flowguard]\nauthority_docs=["policy.txt"]\n')
    (root / 'policy.txt').write_text('At most three days.\n')
    source = root / (module + '.py')
    source.write_text(annotate('def accept(days): return days <= 4\n','accept','LIMIT',{'days':'int'}))
    git('init', '-q')
    git('add', '.')
    git('commit', '-qm', 'Existing wrong fourth-day behavior')
    old = git('rev-parse', 'HEAD')
    source.write_text(annotate('def accept(days): return days <= 3\n','accept','LIMIT',{'days':'int'}))
    folder = root / 'tests/intent'
    folder.mkdir(parents=True)
    path = folder / 'rule.py'
    path.write_text(f'''from flowguard.intent import rule,row
@rule('LIMIT',decides='acceptance',fields={{'days':int}},anchor='LIMIT',source='doc policy.txt "At most three days."')
def LIMIT(days): return days <= 3
LIMIT.rows(row(days=4,expect=False,why='the real fourth-day correction'))
''')
    git('add', '.')
    git('commit', '-qm', 'Fix the home and retain its exact counterexample')
    model = load(load_config(root))
    assert not model.errors
    rule = model.rules['LIMIT']
    assert Engine(model).run_rules(rule)['provisional'] is True
    proof = history.proven(model.cfg, rule, rule.live_rows[0], base=old)
    assert proof['status'] == 'proven', proof
    assert proof['base'] == old
    with closing(build(root)) as graph:
        graph.con.execute('CREATE TABLE result(item TEXT PRIMARY KEY,rule TEXT,verdict TEXT,payload TEXT,stamp REAL)')
        graph.con.execute('INSERT INTO result VALUES(?,?,?,?,?)',
                          ('tests/intent/rule.py::LIMIT[rules]', 'LIMIT', 'ok',
                           json.dumps(dict(kind='rules', verdict='ok', provisional=True, proven_rows=[proof])), 1.0))
        graph.con.commit()
    result = Engine(model).run_rules(rule)
    assert result['provisional'] is False
    assert result['proven_rows'] == [proof]
    path.write_text(path.read_text().replace('expect=False', 'expect=True'))
    changed = load(model.cfg)
    result = Engine(changed).run_rules(changed.rules['LIMIT'])
    assert result['provisional'] is True
    assert result['proven_rows'] == []
    assert result['verdict'] == 'red'


def test_more_than_seven_realized_sites_are_all_measured(tmp_path):
    names = tuple('abcdefgh')
    parameters = ','.join(names)
    expression = ' and '.join(names)
    fields = ','.join(f'{name!r}:bool' for name in names)
    arguments = ','.join('c.' + name for name in names)
    row = ','.join(name + '=True' for name in names)
    code = f'def accept({parameters}): return {expression}\n'
    intent = f'''
from flowguard.intent import rule,row
@rule('ALL_FLAGS',decides='all_flags',fields={{{fields}}},anchor='ALL_FLAGS',source='assumed: every flag is necessary')
def ALL_FLAGS({parameters}): return {expression}
ALL_FLAGS.rows(row({row},expect=True,why='all eight required flags are present'))
'''
    model, engine = make(tmp_path, code, intent,bindings={'accept':('ALL_FLAGS',{name:'bool'for name in names})})
    rule = model.rules['ALL_FLAGS']
    result = engine.run_live(rule, rule.homes[0])
    assert result['verdict'] == 'ok', result
    assert result['n'] > 7 and result['k'] == result['n']
    assert result['mutants'] > 7
    assert not any('not measured' in reason for reason in result['grey'])


@pytest.mark.parametrize('expression', ['exists("fixed")', 'Directory().exists()'])
def test_a_callable_name_is_not_a_rule_field(tmp_path, expression):
    code = f'''
def exists(identifier): return False
class Directory:
    def exists(self): return False
def accept(flag):
    if flag:
        return True
    return False
    if {expression}:
        return True
'''
    intent = '''
from flowguard.intent import rule,row
@rule('EXISTING',decides='existence',fields={'exists':bool},source='assumed: the existing state')
def EXISTING(exists): return exists
EXISTING.rows(row(exists=True,expect=True,why='the actual state is true'))
'''
    model, engine = make(tmp_path, code, intent,scenario_case=dict(rule='EXISTING',target='accept',parameters={'exists':'bool'},source_parameters={'flag':'bool'} if 'def accept(flag)' in code else {'exists':'bool'} if 'def accept(exists)' in code else {'state':'dict'},body="answer=app.accept({'exists':exists})\nassert type(answer) is bool" if 'def accept(state)' in code else 'answer=app.accept(exists)\nassert type(answer) is bool'))
    rule = model.rules['EXISTING']
    result = engine.run_live(rule, rule.homes[0])
    assert result['verdict'] == 'ok', result


def test_a_call_argument_still_names_the_rule_field(tmp_path):
    code = '''
def helper(value): return value
def accept(exists):
    if exists:
        return True
    return False
    if helper(exists):
        return True
'''
    intent = '''
from flowguard.intent import rule,row
@rule('EXISTING',decides='existence',fields={'exists':bool},source='assumed: the existing state')
def EXISTING(exists): return exists
EXISTING.rows(row(exists=True,expect=True,why='the actual state is true'))
'''
    model, engine = make(tmp_path, code, intent,scenario_case=dict(rule='EXISTING',target='accept',parameters={'exists':'bool'},source_parameters={'flag':'bool'} if 'def accept(flag)' in code else {'exists':'bool'} if 'def accept(exists)' in code else {'state':'dict'},body="answer=app.accept({'exists':exists})\nassert type(answer) is bool" if 'def accept(state)' in code else 'answer=app.accept(exists)\nassert type(answer) is bool'))
    rule = model.rules['EXISTING']
    result = engine.run_live(rule, rule.homes[0])
    assert result['verdict'] == 'grey', result
    assert any('unreached site' in reason for reason in result['grey'])


def test_a_dictionary_field_still_names_the_rule_field(tmp_path):
    code = '''
def accept(state):
    if state['exists']:
        return True
    return False
    if state['exists']:
        return True
'''
    intent = '''
from flowguard.intent import rule,row
@rule('EXISTING',decides='existence',fields={'exists':bool},source='assumed: the existing state')
def EXISTING(exists): return exists
EXISTING.rows(row(exists=True,expect=True,why='the actual state is true'))
'''
    model, engine = make(tmp_path, code, intent,scenario_case=dict(rule='EXISTING',target='accept',parameters={'exists':'bool'},source_parameters={'flag':'bool'} if 'def accept(flag)' in code else {'exists':'bool'} if 'def accept(exists)' in code else {'state':'dict'},body="answer=app.accept({'exists':exists})\nassert type(answer) is bool" if 'def accept(state)' in code else 'answer=app.accept(exists)\nassert type(answer) is bool'))
    rule = model.rules['EXISTING']
    result = engine.run_live(rule, rule.homes[0])
    assert result['verdict'] == 'grey', result
    assert any('unreached site' in reason for reason in result['grey'])

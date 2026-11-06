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


def make(tmp_path, code, intent, helper=''):
    root = tmp_path / ('p' + uuid.uuid4().hex)
    root.mkdir()
    name = 'subject_' + uuid.uuid4().hex
    (root / (name + '.py')).write_text(textwrap.dedent(code).replace('PKG', name))
    (root / 'tests/intent').mkdir(parents=True)
    (root / 'tests/intent/rules.py').write_text(textwrap.dedent(intent).replace('PKG', name))
    if helper:
        (root / ('tests/world_' + name + '.py')).write_text(textwrap.dedent(helper).replace('PKG', name))
    (root / 'pyproject.toml').write_text('[tool.flowguard]\nroots=[".","tests"]\n')
    model = load(load_config(root))
    assert not model.errors, model.errors
    return model, Engine(model)


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
from world_PKG import world
@rule('LAPSE',decides='lapse',fields={'ended':int},source='assumed: after grace')
def LAPSE(ended): return ended > 3
LAPSE.rows(row(ended=4,expect=True,why='the first lapsed day'))
@LAPSE.home('PKG:lapse_notices')
def notice(c,fn):
    BODY
'''


@pytest.mark.parametrize('body', [
    "store,member=world(c)\n    return member in [n['member_id'] for n in fn(store)]",
    "store,member=world(c)\n    return any(n['member_id']==member for n in fn(store))",
    "store,member=world(c)\n    mine=[n for n in fn(store) if n['member_id']==member]\n    return len(mine)>0",
])
def test_selecting_the_real_member_from_the_result_is_honest(tmp_path, body):
    model, engine = make(tmp_path, STORE, NOTICE.replace('BODY', body), MEMBERS)
    rule = model.rules['LAPSE']
    result = engine.run_home(rule, rule.homes[0], 'cells')
    assert result['verdict'] == 'ok', result


@pytest.mark.parametrize('body', [
    "store,member=world(c)\n    return c.ended in [n['member_id'] for n in fn(store)]",
    "store,member=world(c)\n    answer=c.ended>3\n    fn(store)\n    return answer",
])
def test_a_case_mirror_still_cannot_replace_the_result(tmp_path, body):
    model, engine = make(tmp_path, STORE, NOTICE.replace('BODY', body), MEMBERS)
    rule = model.rules['LAPSE']
    result = engine.run_home(rule, rule.homes[0], 'cells')
    assert any('adapter decides' in reason for reason in result['grey'])


WORKSHOPS = '''
from datetime import timedelta
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
from world_PKG import TODAY,rigged,setup
@rule('WAIVE',decides='waived',fields={'days_before':int},source='assumed: refund threshold')
def WAIVE(days_before): return None if days_before<0 else days_before>=2
WAIVE.rows(row(days_before=2,expect=True,why='two days is early enough'))
@WAIVE.home('PKG:withdraw')
def withdraw(c,fn):
    BODY
'''


def test_a_builder_cannot_encode_the_policy_in_a_fee(tmp_path):
    model, engine = make(tmp_path, WORKSHOPS, WAIVE.replace('BODY', 'store,workshop=rigged(c)\n    return fn(store,workshop,TODAY)'), WORKSHOP_WORLD)
    rule = model.rules['WAIVE']
    result = engine.run_home(rule, rule.homes[0], 'cells')
    assert result['verdict'] == 'grey' and not result['red'], result
    assert any('forces the answer via rigged' in reason for reason in result['grey'])


def test_an_honest_date_builder_remains_accepted(tmp_path):
    model, engine = make(tmp_path, WORKSHOPS, WAIVE.replace('BODY', 'store,workshop=setup(c.days_before)\n    return fn(store,workshop,TODAY)'), WORKSHOP_WORLD)
    rule = model.rules['WAIVE']
    result = engine.run_home(rule, rule.homes[0], 'cells')
    assert result['verdict'] == 'ok', result


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
    @FIELDS.home('PKG:Contract.from_dict')
    def from_dict(c,fn):
        fn({c.key:None})
        return True
    '''
    model, engine = make(tmp_path, code, intent)
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
    @VALID.home('PKG:validate')
    def validate(c,fn):return fn(list(c.unique)) is None
    '''
    model, engine = make(tmp_path, code, intent)
    rule = model.rules['VALID']
    result = engine.run_live(rule, rule.homes[0])
    site = next(site for site in result['sites'] if site['text'].startswith('not isinstance(unique, list) or'))
    assert result['verdict'] == 'grey'
    assert site['realized'] and site['mutable'] and site['live'] is False
    assert any('or becomes and' in reason for reason in result['grey'])


@pytest.mark.parametrize('redefined', [False, True])
def test_superseding_a_rule_keeps_its_distinct_adapter_without_copying_it(tmp_path, redefined):
    code = '''
    def access(days): return days <= 7
    def workshop(days): return days <= 3
    '''
    intent = '''
    from flowguard.intent import rule,row,distinct
    @rule('OLD',decides='grace',fields={'days':int},source='assumed: old rule')
    def OLD(days): return days <= 3
    OLD.rows(row(days=4,expect=False,why='old fourth-day lesson',retired='new decision has seven days'))
    @OLD.home('PKG:access')
    def access(c,fn): return fn(c.days)
    @distinct('OLD','PKG:workshop',why='workshops have their own three days',source='assumed: independent workshops')
    def workshop(c,fn): return fn(c.days)
    @rule('NEW',decides='grace',fields={'days':int},supersedes=[OLD],source='assumed: new seven-day rule')
    def NEW(days): return days <= 7
    NEW.rows(row(days=7,expect=True,why='new last grace day'))
    '''
    intent = textwrap.dedent(intent)
    if redefined:
        intent += "\n@distinct('NEW','PKG:workshop',why='explicit replacement reason',source='assumed: updated separation')\ndef new_workshop(c,fn): return fn(c.days)\n"
    model, engine = make(tmp_path, code, intent)
    new = model.rules['NEW']
    assert len(new.homes) == 1
    assert new.homes[0].target.endswith(':access')
    distincts = model.node_distincts('NEW')
    assert len(distincts) == 1
    assert distincts[0].adapter is not None
    assert distincts[0].why == ('explicit replacement reason' if redefined else 'workshops have their own three days')
    result = engine.run_distinct(new, distincts[0])
    assert result['verdict'] == 'ok', result


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
    source.write_text('def accept(days): return days <= 4\n')
    git('init', '-q')
    git('add', '.')
    git('commit', '-qm', 'Existing wrong fourth-day behavior')
    old = git('rev-parse', 'HEAD')
    source.write_text('def accept(days): return days <= 3\n')
    folder = root / 'tests/intent'
    folder.mkdir(parents=True)
    path = folder / 'rule.py'
    path.write_text(f'''from flowguard.intent import rule,row
@rule('LIMIT',decides='acceptance',fields={{'days':int}},source='doc policy.txt "At most three days."')
def LIMIT(days): return days <= 3
LIMIT.rows(row(days=4,expect=False,why='the real fourth-day correction'))
@LIMIT.home('{module}:accept')
def home(c,fn): return fn(c.days)
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
@rule('ALL_FLAGS',decides='all_flags',fields={{{fields}}},source='assumed: every flag is necessary')
def ALL_FLAGS({parameters}): return {expression}
ALL_FLAGS.rows(row({row},expect=True,why='all eight required flags are present'))
@ALL_FLAGS.home('PKG:accept')
def flags(c,fn): return fn({arguments})
'''
    model, engine = make(tmp_path, code, intent)
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
@EXISTING.home('PKG:accept')
def home(c,fn): return fn(c.exists)
'''
    model, engine = make(tmp_path, code, intent)
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
@EXISTING.home('PKG:accept')
def home(c,fn): return fn(c.exists)
'''
    model, engine = make(tmp_path, code, intent)
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
@EXISTING.home('PKG:accept')
def home(c,fn): return fn({'exists':c.exists})
'''
    model, engine = make(tmp_path, code, intent)
    rule = model.rules['EXISTING']
    result = engine.run_live(rule, rule.homes[0])
    assert result['verdict'] == 'grey', result
    assert any('unreached site' in reason for reason in result['grey'])

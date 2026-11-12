"""Independent controls for forgotten boundaries and false evidence, not implementation mirrors."""
from pathlib import Path
import textwrap
import uuid

import pytest

from flowguard.intent.config import load_config
from flowguard.intent.engine import Engine
from flowguard.intent.loader import load
from tests.intent_engine._source_fixture import annotate, native, scenario, source_engine, source_sessions


def project(tmp_path, code, declarations):
    root = tmp_path / uuid.uuid4().hex
    root.mkdir()
    module = 'sample_' + root.name
    code=textwrap.dedent(code)
    scenarios=[]
    if code.strip():
        import ast
        tree=ast.parse(code)
        bindings=[(n.name,n.name) for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in {'accept','second','always','later'}]
        for cls in (n for n in tree.body if isinstance(n,ast.ClassDef)):
            bindings += [(cls.name+'.'+n.name,n.name)for n in cls.body if isinstance(n,ast.FunctionDef)and n.name=='accept']
        (root/'tests').mkdir()
        for target,short in bindings:
            name='LIMIT' if short in {'accept','second'} else short.upper()
            call='app.'+target+'(days)'
            instance='.'in target and not any(isinstance(d,ast.Name)and d.id in {'classmethod','staticmethod'}for d in next(n for n in next(c for c in tree.body if isinstance(c,ast.ClassDef)and c.name==target.split('.')[0]).body if isinstance(n,ast.FunctionDef)and n.name==short).decorator_list)
            if instance:
                call='app.'+target.replace('.', '().',1)+'(days)'
                scenarios.append((target,call))
            else:
                testnode=native(root,module,target,name+'_'+short.upper(),{'days':'int'},call=call) if '.'in target else ''
                code=annotate(code,target,name,{'days':'int'},calibrated_by=testnode)
    for target,call in scenarios:
        declarations=declarations.replace(", anchor='LIMIT'",'')
        code,declarations=scenario(root,module,code,declarations,rule='LIMIT',target=target,
            parameters={'days':'int'},source_parameters={'days':'int'},
            body='answer='+call+'\nassert type(answer) is bool')
    (root / (module + '.py')).write_text(code)
    folder = root / 'tests/intent'
    folder.mkdir(parents=True)
    header = 'from flowguard.intent import rule, row, Refused, distinct, D\n'
    (folder / 'policy.py').write_text(header + textwrap.dedent(declarations).replace('PKG', module))
    model = load(load_config(root))
    return model, source_engine(model), module


SINGLE = '''
@rule('LIMIT', decides='limit', source='assumed: a known boundary', fields={'days': int}, anchor='LIMIT')
def LIMIT(days):
    return days <= 3
LIMIT.rows(row(days=4, expect=False, why='a previously fixed fourth-day error'))
'''


def test_a_later_session_regression_is_found_in_the_real_home(tmp_path):
    model, engine, module = project(tmp_path, 'def accept(days): return days <= 4', SINGLE)
    assert not model.errors
    rule = model.rules['LIMIT']
    result = engine.run_home(rule, rule.homes[0], 'cells')
    assert result['verdict'] == 'red'
    assert 'days=4' in result['red'][0] and 'rule F, code True' in result['red'][0]


def test_every_bound_copy_is_checked(tmp_path):
    extra = ""  # Both source sensors deliberately share LIMIT.
    model, engine, _ = project(tmp_path, 'def accept(days): return days <= 3\ndef second(days): return days <= 4', SINGLE + extra)
    rule = model.rules['LIMIT']
    assert engine.run_home(rule, rule.homes[0], 'cells')['verdict'] == 'ok'
    assert engine.run_home(rule, rule.homes[1], 'cells')['verdict'] == 'red'


@pytest.mark.parametrize('body', ['days=LIMIT_VALUE', 'days=1 + 3', 'days=make_value()', '**dict(days=4)'])
def test_row_computations_are_rejected_before_execution(tmp_path, body):
    text = SINGLE.replace('days=4, expect=False', body + ', expect=False')
    model, _, _ = project(tmp_path, 'def accept(days): return days <= 3', text)
    assert any('must be a literal' in error['msg'] for error in model.errors)


def test_row_reason_and_domain_are_required(tmp_path):
    for text, expected in [(SINGLE.replace("why='a previously fixed fourth-day error'", "why=''"), 'why='),
                           (SINGLE.replace('return days <= 3', 'return True if days <= 3 else None'), 'outside the predicate domain')]:
        model, _, _ = project(tmp_path, 'def accept(days): return days <= 3', text)
        assert any(expected in error['msg'] for error in model.errors)


def test_assumptions_cannot_turn_green(tmp_path):
    model, engine, _ = project(tmp_path, 'def accept(days): return days <= 3', SINGLE)
    result = engine.run_rules(model.rules['LIMIT'])
    assert result['verdict'] == 'grey'
    assert any('assumed' in reason for reason in result['grey'])


@pytest.mark.parametrize('left,right', [
    ('x + y <= 3', 'x + y <= 4'), ('x - y < 3', 'x - y <= 3'),
    ('x + 2*y <= 5', 'x + 2*y <= 6'), ('2*x - y > 1', '2*x - y >= 1'),
    ('x/2 + y <= 4', 'x/2 + y <= 5'), ('x + y >= 2', 'x + y > 2'),
    ('x - y <= -2', 'x - y <= -1'), ('-x + y < 0', '-x + y <= 0'),
])
def test_multifield_linear_conflicts_are_complete(tmp_path, left, right):
    text = f'''\n@rule('A', decides='limit', source='assumed: A', fields={{'x': D, 'y': D}})
def A(x,y): return {left}
@rule('B', decides='limit', source='assumed: B', fields={{'x': D, 'y': D}})
def B(x,y): return {right}
'''
    model, engine, _ = project(tmp_path, '', text)
    assert not model.errors
    result = engine.check_key('limit')
    assert result['label'] == 'complete' and result['conflicts']


@pytest.mark.parametrize('operator', ['<', '<=', '=='])
def test_a_total_key_cannot_hide_a_gap(tmp_path, operator):
    text = f'''\n@rule('A', decides='limit', source='assumed: A', fields={{'x': int}}, total=True)
def A(x): return True if x {operator} 3 else None
'''
    model, engine, _ = project(tmp_path, '', text)
    result = engine.run_rules(model.rules['A'])
    assert result['verdict'] == 'red' and any('gap' in line for line in result['red'])


@pytest.mark.parametrize('override', [True, False])
@pytest.mark.parametrize('operator', ['<', '<=', '=='])
def test_consistent_pairs_and_explicit_overrides(tmp_path, operator, override):
    text = f'''\n@rule('A', decides='limit', source='assumed: A', fields={{'x': int}})
def A(x): return x {operator} 3
@rule('B', decides='limit', source='assumed: B', fields={{'x': int}}, overrides={'("A",)' if override else '()'})
def B(x): return {'True' if override else 'x ' + operator + ' 3'}
'''
    model, engine, _ = project(tmp_path, '', text)
    assert not model.errors
    result = engine.check_key('limit')
    assert not result['conflicts']
    assert bool(result['overrides']) == override


@pytest.mark.parametrize('expression', ['x*y <= 3', 'x**2 + y <= 3'])
def test_non_linear_rules_never_read_green(tmp_path, expression):
    text = f'''\n@rule('A', decides='limit', source='assumed: nonlinear', fields={{'x': D, 'y': D}})
def A(x,y): return {expression}
'''
    model, engine, _ = project(tmp_path, '', text)
    result = engine.run_rules(model.rules['A'])
    assert result['verdict'] == 'grey' and result['label'] != 'complete'


def test_predicate_borrowing_project_constant_is_not_independent(tmp_path):
    text = SINGLE.replace("@rule('LIMIT'", "from PKG import LIMIT_VALUE\n@rule('LIMIT'").replace('return days <= 3', 'return days <= LIMIT_VALUE')
    model, engine, _ = project(tmp_path, 'LIMIT_VALUE=3\ndef accept(days): return days <= LIMIT_VALUE', text)
    result = engine.run_rules(model.rules['LIMIT'])
    assert result['verdict'] == 'grey'
    assert any('borrows' in line for line in result['grey'])


def test_binding_never_entered_is_a_failure(tmp_path):
    old = SINGLE + "\n@LIMIT.home('PKG:accept')\ndef mirror(c,fn): return c.days <= 3\n"
    model, _, _ = project(tmp_path, 'def accept(days): return days <= 3', old)
    assert any('Rule.home() call adapters were removed' in e['msg'] and 'rebuild' in e['msg'] for e in model.errors)


def test_zero_realized_sites_are_not_vacuously_live(tmp_path):
    model, engine, _ = project(tmp_path, 'def accept(days): return True', SINGLE)
    result = engine.run_live(model.rules['LIMIT'], model.rules['LIMIT'].homes[0])
    assert result['verdict'] == 'grey' and any('nothing to require' in line for line in result['grey'])


def test_mutation_is_restored_after_liveness(tmp_path):
    model, engine, module = project(tmp_path, 'def accept(days): return days <= 3', SINGLE)
    rule = model.rules['LIMIT']
    function = engine.home_sites(rule.homes[0].target)[0]
    original = function.__code__
    result = engine.run_live(rule, rule.homes[0])
    assert result['verdict'] == 'ok' and result['k'] == result['n'] > 0
    assert function.__code__ is original and function(4) is False


@pytest.mark.parametrize('expression', ['x <= -3', 'x != 3', 'x > 3'])
def test_three_more_consistent_pairs(tmp_path, expression):
    text = f'''\n@rule('A', decides='same', source='assumed: A', fields={{'x': int}})
def A(x): return {expression}
@rule('B', decides='same', source='assumed: B', fields={{'x': int}})
def B(x): return {expression}
'''
    model, engine, _ = project(tmp_path, '', text)
    assert not model.errors
    result = engine.check_key('same')
    assert result['label'] == 'complete' and not result['conflicts']


def test_unreached_second_site_is_not_a_false_green(tmp_path):
    code = '''
    def accept(days):
        if days <= 3:
            return True
        return False
        if days > 99:
            return True
    '''
    model, engine, _ = project(tmp_path, code, SINGLE)
    result = engine.run_live(model.rules['LIMIT'], model.rules['LIMIT'].homes[0])
    assert result['verdict'] == 'grey'
    assert any('unreached site' in line for line in result['grey'])


def test_a_borrowed_distinct_adapter_cannot_prove_a_constant_answer(tmp_path):
    # The retired route is rejected; no adapter is borrowed to fabricate evidence.
    extra = "\n@distinct('LIMIT','PKG:always',why='another decision',source='assumed: test')\ndef mirror(c,fn): return fn(c.days)\n"
    model, _, _ = project(tmp_path, 'def accept(days): return days <= 3\ndef always(days): return True', SINGLE + extra)
    assert any('call adapters were removed' in e['msg'] and 'rebuild' in e['msg'] for e in model.errors)


def test_a_distinct_checks_the_other_nodes_own_threshold(tmp_path):
    extra = "\ndistinct('PKG:accept','LATER',why='another decision',source='assumed: test')\n"
    model, engine, _ = project(tmp_path, 'def accept(days): return days <= 3\ndef later(days): return days <= 30', SINGLE + extra)
    from flowguard.intent.differences import anchor_distinct
    result=anchor_distinct(model.cfg.root,model.distincts[0],index=model.anchor_index)
    assert result['status']=='ok' and result['changed']>0 and result['complete']




@pytest.mark.parametrize('value,expected', [('open', 'ok'), ('held', 'red')])
def test_declared_allowed_states_against_real_writers(tmp_path, value, expected):
    code = f'class Hire:\n    def create(self): self.status = {value!r}\n'
    text = '''
    from flowguard.intent import states
    states('PKG:Hire.status', ['open', 'returned'], source='doc policy.txt "Only open and returned"')
    '''
    model, _, _ = project(tmp_path, code, text)
    cfg = model.cfg
    (cfg.root / 'policy.txt').write_text('Only open and returned\n')
    cfg.authority_docs = ['policy.txt']
    result = Engine(model).run_states(next(iter(model.states.values())))
    assert result['verdict'] == expected
    if expected == 'red':
        assert 'held' in result['red'][0]


def test_unmodelled_status_writes_do_not_create_rules(tmp_path):
    model, _, _ = project(tmp_path, "class Hire:\n def create(self): self.status='held'", '')
    assert model.declared_items() == [] and not model.states


def test_structure_rule_turns_a_skip_into_a_failure(tmp_path):
    code = "def work():\n    pytest.skip('do not conceal a missing behavior')\n"
    text = '''
    from flowguard.intent import structure_rule
    @structure_rule('NO_SKIP', source='doc policy.txt "Tests must not skip"')
    def no_skip(graph):
        return [call for call in graph.calls() if call['text'].endswith('.skip')]
    '''
    model, _, _ = project(tmp_path, code, text)
    (model.cfg.root / 'policy.txt').write_text('Tests must not skip\n')
    model.cfg.authority_docs = ['policy.txt']
    result = Engine(model).run_structure(model.structures['NO_SKIP'])
    assert result['verdict'] == 'red' and 'NO_SKIP' in result['red'][0]


@pytest.mark.parametrize('decoration', ['classmethod', 'staticmethod'])
def test_method_homes_keep_their_real_binding(tmp_path, decoration):
    parameters = 'cls, days' if decoration == 'classmethod' else 'days'
    code = f'class Policy:\n    @{decoration}\n    def accept({parameters}): return days <= 3\n'
    text = SINGLE.replace('PKG:accept', 'PKG:Policy.accept')
    model, engine, _ = project(tmp_path, code, text)
    rule = model.rules['LIMIT']
    result = engine.run_home(rule, rule.homes[0], 'cells')
    # Design 4.5/6.4 excludes methods from sealed comparisons; no false agreement.
    assert result['verdict'] == 'grey' and result['entered'] is False
    assert result['red'] == []
    assert result['grey'] == ['not a module-level function -> strengthen or split the lower contract']


@pytest.mark.parametrize('imports,call', [
    ('from flowguard.intent import row as case', 'case'),
    ('import flowguard.intent as fg', 'fg.row'),
    ('import flowguard.intent', 'flowguard.intent.row'),
    ('from flowguard import intent as fg', 'fg.row'),
    ('import flowguard.intent as fg\ncase = fg.row', 'case'),
])
def test_row_alias_cannot_turn_a_computation_into_a_literal(tmp_path, imports, call):
    declaration = imports + '\n' + SINGLE.replace('row(days=4', call + '(days=int("4")')
    model, _, _ = project(tmp_path, 'def accept(days): return days <= 3', declaration)
    assert any('must be a literal' in error['msg'] for error in model.errors)


def test_a_computed_row_from_an_outside_helper_is_refused(tmp_path):
    # The helper's function body is intentionally outside the intent AST.
    code = '''
    from flowguard.intent import row
    def make(): return row(days=int('4'), expect=False, why='computed outside')
    def accept(days): return days <= 3
    '''
    text = SINGLE.replace("LIMIT.rows(row(days=4, expect=False, why='a previously fixed fourth-day error'))",
                          'from PKG import make\nLIMIT.rows(*[make()])')
    model, _, _ = project(tmp_path, code, text)
    assert any('verified literal' in error['msg'] for error in model.errors)

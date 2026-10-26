"""Finite test positions, indivisible units and deterministic file limits."""
from pathlib import Path
import json,runpy
from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory
from flowguard.map.tree import build_tree
from flowguard.map.testtree import test_functions as functions,resolve_test_anchor,test_positions as positions,test_units as units,test_file_findings as findings


def fixture(root):
    base=Path(__file__).parents[1]/'.flowguard'
    path=base/'target/models/_testtree_fixture.py'
    if not path.exists():path=base/'models/_testtree_fixture.py'
    data,nodeids=runpy.run_path(str(path))['fixture'](root)
    inv=build_inventory(root,DEFAULT_IGNORE,write_cache=False)
    return data,nodeids,inv,build_tree(root,data,inv)


def test_unittest_and_same_file_base_classes_count():
    text='''import unittest
class Base(unittest.TestCase):
    def test_base(self): pass
class Suite(Base):
    def test_own(self): pass
class Helper:
    def test_inherited(self): pass
class TestChild(Helper): pass
'''
    assert set(functions(text))=={'Base.test_base','Suite.test_base','Suite.test_own','TestChild.test_inherited'}


def test_bare_method_tested_by_resolves_by_suffix(tmp_path):
    path=tmp_path/'test_case.py';path.write_text('import unittest\nclass Suite(unittest.TestCase):\n    def test_value(self): pass\n')
    assert resolve_test_anchor(path,'test_value')=='Suite.test_value'
    assert resolve_test_anchor(path,'Suite::test_value[case]')=='Suite.test_value'


def test_positions_on_a_fixture_tree(tmp_path):
    data,nodeids,inv,tree=fixture(tmp_path)
    assert tuple(positions(tmp_path,data,inv,tree,nodeids).values())==('A','A','system','other')
    path=tmp_path/'tests/test_extra.py';path.write_text('import a,b\ndef test_free(): assert True\n')
    node='tests/test_extra.py::test_free'
    # Equal import evidence follows the map order; an explicit listing takes precedence.
    inv=build_inventory(tmp_path,DEFAULT_IGNORE,write_cache=False)
    assert positions(tmp_path,data,inv,tree,[node])[node]=='core'
    data['components'][1]['tests'].append('tests/test_extra.py')
    assert positions(tmp_path,data,inv,tree,[node])[node]=='other'
    data['components'][0]['tests'].append('tests/test_extra.py')
    assert positions(tmp_path,data,inv,tree,[node])[node]=='core'
    path.write_text('def test_free(): assert True\n');inv=build_inventory(tmp_path,DEFAULT_IGNORE,write_cache=False)
    data['components'][0]['tests'].remove('tests/test_extra.py');data['components'][1]['tests'].remove('tests/test_extra.py')
    assert positions(tmp_path,data,inv,tree,[node])[node]=='system'


def test_mixed_file_and_large_file_are_named(tmp_path):
    from flowguard.map.lint import apply_accepted_debts
    from flowguard.map.check import run_check
    data,nodeids,inv,tree=fixture(tmp_path)
    rows=findings(tmp_path,data,inv,tree)
    mixed=[row for row in rows if row.code=='test_file_mixes_models']
    large=[row for row in rows if row.code=='large_test_file']
    assert len(mixed)==2 and all(row.level=='warn' for row in mixed)
    assert mixed[0].message=="tests/test_mix.py: move A's 3 bound test(s) to tests/test_A.py (6 test functions in the file; split before 6 per subtree)"
    assert len(large)==1 and large[0].message=='tests/test_big.py: 41 test functions (soft limit 40; split before 60); split it by model: - bound; 41 unbound (move each by the split rule of references/routes.md#Split a test file)'
    debts=[dict(code=row.code,component=row.component,reason='finite fixture') for row in rows]
    assert all(row.level=='info' for row in apply_accepted_debts(rows,debts)[0])
    # Both unrelated roots now bind six functions; the size file also crosses 60.
    mix=tmp_path/'tests/test_mix.py'
    mix.write_text('import a,b\n'+''.join(f'def test_{side}_{index}(): assert {side}.run()=="ready"\n' for side in ('a','b') for index in range(6)))
    for mid,side in (('A','a'),('B','b')):
        path=tmp_path/'.flowguard/models'/(mid+'.py');source=path.read_text();source=source.replace(repr([f'tests/test_mix.py:test_{side}_{i}' for i in range(3)])[1:-1],repr([f'tests/test_mix.py:test_{side}_{i}' for i in range(6)])[1:-1]);path.write_text(source)
    big=tmp_path/'tests/test_big.py';big.write_text(''.join(f'def test_big_{i}(): assert True\n' for i in range(61)))
    inv=build_inventory(tmp_path,DEFAULT_IGNORE,write_cache=False);tree=build_tree(tmp_path,data,inv)
    rows=findings(tmp_path,data,inv,tree)
    assert {row.code for row in rows if row.level=='error'}=={'large_test_file','test_file_mixes_models'}
    assert all(row.level=='error' for row in apply_accepted_debts(rows,debts)[0])
    data['accepted_debts']=debts
    assert any(row.level=='error' and row.code=='large_test_file' for row in run_check(tmp_path,data,inv))
    (tmp_path/'.flowguard/cache').mkdir(exist_ok=True)
    from flowguard.map.common import content_digest
    record={'schema':'flowguard.test_durations.v1','files':{'tests/test_big.py':content_digest(big)},'seconds':{'tests/test_big.py::test_big_0':61}}
    (tmp_path/'.flowguard/cache/test-durations.json').write_text(json.dumps(record))
    assert any(row.level=='info' and row.message=='tests/test_big.py: 61.0s (advice limit 60s); a split by model usually helps' for row in findings(tmp_path,data,inv,tree))
    mix.write_text('def test_clean(): assert True\n');big.write_text('def test_clean(): assert True\n')
    inv=build_inventory(tmp_path,DEFAULT_IGNORE,write_cache=False);tree=build_tree(tmp_path,data,inv)
    assert not findings(tmp_path,data,inv,tree)


def _split_project(root):
    (root/'.flowguard/models').mkdir(parents=True)
    (root/'tests').mkdir()
    (root/'native.py').write_text('def a(): return True\ndef b(): return True\n')
    (root/'tests/test_M.py').write_text('from native import a,b\ndef test_a(): assert a()\ndef test_b(): assert b()\n')
    def model(mid,rules):
        return '''from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact,load_anchor
from pathlib import Path
MODEL_ID=MID
PARENT='app'
IMPLEMENTED_BY=ANCHORS
TESTED_BY=BINDINGS
class Step:
    name='Run'
    def __init__(self,bad=''):self.bad=bad
    def apply(self,event,state):return (FunctionResult(event,(self.bad!='a',self.bad!='b')),)
RULES=RULE_TABLE
def make(bad=''):return Explorer(Workflow((Step(bad),)),((True,True),),('run',),invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer():return make()
def broken_variants():return VARIANTS
def conformance():return CodeFactsReport(tuple(Fact(name,load_anchor(anchor,root=Path.cwd())()) for name,anchor in IMPLEMENTED_BY.items()))
'''.replace('MID',repr(mid)).replace('ANCHORS',repr({name:'native.py:'+name for name in rules})).replace('BINDINGS',repr({name:['tests/test_M.py:test_'+name] for name in rules})).replace('RULE_TABLE','('+','.join(f'Invariant("{name}","{name} stays true",lambda s,t:s[{index}])' for name,index in (('a',0),('b',1)) if name in rules)+',)').replace('VARIANTS','{'+','.join(repr('bad_'+name)+':make('+repr(name)+')' for name in rules)+'}')
    (root/'.flowguard/models/M.py').write_text(model('M',('a','b')))
    data=dict(schema='flowguard.map.v1',components=[dict(id='app',files=['native.py'],summary='Two predicates',responsibilities=['Judge predicates'],models=[],tests=['tests/test_*.py'],status='draft')])
    (root/'.flowguard/map.json').write_text(json.dumps(data))
    return model


def test_one_to_one_test_file_splits_with_its_model(tmp_path):
    from flowguard.map.target import main,check_target
    model=_split_project(tmp_path)
    assert main(['--root',str(tmp_path),'start','Split aspects'])==0
    target=tmp_path/'.flowguard/target'
    data=json.loads((target/'map.json').read_text());data['remove']=['model:M'];(target/'map.json').write_text(json.dumps(data))
    for name in ('a','b'):(target/'models'/(name+'.py')).write_text(model(name,(name,)))
    report=check_target(tmp_path)
    todo=[row for row in report.todos if row.code=='test_file_not_split']
    assert len(todo)==1 and 'a 1 -> tests/test_a.py' in todo[0].message and 'b 1 -> tests/test_b.py' in todo[0].message
    assert main(['--root',str(tmp_path),'check'])==3
    assert main(['--root',str(tmp_path),'promote'])==1
    for name in ('a','b'):
        (tmp_path/'tests'/('test_'+name+'.py')).write_text(f'from native import {name}\ndef test_{name}(): assert {name}()\n')
        path=target/'models'/(name+'.py');path.write_text(path.read_text().replace('tests/test_M.py','tests/test_'+name+'.py'))
    (tmp_path/'tests/test_M.py').write_text('from native import a,b\ndef test_shared(): assert a() and b()\n')
    for name in ('a','b'):
        path=target/'models'/(name+'.py');source=path.read_text().replace("'tests/test_"+name+".py:test_"+name+"'","'tests/test_"+name+".py:test_"+name+"','tests/test_M.py:test_shared'");path.write_text(source)
    assert not any(row.code=='test_file_not_split' for row in check_target(tmp_path).todos)


def test_component_tests_line_counts_here_and_below(tmp_path):
    from flowguard.map.views import render_show
    data,nodeids,inv,tree=fixture(tmp_path)
    text=render_show(tmp_path,data,inv,component='core',detail=False,budget=20000)
    assert 'functions here and below (bound ' in text and 'bindable:' not in text
    assert 'tests/test_tree.py (3 bound)' in text


def test_large_test_seconds_is_validated():
    from flowguard.map.mapfile import validate_map
    base={'schema':'flowguard.map.v1','components':[]}
    for value in (0,-1,'60',True,float('inf'),float('nan')):
        assert 'large_test_seconds must be a positive number' in validate_map(dict(base,large_test_seconds=value))
    assert not validate_map(dict(base,large_test_seconds=.01))

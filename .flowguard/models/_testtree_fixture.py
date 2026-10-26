"""A finite model tree with native test calls and no imported project models."""
from pathlib import Path
import json

def write(root,path,text):
    destination=root/path;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(text)


def model(mid,parent,path,bindings,*,child=False,parent_model=False):
    declarations='    value:str=""\n'+('    receipt:str=""\n' if parent_model else '')
    return f'''from dataclasses import dataclass
from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact,load_anchor
from pathlib import Path
MODEL_ID={mid!r}
PARENT={parent!r}
IMPLEMENTED_BY={{'Run':{(path+':run')!r}}}
TESTED_BY={{'safe':{bindings!r}}}
OUTPUTS={{'value':('ready',)}}
HANDOFF={ {'child':{'value':'receipt'}} if parent_model else {}!r}
KEEPS={('value',) if parent_model else ()!r}
@dataclass(frozen=True)
class State:
{declarations}class Step:
    name='Run'
    reads=()
    writes={('value','receipt') if parent_model else ('value',)!r}
    def __init__(self,bad=False):self.bad=bad
    def apply(self,event,state):
        value='bad' if self.bad else 'ready'
        return (FunctionResult(value,State({ 'value,value' if parent_model else 'value'})),)
RULES=(Invariant('safe','output stays ready',lambda s,t:s.value in ('','ready')),)
def make(bad=False):return Explorer(Workflow((Step(bad),)),(State(),),('ready',),invariants=RULES,max_sequence_length=1,progress_steps=0)
def build_explorer():return make()
def broken_variants():return {{'bad':make(True)}}
def conformance():return CodeFactsReport((Fact('native',load_anchor(IMPLEMENTED_BY['Run'],root=Path.cwd())()=='ready'),))
'''


def fixture(root):
    root=Path(root)
    write(root,'a.py','import child\ndef run(): return child.run()\n')
    write(root,'child.py','def run(): return "ready"\n')
    write(root,'b.py','def run(): return "ready"\n')
    source='''import a,b,child
def test_bound(): assert a.run()=='ready'
def test_parent_child(): assert a.run()==child.run()
def test_unrelated(): assert a.run()==b.run()
def test_free(): assert b.run()=='ready'
'''
    write(root,'tests/test_tree.py',source)
    write(root,'tests/test_mix.py','import a,b\n'+''.join(f'def test_{side}_{index}(): assert {side}.run()=="ready"\n' for side in ('a','b') for index in range(3)))
    write(root,'tests/test_big.py',''.join(f'def test_big_{index}(): assert True\n' for index in range(41)))
    for mid,parent,path,bindings,options in (
        ('A','core','a.py',['tests/test_tree.py:test_bound','tests/test_tree.py:test_parent_child','tests/test_tree.py:test_unrelated']+[f'tests/test_mix.py:test_a_{i}' for i in range(3)],{'parent_model':True}),
        ('child','A','child.py',['tests/test_tree.py:test_parent_child'],{}),
        ('B','other','b.py',['tests/test_tree.py:test_unrelated']+[f'tests/test_mix.py:test_b_{i}' for i in range(3)],{})):
        write(root,'.flowguard/models/'+mid+'.py',model(mid,parent,path,bindings,**options))
    data=dict(schema='flowguard.map.v1',project='tree',layers=['code'],components=[dict(id=cid,layer='code',summary=cid,responsibilities=[cid],files=paths,tests=tests,models=[],status='draft',depends_on=deps) for cid,paths,tests,deps in (
        ('core',['a.py','child.py'],['tests/test_tree.py','tests/test_mix.py','tests/test_big.py'],[]),
        ('other',['b.py'],['tests/test_tree.py','tests/test_mix.py'],[]))])
    write(root,'.flowguard/map.json',json.dumps(data))
    nodeids=tuple('tests/test_tree.py::'+name for name in ('test_bound','test_parent_child','test_unrelated','test_free'))
    return data,nodeids


def runner_fixture(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    for name in ('one','two'):
        write(root,'tests/test_'+name+'.py','def test_a(): assert True\ndef test_b(): assert True\n')
    return root


def runner_cases(root):
    from flowguard.pytest_shards_cli import build_parser,run
    root=runner_fixture(root)
    args=build_parser().parse_args(['--root',str(root),'--shards','2'])
    first_code,first=run(args)
    record=root/'.flowguard/cache/test-durations.json'
    first_record=record.exists()
    second_code,second=run(args)
    before=record.read_bytes() if record.exists() else None
    write(root,'tests/test_broken.py','def test_broken(:\n')
    blocked_code,blocked=run(args)
    return dict(first=first,second=second,blocked=blocked,first_code=first_code,second_code=second_code,blocked_code=blocked_code,
                recorded=first_record,preserved=before==(record.read_bytes() if record.exists() else None))

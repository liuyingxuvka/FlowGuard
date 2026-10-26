"""Finite source-backed graph fixtures; never import these project models."""
from pathlib import Path
import json,runpy

def write(root,path,text):
    destination=root/path;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(text)

def helpers():
    path=Path(__file__).parent/'_target_fixture.py'
    if not path.exists():path=Path(__file__).parents[2]/'models/_target_fixture.py'
    return runpy.run_path(str(path))

def model(mid, *, parent='extra', fields=('value',), outputs=None, handoff=None, reads=(), keeps=(), dispatch=None):
    declarations=''.join('    '+field+':str=""\n' for field in fields)
    values=','.join('value' for field in fields)
    return f'''raise AssertionError("a relation view imported a model")
from dataclasses import dataclass
from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
MODEL_ID={mid!r}
PARENT={parent!r}
IMPLEMENTED_BY={{"Run":"extra.py:{mid.lower()}"}}
TESTED_BY={{}}
OUTPUTS={outputs if outputs is not None else {'value':('ready',)}!r}
HANDOFF={handoff or {}!r}
READS_PARENT={reads!r}
KEEPS={keeps!r}
@dataclass(frozen=True)
class State:
{declarations}class Mark:
    name="Run"
    reads=()
    writes={fields!r}
    def __init__(self,bad=False):self.bad=bad
    def apply(self,event,state):
        value="bad" if self.bad else "ready"
        return (FunctionResult(value,State({values})),)
RULE=Invariant("value_safe","value remains ready",lambda s,t:s.value in ("","ready"))
def make(bad=False):return Explorer(Workflow((Mark(bad),)),(State(),),("ready",),invariants=(RULE,),max_sequence_length=1,progress_steps=0)
def build_explorer():return make()
def broken_variants():return {{"bad":make(True)}}
def conformance():return True
'''+('DISPATCH='+repr(dispatch)+'\n' if dispatch is not None else '')


def fixture(root):
    root=Path(root);data=helpers()['make_port_project'](root)
    sources=[]
    def add(mid, **options):
        write(root,'.flowguard/models/'+mid+'.py',model(mid,**options))
        sources.append('def '+mid.lower()+'(value="ready"): return value\n')
    add('W')
    add('P');add('K1',outputs={},handoff={'P':{'value':'value'}});add('K2',outputs={},handoff={'P':{'value':'value'}})
    add('Q');add('Q8');add('R');add('KR',outputs={},handoff={'R':{'value':'value'}})
    add('U',fields=('value','v1','v2','v3'),outputs={'v1':('ready',)},handoff={name:{'value':'v'+str(index)} for index,name in enumerate(('C1','C2','C3'),1)})
    for name in ('C1','C2','C3'):add(name,parent='U',reads=('value',))
    add('KU',outputs={},handoff={'U':{'v1':'value'}})
    add('V',outputs={},handoff={'T':{'value':'value'}});add('T',parent='V');add('KT',outputs={},handoff={'T':{'value':'value'}})
    add('cmd',fields=('mode','a','b'),outputs={},handoff={'a':{'value':'a'},'b':{'value':'b'}},keeps=('mode',),dispatch={'mode':{'x':'a','y':'b'}})
    # The branch model's real State and steps expose exactly one selected branch.
    path=root/'.flowguard/models/cmd.py';text=path.read_text().replace('s.value in ("","ready")','s.a in ("","ready") and s.b in ("","ready")')
    text=text.replace('State(value,value,value)','State(event,"ready" if event=="x" else "","ready" if event=="y" else "")').replace('(State(),),("ready",)','(State(),),("x","y")')
    path.write_text(text)
    add('a',parent='cmd');add('b',parent='cmd')
    write(root,'extra.py',''.join(sources)+'''def k1(value="ready"): return p()
def k2(value="ready"): return p()
def kr(value="ready"): return r()
def ku(value="ready"): return u()
def v(value="ready"): return t()
def kt(value="ready"): return t()
def u(value="ready"): return c1(value) if c2(value)==c3(value) else "bad"
def cmd(mode="x"): return a() if mode=="x" else b()
''')
    caller='from extra import q,q8,r,t\n'
    # R has six external callers and its consumer; T has six plus V and KT.
    for target,count in (('q',16),('q8',8),('r',6),('t',6)):
        caller+=''.join(f'def call_{target}_{index}(): return {target}()\n' for index in range(count))
    write(root,'callers.py',caller)
    data['components'] += [dict(id='extra',layer='engine',summary='Finite graph results',responsibilities=['produce and consume graph results'],files=['extra.py'],tests=[],models=[],depends_on=[],status='draft'),dict(id='clients',layer='interface',summary='Call result producers',responsibilities=['call the result producers'],files=['callers.py'],tests=[],models=[],depends_on=['extra'],status='draft')]
    write(root,'.flowguard/map.json',json.dumps(data))
    return data


def field_fixture(root):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    write(root,'writer.py','def write(row):\n    row["record_code"]="ready"\n    return row\nclass Store:\n    def change(self): self.status="ready"\n')
    write(root,'reader.py','def read(row): return row["record_code"]\n')
    write(root,'tests/test_state.py','from writer import Store\ndef test_status():\n    store=Store();store.change();assert store.status=="ready"\n')
    source=model('status_model',parent='writer',fields=('status',),outputs={'status':('ready',)})
    source=source.replace('raise AssertionError("a relation view imported a model")','from pathlib import Path\nPath('+repr(str(root/'model_imported.marker'))+').write_text("imported")')
    source=source.replace('"extra.py:status_model"','"writer.py:Store.change"').replace('TESTED_BY={}','TESTED_BY={"status_visible":["tests/test_state.py:test_status"]}').replace('reads=()','reads=("status",)').replace('"value_safe","value remains ready"','"status_visible","status remains ready"').replace('s.value in','s.status in').replace('"bad":make(True)','"status_lost":make(True)')
    write(root,'.flowguard/models/status_model.py',source)
    data=dict(schema='flowguard.map.v1',project='fields',layers=['code'],components=[dict(id=name,layer='code',summary=name,responsibilities=[name],state=['status lifecycle','record_code'] if name=='writer' else ['record_code'],files=[name+'.py'],entrypoints=[],tests=['tests/test_state.py'] if name=='writer' else [],models=[],depends_on=[],status='draft') for name in ('writer','reader')])
    write(root,'.flowguard/map.json',json.dumps(data));return data

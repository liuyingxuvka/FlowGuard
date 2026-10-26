"""Native finite projects for literal consumers and removal/move warnings."""
import json
import subprocess
from pathlib import Path
from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory
from flowguard.map.impact import compute_impact,render_impact

def write(root,path,text):
    target=root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(text)

CONTRACT='''from dataclasses import dataclass
from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
MODEL_ID="policy"
PARENT="producer"
IMPLEMENTED_BY={"Read":"producer.py:emit"}
TESTED_BY={"safe":["tests/test_result.py:test_result"]}
@dataclass(frozen=True)
class State:
    retained:str=""
class Emit:
    name="Emit"
    def __init__(self,bad=False): self.bad=bad
    def apply(self,event,state): return (FunctionResult("stale",State("bad" if self.bad else "stale")),)
RULE=Invariant("safe","the emitted result stays readable",lambda s,t:s.retained!="bad")
def make(bad=False): return Explorer(Workflow((Emit(bad),)),(State(),),("tick",),invariants=(RULE,),max_sequence_length=1,progress_steps=0)
def build_explorer(): return make()
def broken_variants(): return {"bad":make(True)}
def conformance():
    from pathlib import Path
    from flowguard.map.facts import load_anchor,CodeFactsReport,Fact
    actual=load_anchor(IMPLEMENTED_BY["Read"],root=Path.cwd())(*NATIVE_ARGS)
    return CodeFactsReport((Fact("native_result",actual==NATIVE_EXPECTED,repr(actual)),))
NATIVE_ARGS=()
NATIVE_EXPECTED="stale"
'''

def fixture(root):
    write(root,'producer.py','def emit(): return "stale"\n')
    write(root,'consumer.py','def use(value): return value == "stale"\ndef fold(value): return value\n')
    write(root,'tests/test_result.py','from producer import emit\ndef test_result(): assert emit()=="stale"\n')
    write(root,'.flowguard/models/policy.py',CONTRACT)
    consumer = CONTRACT.replace('MODEL_ID="policy"','MODEL_ID="consumer_model"').replace('PARENT="producer"','PARENT="consumer"').replace('"producer.py:emit"','"consumer.py:use"').replace('NATIVE_ARGS=()','NATIVE_ARGS=("stale",)').replace('NATIVE_EXPECTED="stale"','NATIVE_EXPECTED=True')
    consumer += '\ndef code(value): return value=="stale"\n'
    write(root,'.flowguard/models/consumer_model.py',consumer)
    data=dict(schema='flowguard.map.v1',project='literal-consumers',layers=['logic'],components=[dict(id=cid,layer='logic',summary=cid,responsibilities=[cid],files=[cid+'.py'],tests=['tests/test_result.py'] if cid=='producer' else [],models=[],depends_on=[],status='draft') for cid in ('producer','consumer')])
    write(root,'.flowguard/map.json',json.dumps(data))
    for args in (('init','-q'),('add','.'),('-c','user.name=FlowGuard','-c','user.email=model@example.invalid','commit','-qm','baseline')):
        subprocess.run(['git',*args],cwd=root,check=True,capture_output=True)
    return data

def native_case(root,case):
    data=fixture(root)
    if case=='literal':
        write(root,'producer.py','def emit(): return "stale_component"\n')
        changed=['producer.py']
    else:
        path=root/'.flowguard/models/policy.py';old=path.read_text()
        text=old.replace('invariants=(RULE,)','invariants=()').replace('return {"bad":make(True)}','return {}').replace('TESTED_BY={"safe":["tests/test_result.py:test_result"]}','TESTED_BY={}')
        path.write_text(text)
        changed=['.flowguard/models/policy.py']
        if case=='moved':
            recipient=old.replace('MODEL_ID="policy"','MODEL_ID="recipient"').replace('PARENT="producer"','PARENT="consumer"').replace('"producer.py:emit"','"consumer.py:fold"').replace('NATIVE_ARGS=()','NATIVE_ARGS=("stale",)')
            write(root,'.flowguard/models/recipient.py',recipient)
            changed.append('.flowguard/models/recipient.py')
        # Target rules use the same real before/after model bytes, without Git.
        from flowguard.map.facets import target_goal_rules
        from flowguard.map.targetfile import load_target,build_target_view
        from flowguard.map.mapfile import load_map
        planned=root/'.flowguard/target';planned.mkdir();(planned/'models').mkdir()
        write(root,'.flowguard/target/models/policy.py',text)
        path.write_text(old)
        write(root,'.flowguard/target/map.json',json.dumps(dict(schema='flowguard.target.v1',goal='name removed promises',components=[],flows=[],remove=[])))
        target=load_target(root);target_goal_rules(root,target,build_target_view(root,load_map(root),target))
        path.write_text(text)
        import shutil
        shutil.rmtree(planned)
    impact=compute_impact(root,data,build_inventory(root,DEFAULT_IGNORE,write_cache=False),changed,base='HEAD')
    return impact,render_impact(impact)

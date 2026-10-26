"""Small finite fixtures exercise real sequence and advice limits."""
from pathlib import Path
import json

def fixture(root,events=1,length=1,seconds=10,rules=1):
    root=Path(root);(root/'.flowguard/models').mkdir(parents=True,exist_ok=True)
    (root/'native.py').write_text('def identity(value): return value\n')
    source='''from flowguard import FunctionResult,Invariant,Workflow
from flowguard.map.facts import load_anchor,CodeFactsReport,Fact
from flowguard.explorer import Explorer
from pathlib import Path
MODEL_ID='sized'
PARENT='app'
IMPLEMENTED_BY={'Step':'native.py:identity'}
TESTED_BY={}
class Step:
    name='Step'
    def __init__(self,bad=False):self.bad=bad
    def apply(self,event,state):return (FunctionResult(event,int(self.bad)),)
RULES=RULE_TABLE
def make(bad=False):return Explorer(Workflow((Step(bad),)),(0,),EVENTS,invariants=RULES,max_sequence_length=LENGTH if not bad else 1,progress_steps=0)
def build_explorer():return make()
def broken_variants():return {'bad':make(True)}
def conformance():return CodeFactsReport((Fact('native',load_anchor(IMPLEMENTED_BY['Step'],root=Path.cwd())(1)==1),))
'''.replace('RULE_TABLE','('+','.join(f'Invariant("rule_{index}","holds",lambda s,t:s==0)' for index in range(rules))+',)').replace('EVENTS',repr(tuple(range(events)))).replace('LENGTH',str(length))
    (root/'.flowguard/models/sized.py').write_text(source)
    data=dict(schema='flowguard.map.v1',project='size',large_model_seconds=seconds,components=[dict(id='app',files=['native.py'],summary='Compute one identity',responsibilities=['Compute identity'],tests=[],models=[],depends_on=[],status='draft')])
    (root/'.flowguard/map.json').write_text(json.dumps(data))
    return data

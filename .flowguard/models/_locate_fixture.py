"""A static lookup fixture with a shallow owner and a deeper reacher; models must not import."""
import json
from pathlib import Path
from contextlib import redirect_stdout,redirect_stderr
from io import StringIO

def fixture(root):
    root.mkdir(parents=True,exist_ok=True)
    files={'api.py':'def owned(): return 1\ndef helper(): return owned()\ndef wrapper(): return helper()\ndef unowned(): return 0\n',
           'tests/test_api.py':'from api import owned\ndef test_bound(): assert owned()==1\ndef test_unbound(): assert owned()==1\ndef test_plain(): assert True\n'}
    template='''raise AssertionError("a lookup imported a model")
from dataclasses import dataclass
from flowguard import FunctionResult,Invariant,Workflow
from flowguard.explorer import Explorer
MODEL_ID="owner"
PARENT="app"
IMPLEMENTED_BY={"Run":"api.py:owned"}
TESTED_BY={"safe":["tests/test_api.py:test_bound"]}
HANDOFF={"deeper":{"step":"step"}}
OUTPUTS={}
@dataclass(frozen=True)
class State:
    step:str=""
class Mark:
    name="Run"
    reads=()
    writes=("step",)
    def __init__(self,bad=False): self.bad=bad
    def apply(self,event,state): return (FunctionResult("bad" if self.bad else "done",State("bad" if self.bad else "done")),)
RULE=Invariant("safe","the owned operation returns safely",lambda s,t:s.step in ("","done"))
def make(bad=False): return Explorer(Workflow((Mark(bad),)),(State(),),("run",),invariants=(RULE,),max_sequence_length=1,progress_steps=0)
def build_explorer(): return make()
def broken_variants(): return {"bad":make(True)}
def conformance(): return True
'''
    files['.flowguard/models/owner.py']=template
    child=template.replace('MODEL_ID="owner"','MODEL_ID="deeper"').replace('PARENT="app"','PARENT="owner"').replace('"api.py:owned"','"api.py:wrapper"').replace('TESTED_BY={"safe":["tests/test_api.py:test_bound"]}','TESTED_BY={}').replace('HANDOFF={"deeper":{"step":"step"}}','HANDOFF={}').replace('OUTPUTS={}','OUTPUTS={"step":("done",)}')
    files['.flowguard/models/deeper.py']=child
    data=dict(schema='flowguard.map.v1',project='lookup',layers=['code'],components=[dict(id='app',layer='code',summary='owned operations',responsibilities=['own operations'],files=['api.py'],entrypoints=['api.py:owned'],tests=['tests/test_api.py'],models=[],depends_on=[],status='draft')])
    files['.flowguard/map.json']=json.dumps(data)
    for relative,text in files.items():
        path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    return data

CASES={'owned':'api.py:owned','reached':'api.py:helper','unowned':'api.py:unowned','bound':'tests/test_api.py::test_bound','unbound':'tests/test_api.py::test_unbound','file':'tests/test_api.py','unknown':'api.py:missing'}

def observe(root,case):
    from flowguard.__main__ import main
    output=StringIO();errors=StringIO()
    with redirect_stdout(output),redirect_stderr(errors):
        status=main(['read','--root',str(root),'--find',CASES[case]])
    return status,output.getvalue()+errors.getvalue()

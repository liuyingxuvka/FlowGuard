"""Model-file edits have their own target guard, independent of component fingerprints."""
from dataclasses import dataclass,replace
from pathlib import Path
from tempfile import TemporaryDirectory
from contextlib import redirect_stdout,redirect_stderr
from io import StringIO
import json
from flowguard import FunctionResult,Invariant,InvariantResult,Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport,Fact
MODEL_ID='model_edits'
PARENT='map-check'
IMPLEMENTED_BY={'ModelEdits':'flowguard/map/check.py:model_edit_findings'}
USES={'Confirm':'flowguard/map/cli.py:cmd_confirm','TargetAdd':'flowguard/map/target.py:add_to_target'}
TESTED_BY={'model_edited_outside_target_is_named':['tests/test_flowguard_map.py:test_map_check_names_model_edited_outside_target']}
@dataclass(frozen=True)
class State:
    model_edited:bool=False
    last_report:str=''
class Check:
    name='ModelEdits'
    reads=('model_edited',)
    writes=('model_edited','last_report')
    def __init__(self,bad=False):self.bad=bad
    def apply(self,event,state):
        value=replace(state,model_edited=True,last_report='') if event=='edit' else replace(state,model_edited=False,last_report='') if event=='target' else state if event=='confirm' else replace(state,last_report='model_edited_outside_target' if state.model_edited and not self.bad else 'clean')
        return (FunctionResult(value.last_report,value),)
RULES=(Invariant("model_edited_outside_target_is_named", "model edits need their own target and cannot be silently cleared by confirm",
              lambda s,t: InvariantResult.fail("unplanned model edit was hidden") if s.model_edited and s.last_report
              and s.last_report != "model_edited_outside_target" else InvariantResult.pass_()),)
def make(bad=False):return Explorer(Workflow((Check(bad),)),(State(),),('edit','confirm','check','target'),invariants=RULES,max_sequence_length=3,progress_steps=0)
def build_explorer():return make()
def broken_variants():return {'ignores_in_place_model_edit':make(True)}
def conformance():
    from flowguard.map.check import model_edit_findings
    from flowguard.map.cli import main as map_main
    from flowguard.map.target import main as target_main
    from flowguard.map.common import content_digest
    with TemporaryDirectory(prefix='fg-model-edit-') as directory:
        root=Path(directory);(root/'.flowguard/models').mkdir(parents=True)
        (root/'native.py').write_text('def run(): return True\n')
        logical='.flowguard/models/one.py';path=root/logical
        path.write_text('MODEL_ID="one"\nPARENT="app"\nIMPLEMENTED_BY={"Run":"native.py:run"}\nTESTED_BY={}\ndef build_explorer():pass\ndef conformance():pass\n')
        data=dict(schema='flowguard.map.v1',fingerprint_format=2,model_digests={logical:content_digest(path)},components=[dict(id='app',summary='Compute one value',responsibilities=['Compute value'],files=['native.py'],tests=[],models=[],status='draft')])
        (root/'.flowguard/map.json').write_text(json.dumps(data))
        facts=[]
        facts.append(Fact('unchanged',not model_edit_findings(root,data,'error')))
        path.write_text(path.read_text()+'# changed model\n')
        facts.append(Fact('changed',bool(model_edit_findings(root,data,'error'))))
        with redirect_stdout(StringIO()),redirect_stderr(StringIO()):
            confirmed=map_main(['--root',str(root),'confirm','app'])
        data=json.loads((root/'.flowguard/map.json').read_text())
        facts.append(Fact('confirm_keeps_guard',confirmed==0 and bool(model_edit_findings(root,data,'error'))))
        with redirect_stdout(StringIO()),redirect_stderr(StringIO()):
            started=target_main(['--root',str(root),'start','Plan model edit'])
            added=target_main(['--root',str(root),'add','one'])
        facts.append(Fact('target_owns_edit',started==added==0 and not model_edit_findings(root,data,'error')))
        return CodeFactsReport(tuple(facts))

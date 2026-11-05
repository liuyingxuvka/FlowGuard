"""Default operation observations and real reconciliation of persisted drift."""
import ast
import json
import runpy

import pytest

from flowguard.flow.checks import check_model
from flowguard.flow.model import load_model
from flowguard.flow.native_evidence import evaluate_report

from checkrun import run_check


MODEL = '''from flowguard.flow import Model, need
from flowguard.flow.adapter import fields
m=Model("output",covers=["app.py:Program"])
m.field("n",(0,1),0)
@m.action()
def step(s):
    need(s["n"]==0)
    s["n"]=1
    return "expected"
m.terminal("n",[1])
m.bind_adapter({"system":"app:Program","classes":["app:Program"],"refusal":["app:Refusal"]},
    state=lambda snapshot:{"n":fields(snapshot,names=("n",))["n"]},operations={"step":"step"})
MODEL=m
'''

APP = '''class Refusal(Exception): pass
class Program:
    def __init__(self): self.n=0
    def step(self):
        if self.n!=0: raise Refusal("finished")
        self.n=1
        return "wrong"
'''


def setup(project, *, model=MODEL, app=APP):
    project.file("app.py",app)
    return project.flow("output",model)


def first_drift(project):
    setup(project)
    first=run_check(project.root,"--json")
    assert first.code==1,first.out+first.err
    saved=json.loads((project.root/".flowguard/conflicts.json").read_text())
    entry,=[row for row in saved["conflicts"] if row["kind"]=="MODEL DRIFT"]
    return first,entry


def test_default_clean_model_observes_output_drift_and_persists_only_inputs(project):
    path=setup(project)
    logical=check_model(load_model(path,project.root))
    assert logical.graph.complete and not logical.findings
    first,entry=first_drift(project)
    origin=entry["detail"]["native_origin"]
    assert ast.literal_eval(origin["inputs_literal"])==[
        {"external_input":None,"function_name":"step","function_input":{}}]
    assert origin["code_inputs"]["app.py"] and origin["witness"]["record"].startswith(".flowguard/cache/flow/parts/")
    public,=[row for row in first.data["conflicts"] if row["kind"]=="MODEL DRIFT"]
    assert "trace" not in public["detail"]["native"]
    assert "native_origin" not in public["detail"]
    assert "inputs_literal" not in first.out and "rule_captures" not in first.out


def test_default_clean_model_observes_permit_refuse_divergence(project):
    setup(project,app=APP.replace('self.n=1','raise Refusal("not allowed")'))
    result=run_check(project.root,"--json")
    assert result.code==1,result.out+result.err
    assert any(row["kind"]=="MODEL DRIFT" for row in result.data["conflicts"])


def test_cheap_default_uses_one_enabled_witness_per_operation_not_all_state_calls(project):
    path=setup(project,model=MODEL.replace('m.field("n",(0,1),0)','m.field("n",range(5),0)')
        .replace('@m.action()\ndef step(s):\n    need(s["n"]==0)\n    s["n"]=1\n    return "expected"',
                 '@m.action(n=range(5))\ndef step(s,n):\n    s["n"]=n\n    return "expected"')
        .replace('m.terminal("n",[1])',''),
        app=APP.replace('def step(self):','def step(self,n):').replace('        if self.n!=0: raise Refusal("finished")\n','')
               .replace('self.n=1','self.n=n').replace('"wrong"','"expected"'))
    loaded=load_model(path,project.root)
    report=check_model(loaded)
    assert report.graph.complete and len(report.graph.states)==5 and len(report.graph.calls)==5
    assert not report.findings
    original=loaded.model.adapter_binding.execute
    calls=[]
    def execute(inputs,**kwargs):
        calls.append(tuple(inputs))
        return original(inputs,**kwargs)
    loaded.model.adapter_binding.execute=execute
    evidence=evaluate_report(project.root,report)
    assert evidence["status"]=="conformant",evidence["limits"]
    assert len(calls)==2 and len(calls[0])==0 and len(calls[1])==1
    assert evidence["operation_coverage"]["witness_budget"]==1
    assert evidence["operation_coverage"]["seed"] is None
    assert evidence["operation_coverage"]["model_path"]==".flowguard/flow/output.py"
    assert evidence["operation_coverage"]["witnesses"][0]["production_steps"]==1


def test_never_enabled_operation_receives_a_real_refusal_probe(project):
    path=setup(project,model=MODEL.replace('need(s["n"]==0)','need(False)'),
               app=APP.replace('if self.n!=0','if True'))
    evidence=evaluate_report(project.root,check_model(load_model(path,project.root)))
    coverage=evidence["operation_coverage"]["witnesses"]
    assert coverage[0]["operation"]=="step" and coverage[0]["selection"]=="refusal"
    checked=evidence["checks"][coverage[0]["check"]]
    assert checked["native"]["steps"][-1]["outcome"]=="refusal"


@pytest.mark.parametrize("repair,kind",[("code","code_fixed"),("model","model_corrected")])
def test_real_cli_repairs_old_drift_with_current_oracle_and_frozen_regression(project,repair,kind):
    _,entry=first_drift(project)
    if repair=="code":
        project.file("app.py",APP.replace('"wrong"','"expected"'))
    else:
        project.flow("output",MODEL.replace('return "expected"','return "wrong"'))
    repaired=run_check(project.root,"--json","--max-states","2")
    assert repaired.code==0,repaired.out+repaired.err
    assert any(row["id"]==entry["id"] and row["why"].startswith(kind+":") for row in repaired.data["closed"])
    assert not repaired.data["conflicts"]
    repeated=run_check(project.root,"--json")
    assert repeated.code==0,repeated.out+repeated.err
    # Dropping the now-closed retained-condition input creates the ordinary
    # core cache entry; its next use must be wholly cached.
    cached=run_check(project.root,"--json")
    assert cached.code==0 and all(row["cached"] for row in cached.data["parts"]),cached.out
    # The status route consumes current evidence and must not revive inherited drift.
    from flowguard.__main__ import main
    assert main(["status","--root",str(project.root)])==0
    saved=json.loads((project.root/".flowguard/conflicts.json").read_text())
    assert not saved["conflicts"]
    regression,=(project.root/"tests/flowguard_native").glob("test_*.py")
    assert "max_states=2" in regression.read_text()
    if repair=="code":
        project.file("app.py",APP)
    else:
        project.flow("output",MODEL)
    with pytest.raises(AssertionError,match="native regression"):
        runpy.run_path(str(regression),run_name="__main__")


def test_partial_current_model_cannot_close_repaired_drift(project):
    _,entry=first_drift(project)
    project.file("app.py",APP.replace('"wrong"','"expected"'))
    partial=run_check(project.root,"--json","--max-states","1")
    assert partial.code==1 and not partial.data["complete"],partial.out+partial.err
    assert any(row["id"]==entry["id"] for row in partial.data["conflicts"])
    assert not partial.data["closed"]


def test_old_drift_without_origin_recovers_actual_original_cached_inputs(project):
    _,entry=first_drift(project)
    path=project.root/".flowguard/conflicts.json"
    saved=json.loads(path.read_text())
    del saved["conflicts"][0]["detail"]["native_origin"]
    path.write_text(json.dumps(saved))
    record=project.root/".flowguard/cache/flow/parts"/(entry["history"]["baseline"]["receipt"]+".json")
    historical=json.loads(record.read_text())
    for check in historical["info"]["native"]["checks"].values():
        check.pop("replay_inputs_literal",None)  # Original AdapterRun inputs already existed before the new format.
    record.write_text(json.dumps(historical))
    project.file("app.py",APP.replace('"wrong"','"expected"'))
    repaired=run_check(project.root,"--json")
    assert repaired.code==0,repaired.out+repaired.err
    assert repaired.data["closed"][0]["id"]==entry["id"]
    assert repaired.data["closed"][0]["why"].startswith("code_fixed:")


def test_unknown_original_code_identity_is_not_called_a_code_fix(project):
    _,entry=first_drift(project)
    path=project.root/".flowguard/conflicts.json"
    saved=json.loads(path.read_text())
    saved["conflicts"][0]["detail"]["native_origin"]["code_inputs"]=None
    path.write_text(json.dumps(saved))
    project.file("app.py",APP.replace('"wrong"','"expected"'))
    repaired=run_check(project.root,"--json")
    assert repaired.code==0,repaired.out+repaired.err
    assert repaired.data["closed"][0]["id"]==entry["id"]
    assert repaired.data["closed"][0]["why"].startswith("drift_resolved:")


def test_rediscovered_drift_preserves_original_inputs_and_identities(project):
    _,entry=first_drift(project)
    project.file("app.py",APP.replace('"wrong"','"still wrong"'))
    again=run_check(project.root,"--json")
    assert again.code==1,again.out+again.err
    saved=json.loads((project.root/".flowguard/conflicts.json").read_text())
    current,=[row for row in saved["conflicts"] if row["kind"]=="MODEL DRIFT"]
    assert current["detail"]["native_origin"]==entry["detail"]["native_origin"]
    assert current["history"]["baseline"]==entry["history"]["baseline"]


def test_model_correction_with_unrelated_code_edit_does_not_claim_code_fixed(project):
    _,entry=first_drift(project)
    project.flow("output",MODEL.replace('return "expected"','return "wrong"'))
    project.file("app.py",APP+'\n# Unrelated source annotation.\n')
    result=run_check(project.root,"--json")
    assert result.code==0,result.out+result.err
    assert result.data["closed"][0]["id"]==entry["id"]
    assert result.data["closed"][0]["why"].startswith("drift_resolved:")


@pytest.mark.parametrize("origin_retained",[False,True])
def test_current_origin_survives_cache_cleanup_but_missing_historical_inputs_stay_unknown(project,origin_retained):
    _,entry=first_drift(project)
    if not origin_retained:
        path=project.root/".flowguard/conflicts.json"
        saved=json.loads(path.read_text())
        del saved["conflicts"][0]["detail"]["native_origin"]
        path.write_text(json.dumps(saved))
    (project.root/".flowguard/cache/flow/parts"/(entry["history"]["baseline"]["receipt"]+".json")).unlink()
    project.file("app.py",APP.replace('"wrong"','"expected"'))
    result=run_check(project.root,"--json")
    if origin_retained:
        assert result.code==0 and result.data["closed"],result.out+result.err
    else:
        assert result.code==1 and not result.data["closed"],result.out+result.err
        assert any(row["id"]==entry["id"] for row in result.data["conflicts"])
        assert result.data["unknown"]==["output"]

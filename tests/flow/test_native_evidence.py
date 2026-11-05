"""Real model/code correspondence, rather than caller-declared confirmation."""
from pathlib import Path
import json
import pytest

from flowguard.flow.checks import check_model
from flowguard.flow.model import load_model
from flowguard.flow.native_evidence import evaluate_report


MODEL = '''from flowguard.flow import Model, need
from flowguard.flow.adapter import fields
m = Model("counter", covers=["app.py:Program"])
m.field("n", (0, 1), 0)
@m.action()
def step(s):
    need(s["n"] == 0)
    s["n"] = 1
m.bind_adapter({"system":"app:Program", "classes":["app:Program"], "refusal":["app:Refusal"]},
    state=lambda snapshot: {"n":fields(snapshot,names=("n",))["n"]}, operations={"step":"step"})
MODEL = m
'''

APP = '''class Refusal(Exception): pass
class Program:
    def __init__(self): self.n = 0
    def step(self):
        if self.n != 0: raise Refusal("at limit")
        self.n = 1
'''

OFFERED_MODEL = '''from flowguard.flow import Model,need
from flowguard.flow.adapter import fields
m=Model('offered refusal',covers=['app.py:Program'])
m.field('phase',('available','reserved','overdue','loaned'),'available')
m.terminal('phase',('loaned',))
@m.action()
def reserve(s):
    need(s['phase']=='available')
    s['phase']='reserved'
@m.action()
def mark_overdue(s):
    need(s['phase']=='reserved')
    s['phase']='overdue'
@m.action()
def collect(s):
    need(s['phase']=='reserved')
    s['phase']='loaned'
@m.action()
def cancel(s):
    need(s['phase'] in ('reserved','overdue'))
    s['phase']='available'
m.option('collect',lambda s:s['phase'] in ('reserved','overdue'),action='collect')
m.reach('a reservation can become a loan',lambda s:s['phase']=='loaned')
m.bind_adapter({'system':'app:Program','classes':['app:Program'],'refusal':['app:Refusal']},
    state=lambda snapshot:fields(snapshot,names=('phase',)),
    operations={name:name for name in ('reserve','mark_overdue','collect','cancel')})
MODEL=m
'''

OFFERED_APP = '''class Refusal(Exception): pass
class Program:
    def __init__(self): self.phase='available'
    def reserve(self):
        if self.phase!='available': raise Refusal('not available')
        self.phase='reserved'
    def mark_overdue(self):
        if self.phase!='reserved': raise Refusal('not reserved')
        self.phase='overdue'
    def collect(self):
        if self.phase not in ('reserved','overdue'): raise Refusal('not collectable')
        self.phase='loaned'
    def cancel(self):
        if self.phase not in ('reserved','overdue'): raise Refusal('not cancellable')
        self.phase='available'
'''


def offered_report(root,*,accepts_overdue=True):
    model=root/'.flowguard/flow/offered.py';model.parent.mkdir(parents=True)
    model.write_text(OFFERED_MODEL,encoding='utf-8')
    app=OFFERED_APP if accepts_overdue else OFFERED_APP.replace("self.phase not in ('reserved','overdue'): raise Refusal('not collectable')",
                                                               "self.phase!='reserved': raise Refusal('not collectable')")
    (root/'app.py').write_text(app,encoding='utf-8')
    return check_model(load_model(model,root))


def test_offered_refusal_model_records_the_final_call_outside_its_prefix(tmp_path):
    report=offered_report(tmp_path)
    assert report.graph.complete
    finding,=[finding for finding in report.findings if finding.kind=='CONTRADICTION']
    assert finding.path==('reserve()','mark_overdue()')
    assert finding.detail['call']=='collect()'
    assert not any(finding.kind=='STUCK' for finding in report.findings)


def test_contradiction_cannot_be_confirmed_when_the_real_final_call_succeeds(tmp_path):
    report=offered_report(tmp_path)
    finding,=[finding for finding in report.findings if finding.kind=='CONTRADICTION']
    evidence=evaluate_report(tmp_path,report)
    assert evidence['status']=='drift' and finding.id not in evidence['confirmed']
    checks=[check for check in evidence['checks'].values() if check['status']=='drift']
    assert any(check['trace']['steps'][-1]['function_name']=='collect' and
               check['trace']['steps'][-1]['label']=='refusal' and
               check['native']['steps'][-1]['outcome']=='success' for check in checks)


def test_contradiction_confirmation_contains_the_actual_final_refusal(tmp_path):
    report=offered_report(tmp_path,accepts_overdue=False)
    finding,=[finding for finding in report.findings if finding.kind=='CONTRADICTION']
    evidence=evaluate_report(tmp_path,report)
    assert evidence['status']=='conformant'
    proof=evidence['confirmed'][finding.id]
    assert any(evidence['checks'][key]['trace']['steps'][-1]['function_name']=='collect' and
               evidence['checks'][key]['native']['steps'][-1]['outcome']=='refusal' for key in proof['checks'])


@pytest.mark.parametrize('field,value',[('call',None),('call',[]),('call','missing()'),
                                      ('call','cancel()'),('call','reserve()'),('option','missing')])
def test_missing_or_invalid_contradiction_call_is_unknown(tmp_path,field,value):
    report=offered_report(tmp_path,accepts_overdue=False)
    finding,=[finding for finding in report.findings if finding.kind=='CONTRADICTION']
    finding.detail[field]=value
    evidence=evaluate_report(tmp_path,report)
    assert evidence['status']=='unknown' and finding.id not in evidence['confirmed']
    assert evidence['limits']


def test_actual_cli_reports_drift_at_the_unverified_refused_option_call(project):
    from checkrun import run_check
    project.file('app.py',OFFERED_APP)
    project.flow('offered',OFFERED_MODEL)
    result=run_check(project.root,'--json')
    assert result.code==1,result.out+result.err
    drift,=[finding for finding in result.data['conflicts'] if finding['kind']=='MODEL DRIFT']
    summary=drift['detail']['native']
    native=json.loads((project.root/summary['record']).read_text(encoding='utf-8'))['info']['native']
    witness=native['checks'][summary['check']]
    assert witness['trace']['steps'][-1]['function_name']=='collect'
    assert witness['trace']['steps'][-1]['label']=='refusal'
    assert witness['native']['steps'][-1]['call']['name']=='collect'
    assert witness['native']['steps'][-1]['outcome']=='success'
    stored=json.loads((project.root/'.flowguard/conflicts.json').read_text(encoding='utf-8'))
    contradiction=next(finding for finding in stored['conflicts'] if finding['kind']=='CONTRADICTION')
    assert contradiction.get('native_confirmation',{}).get('status')!='confirmed'


def project(tmp_path, *, app=APP):
    model = tmp_path / ".flowguard/flow/counter.py"
    model.parent.mkdir(parents=True)
    model.write_text(MODEL)
    (tmp_path / "app.py").write_text(app)
    return check_model(load_model(model, tmp_path))


def test_stuck_confirmation_observes_all_actual_exit_refusals(tmp_path):
    from flowguard.flow.cli import conflict_question
    from flowguard.flow.project import conflict_entry

    report = project(tmp_path)
    stuck, = [f for f in report.findings if f.kind == "STUCK"]
    entry = conflict_entry(stuck)
    assert 'model-only: check the owner words and actual code' in conflict_question(tmp_path, entry)
    entry['native_confirmation'] = {'status': 'unknown'}
    assert 'repair the model or code as warranted' in conflict_question(tmp_path, entry)
    evidence = evaluate_report(tmp_path, report)
    assert evidence["status"] == "conformant"
    assert evidence["confirmed"][stuck.id]["status"] == "confirmed"
    checks = [evidence["checks"][key] for key in evidence["confirmed"][stuck.id]["checks"]]
    assert any(check["native"]["steps"][-1]["outcome"] == "refusal" for check in checks)
    assert evidence["code_inputs"]["app.py"]
    entry['native_confirmation'] = evidence['confirmed'][stuck.id]
    question = conflict_question(tmp_path, entry)
    assert 'repair the dead end in code' in question and 'model-only' not in question
    entry['kind'] = 'NEVER REACHED'
    question = conflict_question(tmp_path, entry)
    assert 'make the promised behavior reachable in code' in question and 'model-only' not in question
    entry.pop('native_confirmation')
    assert 'repair the model or code as warranted' in conflict_question(tmp_path, entry)


def test_model_code_disagreement_cannot_confirm_or_close_the_model_bug(tmp_path):
    report = project(tmp_path, app=APP.replace('self.n = 1', 'self.n = 0'))
    evidence = evaluate_report(tmp_path, report)
    assert evidence["status"] == "drift"
    assert not evidence["confirmed"] and not evidence["closures"]
    assert any(check["status"] == "drift" for check in evidence["checks"].values())


def test_unbound_logical_model_has_no_native_confirmation(tmp_path):
    model = tmp_path / ".flowguard/flow/logic.py"
    model.parent.mkdir(parents=True)
    model.write_text('from flowguard.flow import Model\nm=Model("logic")\nm.field("done",(False,True),False)\nMODEL=m\n')
    evidence = evaluate_report(tmp_path, check_model(load_model(model, tmp_path)))
    assert evidence["status"] == "model-only" and not evidence["bound"]
    assert not evidence["confirmed"] and not evidence["checks"]


def test_real_cli_reuses_native_inputs_and_detects_a_production_only_edit(project):
    from checkrun import run_check
    project.file("app.py", APP)
    project.flow("counter", MODEL)
    first = run_check(project.root, "--json")
    assert first.code == 1, first.out + first.err
    # The next check installs the newly discovered conflict's stable original-condition inputs.
    assert run_check(project.root, "--json").code == 1
    unchanged = run_check(project.root, "--json")
    assert unchanged.code == 1, unchanged.out + unchanged.err
    assert all(part["cached"] for part in unchanged.data["parts"]), unchanged.out
    project.file("app.py", APP.replace("self.n = 1", "self.n = 0"))
    drift = run_check(project.root, "--json")
    assert drift.code == 1, drift.out + drift.err
    mismatch, = [finding for finding in drift.data['conflicts'] if finding['kind'] == 'MODEL DRIFT']
    assert mismatch['detail']['code_status'] == 'drift'
    summary = mismatch['detail']['native']
    assert 'trace' not in summary
    record = project.root / summary['record']
    assert record.is_file()
    native = json.loads(record.read_text())['info']['native']
    actual = native['walk'] if summary['check'] == 'walk' else native['checks'][summary['check']]
    assert native['status'] == actual['status'] == 'drift'
    assert actual['trace']['steps'] and actual['native']['steps']
    assert actual['native']['rule_captures']['native_evidence']['status'] == 'current'
    assert drift.data['errors'] == []


def test_emitted_stuck_regression_executes_the_repair_not_only_the_old_prefix(tmp_path):
    import runpy
    import pytest
    from flowguard.flow.descriptors import input_evidence, model_descriptor
    from flowguard.flow.project import conflict_entry

    def observed(loaded, report):
        descriptor = model_descriptor(loaded, report, "test-computation", input_evidence(tmp_path, loaded.reads))
        return {"receipt":"test-computation", "finished":True, "loaded":True,
                "complete":report.graph.complete, "errors":len(report.graph.errors),
                "scope":descriptor["scope"], "obligations":descriptor["obligations"], "replay":"not_run"}

    report = project(tmp_path)
    old_finding, = [f for f in report.findings if f.kind == "STUCK"]
    before = evaluate_report(tmp_path, report)
    entry = conflict_entry(old_finding, observation=observed(report.loaded, report))
    entry["native_confirmation"] = before["confirmed"][old_finding.id]
    model_path = tmp_path / ".flowguard/flow/counter.py"
    repair = '@m.action()\ndef reset(s):\n    need(s["n"] == 1)\n    s["n"] = 0\n'
    model_path.write_text(MODEL.replace('m.bind_adapter(', repair + 'm.bind_adapter(')
                          .replace('operations={"step":"step"}', 'operations={"step":"step","reset":"reset"}'))
    fixed_app = APP + '    def reset(self):\n        if self.n != 1: raise Refusal("not broken")\n        self.n = 0\n'
    (tmp_path / "app.py").write_text(fixed_app)
    loaded = load_model(model_path, tmp_path)
    after = check_model(loaded)
    result = evaluate_report(tmp_path, after, [entry], observation=observed(loaded, after))
    from flowguard.flow.history import assess
    assert entry["id"] in result["closures"], {"status":result["status"], "limits":result["limits"],
                                                "comparison":assess(entry, observed(loaded, after))}
    regression = tmp_path / result["closures"][entry["id"]]["regression"]["path"]
    (tmp_path / "app.py").write_text(fixed_app.replace('        self.n = 0\n',
                                                     '        raise Refusal("repair broke again")\n'))
    with pytest.raises(AssertionError, match="native regression"):
        runpy.run_path(str(regression), run_name="__main__")

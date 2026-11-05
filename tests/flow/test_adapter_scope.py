"""A native inventory omission belongs to the declared source scope."""
import pytest

from flowguard.flow.adapter import check_trace, trace_calls
from flowguard.flow.checks import check_model
from flowguard.flow.model import load_model
from flowguard.flow.native_evidence import evaluate_report


MODEL = '''from flowguard.flow import Model
from flowguard.flow.adapter import fields
m=Model('repair',covers=COVERS)
m.field('n',(0,1),0)
m.terminal('n',(1,))
@m.action()
def repair(s): s['n']=1
m.bind_adapter({'system':'MODULE:Program','classes':CLASSES},
    state=lambda snapshot:fields(snapshot,names=('n',)),operations={'repair':'repair'})
MODEL=m
'''

APP = '''class Program:
    def __init__(self): self.n=0
    def repair(self): self.n=1
    def unrelated_report(self): raise AssertionError('unrelated operation ran')
'''


def setup(project, covers, *, app=APP, path='app.py', module='app', classes=None, native_root=None):
    project.file(path,app)
    project.file('unrelated.py',"raise AssertionError('unrelated module ran')\n")
    project.file('unused/__init__.py',"raise AssertionError('path alias module ran')\n")
    text=MODEL.replace('COVERS',repr(covers)).replace('MODULE',module)
    text=text.replace('CLASSES',repr(classes or [module+':Program']))
    if native_root is not None:
        text=text.replace('m.bind_adapter({', 'm.bind_adapter({"root":'+repr(str(native_root))+',')
    path=project.flow('repair',text)
    report=check_model(load_model(path,project.root))
    assert report.graph.complete and not report.findings
    return report


@pytest.mark.parametrize('cover,status',[
    ('consumer/app.py:Program.repair', 'conformant'),
    ('consumer/app.py:Program', 'drift'),
    ('consumer/app.py', 'drift'),
])
def test_loaded_cover_root_is_independent_of_native_execution_root(project, cover, status):
    report = setup(project, [cover], path='consumer/app.py', native_root=project.root/'consumer')
    result = check_trace(report.graph, trace_calls(report.graph, (0,)))
    assert result.status == status, result
    if status == 'drift':
        assert any('system.unrelated_report' in v.message for v in result.conformance.violations)
    else:
        assert len(result.native['steps']) == 1


@pytest.mark.parametrize('path,module,cover',[
    ('app.py','app','app.py:Program.repair'),
    ('app.py','app','./app.py:Program.repair'),
    ('app.py','app','unused/../app.py:Program.repair'),
    ('pkg/__init__.py','pkg','pkg/__init__.py:Program.repair'),
    ('src/app.py','src.app','src/app.py:Program.repair'),
])
def test_precise_feature_scope_keeps_real_operation_witness(project,path,module,cover):
    report=setup(project,[cover],path=path,module=module)
    evidence=evaluate_report(project.root,report)
    assert evidence['status']=='conformant',evidence
    coverage=evidence['operation_coverage']
    assert 'skipped' not in coverage and len(coverage['witnesses'])==1
    observed=evidence['checks'][coverage['witnesses'][0]['check']]
    assert len(observed['native']['steps'])==1
    assert observed['native']['steps'][0]['call']['name']=='repair'


@pytest.mark.parametrize('covers',[[],['app.py'],['app.py:Program']])
def test_full_receiver_file_or_class_scope_still_catches_omission(project,covers):
    report=setup(project,covers)
    run=check_trace(report.graph,trace_calls(report.graph,()))
    assert run.status=='drift'
    assert 'system.unrelated_report' in run.conformance.violations[0].message


@pytest.mark.parametrize('scope,missing',[
    ('base.py:Base.repair',()),
    ('base.py:Base',('system.base_report',)),
    ('app.py:Program',('system.base_report','system.unrelated_report')),
    ('app.py',('system.base_report','system.unrelated_report')),
])
def test_inherited_methods_keep_real_declaring_source(project,scope,missing):
    project.file('base.py','''class Base:
    def __init__(self): self.n=0
    def repair(self): self.n=1
    def base_report(self): raise AssertionError('unrelated inherited operation ran')
''')
    report=setup(project,[scope],app='''from base import Base
class Program(Base):
    def unrelated_report(self): raise AssertionError('unrelated subclass operation ran')
''',classes=['app:Program','base:Base'])
    run=check_trace(report.graph,trace_calls(report.graph,(0,)))
    if missing:
        assert run.status=='drift'
        text=run.conformance.violations[0].message
        assert all(name in text for name in missing)
        if scope=='base.py:Base': assert 'system.unrelated_report' not in text
    else:
        assert run.status=='conformant',run.to_dict()


def test_precise_scope_retains_real_drift_and_unknown(project):
    report=setup(project,['app.py:Program.repair'],app=APP.replace('self.n=1','self.n=9'))
    drift=check_trace(report.graph,trace_calls(report.graph,(0,)))
    assert drift.status=='drift'
    assert 'outside the model domain' in drift.conformance.violations[0].message
    source=project.root/'app.py'
    source.write_text(APP+'''    def __getattr__(self,name): raise AttributeError(name)
''')
    unknown=check_trace(report.graph,trace_calls(report.graph,(0,)))
    assert unknown.status=='unknown' and 'dynamic attribute lookup' in unknown.reason


def test_unavailable_actual_declaring_source_is_unknown_not_excluded(project):
    report=setup(project,['app.py:Program'],app=APP+'del __file__\n')
    run=check_trace(report.graph,trace_calls(report.graph,()))
    assert run.status=='unknown' and 'native operation scope is unavailable' in run.reason


def test_replacement_receiver_cannot_vacuously_erase_covered_class_scope(project):
    report=setup(project,['app.py:Program'],app='''class Replacement:
    def __init__(self): self.n=0
    def repair(self): self.n=1
    def unrelated_report(self): raise AssertionError('unrelated replacement operation ran')
class Program:
    def __new__(cls): return Replacement()
''',classes=['app:Program','app:Replacement'])
    run=check_trace(report.graph,trace_calls(report.graph,()))
    assert run.status=='unknown' and 'native operation scope is unavailable' in run.reason

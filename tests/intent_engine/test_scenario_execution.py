from pathlib import Path
from types import SimpleNamespace

from flowguard.intent import anchors, calibration
from flowguard.intent.flow import Flow, Node, Read, Relation
from flowguard.intent.cells import Raised


def scenario(tmp_path, *, enum=False, refusal=False, extra=''):
    if enum:
        (tmp_path/'kinds.py').write_text('from enum import Enum\nclass QuoteCase(Enum):\n    EXACT="exact"\n    CHANGED="changed"\n')
        (tmp_path/'policy.py').write_text('''from kinds import QuoteCase
# flowguard: sensor choice(quote: kind) -> allowed: bool
def choice(quote: QuoteCase) -> bool:
    return quote is QuoteCase.EXACT
''')
        declaration='quote: QuoteCase'; values='QuoteCase.EXACT'; imports='from kinds import QuoteCase\n'; call='choice(quote)'; field='quote'
    else:
        (tmp_path/'policy.py').write_text('''# flowguard: sensor choice(x: count) -> allowed: bool
def choice(x: int) -> bool:
    if x < 0: raise ValueError('native negative refusal')
    return x <= 3
''')
        declaration='x: int';values='2';imports='';call='choice(x)';field='x'
    (tmp_path/'test_case.py').write_text(imports+'from policy import choice\nimport pytest\n'+
        '# flowguard: event CASE('+declaration+')\n'+
        '@pytest.mark.parametrize("'+field+'", ['+values+'])\n'+
        'def test_case('+declaration+'):\n    answer='+call+'\n    assert type(answer) is bool\n'+extra)
    (tmp_path/'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    index=anchors.collect_sources(tmp_path,[('policy.py','policy'),('test_case.py','test_case',True)])
    entry=index.named('CASE')[0]; target=index.named('choice')[0]
    nodes=[Node('case','CASE',start=True),Node('answer','choice',phase='return',caller='case',end=True)]
    relations=[Relation('RULE',{field:Read('case','arg.'+field)},Read('answer'),on='answer')]
    if refusal:
        nodes.append(Node('denied','choice',phase='raise',caller='case',end=True))
        relations.append(Relation('RULE',{field:Read('case','arg.'+field)},Read('denied','error'),on='denied'))
    model=Flow('FLOW','test source',tuple(nodes),tuple(('case',n.name) for n in nodes[1:]),relations=tuple(relations))
    identifier='QuoteCase.EXACT' if enum else '2'
    return SimpleNamespace(flow=model,scenario=entry,anchor=target,anchor_index=index,
                           field_map={field:field},testnode='test_case.py::test_case['+identifier+']',
                           observed_rule='RULE',relation_indices=tuple(range(len(relations))),actual_targets=(target.target,),targets=(target.target,))


def test_scenario_gets_actual_production_result_not_test_none_or_predicate(tmp_path):
    binding=scenario(tmp_path)
    actual=calibration.execute_scenario(tmp_path,binding,{'x':4})
    assert actual.status=='ok' and actual.value is False,actual.reasons
    actual=calibration.execute_scenario(tmp_path,binding,{'x':2})
    assert actual.status=='ok' and actual.value is True,actual.reasons


def test_scenario_enum_identity_is_real_member_not_its_string_value(tmp_path):
    binding=scenario(tmp_path,enum=True)
    changed=calibration._EnumRef('kinds','QuoteCase','CHANGED','changed')
    actual=calibration.execute_scenario(tmp_path,binding,{'quote':changed})
    assert actual.status=='ok' and actual.value is False,actual.reasons
    wrong=calibration._EnumRef('kinds','QuoteCase','CHANGED','not-the-value')
    actual=calibration.execute_scenario(tmp_path,binding,{'quote':wrong})
    assert actual.status=='grey' and actual.value is None


def test_scenario_only_declared_native_error_can_be_refused(tmp_path):
    binding=scenario(tmp_path,refusal=True)
    actual=calibration.execute_scenario(tmp_path,binding,{'x':-1})
    assert actual.status=='ok' and isinstance(actual.value,Raised),actual.reasons
    assert type(actual.value.error) is ValueError and str(actual.value.error)=='native negative refusal'
    (tmp_path/'test_case.py').write_text((tmp_path/'test_case.py').read_text()+"    raise ValueError('test harness failure')\n")
    fresh=scenario(tmp_path,extra="    raise ValueError('test harness failure')\n")
    actual=calibration.execute_scenario(tmp_path,fresh,{'x':2})
    assert actual.status in {'red','grey'} and not isinstance(actual.value,Raised)


def test_scenario_does_not_choose_first_or_last_reading(tmp_path):
    binding=scenario(tmp_path,extra='    choice(x)\n')
    actual=calibration.execute_scenario(tmp_path,binding,{'x':4})
    assert actual.status=='grey' and actual.value is None


def test_scenario_internal_failure_is_not_a_business_refusal(tmp_path, monkeypatch):
    binding=scenario(tmp_path)
    def failed(request): raise ValueError('private transport failure')
    monkeypatch.setattr(calibration,'_child',failed)
    actual=calibration.execute_scenario(tmp_path,binding,{'x':2})
    assert actual.status in {'red','grey'} and actual.value is None
    assert 'transport failure' in ' '.join(actual.reasons)


def test_scenario_checks_requested_logical_inputs_for_joint_witnesses(tmp_path):
    binding=scenario(tmp_path)
    binding.requested_inputs={'x':99}
    actual=calibration.execute_scenario(tmp_path,binding,{'x':2})
    assert actual.status=='grey' and actual.value is None
    assert 'input did not match' in ' '.join(actual.reasons)


def test_scenario_never_uses_test_return_or_rule_predicate_as_actual(tmp_path):
    binding=scenario(tmp_path,extra='    return True\n')
    class ExplosiveRule:
        id='RULE'
        def eval(self,*args): raise AssertionError('rule predicate used as actual')
    relation=binding.flow.relations[0]
    binding.flow.relations=(Relation(ExplosiveRule(),relation.inputs,relation.actual,relation.on),)
    actual=calibration.execute_scenario(tmp_path,binding,{'x':4})
    assert actual.status=='ok' and actual.value is False,actual.reasons


def test_enum_source_binding_must_be_the_actual_native_class(tmp_path):
    binding=scenario(tmp_path,enum=True)
    file=tmp_path/'test_case.py'
    file.write_text(file.read_text()+'''\nfrom enum import Enum
QuoteCase = Enum('QuoteCase', {'EXACT':'exact','CHANGED':'changed'})
''')
    index=anchors.collect_sources(tmp_path,[('policy.py','policy'),('test_case.py','test_case',True)])
    binding.anchor_index=index;binding.scenario=index.named('CASE')[0]
    actual=calibration.execute_scenario(tmp_path,binding,{'quote':calibration._EnumRef('kinds','QuoteCase','CHANGED','changed')})
    assert actual.status=='grey' and actual.value is None
    assert 'source type' in ' '.join(actual.reasons)


def test_real_probe_plugin_does_not_write_ordinary_cache_or_project_map(tmp_path):
    binding=scenario(tmp_path)
    file=tmp_path/'pyproject.toml'
    file.write_text(file.read_text()+'addopts="-p flowguard.intent.plugin"\n')
    actual=calibration.execute_scenario(tmp_path,binding,{'x':4})
    assert actual.status=='ok' and actual.value is False,actual.reasons
    assert not (tmp_path/'.flowguard/cache').exists(), list((tmp_path/'.flowguard').rglob('*'))


def test_same_sdk_mutant_is_applied_to_actual_case_not_verifier_collection(tmp_path):
    import json, os, shutil, subprocess, sys
    sdk=Path(calibration.__file__).resolve().parents[1]
    root=tmp_path/'self_sdk';root.mkdir()
    shutil.copytree(sdk,root/'flowguard',ignore=shutil.ignore_patterns('__pycache__'))
    (root/'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\naddopts="-p flowguard.intent.plugin"\n')
    (root/'conftest.py').write_text('''import ast
from flowguard.intent import loader
def pytest_collection_modifyitems(items):
    assert loader.is_literal(ast.Constant(1)) is True, 'mutant reached verifier collection before actual case'
''')
    (root/'projection.py').write_text('''# flowguard: sensor PROJECTION(answer: bool) -> accepted: bool
def projected(answer: bool) -> bool:
    return answer
''')
    (root/'test_native.py').write_text('''import ast
import pytest
from flowguard.intent import loader
from projection import projected
# flowguard: event CASE(expression: str)
@pytest.mark.parametrize('expression', ['1'])
def test_case(expression: str):
    answer=loader.is_literal(ast.parse(expression,mode='eval').body)
    assert type(projected(answer)) is bool
''')
    script='''from pathlib import Path
from types import SimpleNamespace
import ast
from flowguard.intent import anchors,calibration,sites,loader
from flowguard.intent.flow import Flow,Node,Read,Relation
root=Path.cwd()
index=anchors.collect_sources(root,[('flowguard/intent/loader.py','flowguard.intent.loader'),('test_native.py','test_native',True),('projection.py','projection')])
scenario=index.named('CASE')[0];target=index.named('PROJECTION')[0];measurement=index.named('ROW_LITERAL')[0]
model=Flow('F','actual SDK verifier',(Node('case','CASE',start=True),Node('answer','PROJECTION',phase='return',caller='case',end=True)),(('case','answer'),),relations=(Relation('R',{'expression':Read('case','arg.expression')},Read('answer'),on='answer'),))
b=SimpleNamespace(flow=model,scenario=scenario,anchor=target,anchor_index=index,field_map={'expression':'expression'},testnode='test_native.py::test_case[1]',observed_rule='R',relation_indices=(0,),actual_targets=(target.target,),targets=(measurement.target,target.target))
def changed(fdef):fdef.body=[ast.Return(ast.Constant(False))]
code=sites._recompile(loader.is_literal,ast.NodeTransformer(),lambda:True,changed)
with calibration._execution_session(root):
    fact=calibration._prepare_scenario(root,b)
    assert fact['status']=='ok',fact
    with sites.installed(loader.is_literal,code):
        before=loader.is_literal.__code__
        actual=calibration._observe_scenario_current(root,b,{'expression':'1'})
        assert actual.status=='ok' and actual.value is False,actual.reasons
        assert loader.is_literal.__code__ is before,'mutant code was erased after actual observation'
with calibration._execution_session(root):
    with sites.installed(loader.is_literal,code):
        unprepared=calibration._observe_scenario_current(root,b,{'expression':'1'})
        assert unprepared.status=='grey' and 'prepared' in ' '.join(unprepared.reasons)
'''
    env=os.environ.copy();env['PYTHONPATH']=str(root)
    process=subprocess.run([sys.executable,'-B','-c',script],cwd=root,env=env,capture_output=True,text=True)
    assert process.returncode==0,process.stdout+process.stderr


def test_scenario_parameter_point_type_mismatch_is_red(tmp_path):
    binding=scenario(tmp_path)
    actual=calibration.execute_scenario(tmp_path,binding,{'x':'not-an-int'})
    assert actual.status=='red' and actual.value is None
    assert 'parameter type' in ' '.join(actual.reasons)


def test_repeated_current_scenario_without_permanent_plugin_keeps_verified_imports(tmp_path):
    import os,subprocess,sys
    binding=scenario(tmp_path)
    script='''from pathlib import Path
from flowguard.intent import calibration
root=Path.cwd()
binding=calibration._binding(__import__('json').loads(__import__('sys').argv[1]))
with calibration._execution_session(root):
    fact=calibration._prepare_scenario(root,binding)
    assert fact['status']=='ok',fact
    first=calibration._observe_scenario_current(root,binding,{'x':4})
    assert first.status=='ok' and first.value is False,first.reasons
    second=calibration._observe_scenario_current(root,binding,{'x':2})
    assert second.status=='ok' and second.value is True,second.reasons
'''
    import json
    sdk=Path(calibration.__file__).resolve().parents[2]
    env=os.environ.copy();env['PYTHONPATH']=str(sdk)
    result=subprocess.run([sys.executable,'-B','-c',script,json.dumps(calibration._binding_data(binding))],cwd=tmp_path,env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


def test_native_plugin_and_driver_share_one_verified_source_owner(tmp_path):
    binding=scenario(tmp_path)
    tests=tmp_path/'tests';tests.mkdir();(tests/'__init__.py').write_text('')
    (tests/'conftest.py').write_text('pytest_plugins=["flowguard.intent.plugin"]\n')
    (tmp_path/'test_case.py').rename(tests/'test_case.py')
    (tmp_path/'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\naddopts="-p flowguard.intent.plugin"\n')
    index=anchors.collect_sources(tmp_path,[('policy.py','policy'),('tests/test_case.py','tests.test_case',True)])
    binding.anchor_index=index;binding.scenario=index.named('CASE')[0]
    binding.testnode='tests/test_case.py::test_case[2]'
    # Start with one explicitly selected SDK dependency; the outer source-tree
    # test process may itself have a different installed FlowGuard on PYTHONPATH.
    # No project plugin, config or assertion is removed to make this control pass.
    import json, os, subprocess, sys
    sdk=Path(calibration.__file__).resolve().parents[2]
    script="""from pathlib import Path
import json,sys
from flowguard.intent import calibration
binding=calibration._binding(json.loads(sys.argv[1]))
actual=calibration.execute_scenario(Path.cwd(),binding,{'x':4})
assert actual.status=='ok' and actual.value is False,actual.reasons
"""
    env=os.environ.copy();env['PYTHONPATH']=str(sdk)
    result=subprocess.run([sys.executable,'-B','-c',script,json.dumps(calibration._binding_data(binding))],cwd=tmp_path,env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


def test_super_method_mutant_keeps_the_actual_anchor_code_identity(tmp_path):
    import json,os,subprocess,sys
    binding=scenario(tmp_path)
    (tmp_path/'policy.py').write_text('''class Base:
    def offset(self): return 0
class Policy(Base):
    # flowguard: sensor choice(x: count) -> allowed: bool
    def choice(self, x: int) -> bool:
        return x + super().offset() <= 3
''')
    case=tmp_path/'test_case.py';case.write_text(case.read_text().replace('from policy import choice','from policy import Policy').replace('answer=choice(x)','answer=Policy().choice(x)'))
    index=anchors.collect_sources(tmp_path,[('policy.py','policy'),('test_case.py','test_case',True)])
    binding.anchor_index=index;binding.scenario=index.named('CASE')[0];binding.anchor=index.named('choice')[0]
    binding.actual_targets=binding.targets=(binding.anchor.target,)
    script='''from pathlib import Path
import json,sys,importlib
from flowguard.intent import calibration,sites
from flowguard.intent.config import load_config,setup_path
from flowguard.intent.imports import prepare
root=Path.cwd();binding=calibration._binding(json.loads(sys.argv[1]))
setup_path(load_config(root));prepare(root)
fn=importlib.import_module('policy').Policy.choice
with calibration._execution_session(root):
    fact=calibration._prepare_scenario(root,binding)
    assert fact['status']=='ok',fact
    mutant=next(m for m in sites.mutants_of(sites.sites_of(fn),set()) if m.how=='flip')
    code=sites.mutant_code(fn,mutant)
    with sites.installed(fn,code):
        actual=calibration._observe_scenario_current(root,binding,{'x':3})
        assert actual.status=='ok' and actual.value is False,actual.reasons
        assert fn.__code__ is code
        assert code.co_qualname == fn.__qualname__
'''
    sdk=Path(calibration.__file__).resolve().parents[2]
    env=os.environ.copy();env['PYTHONPATH']=str(sdk)
    process=subprocess.run([sys.executable,'-B','-c',script,json.dumps(calibration._binding_data(binding))],cwd=tmp_path,env=env,capture_output=True,text=True)
    assert process.returncode==0,process.stdout+process.stderr

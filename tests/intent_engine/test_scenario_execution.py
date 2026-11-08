"""Scenario observations use actual items in the existing pytest session."""
import ast
from contextlib import ExitStack
import importlib
from pathlib import Path
from types import SimpleNamespace

from flowguard.intent import anchors, calibration, sites
from flowguard.intent.flow import Flow, Node, Read, Relation
from flowguard.intent.cells import Raised
from flowguard.intent.runtime import Runtime
from tests.intent_engine._source_fixture import source_sessions
from tests.intent_engine._protocol_controls import bind_scenario

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
    binding = scenario(tmp_path)
    bind_scenario(tmp_path, binding)
    actual = calibration.execute_scenario(tmp_path, binding, {'x': 4})
    assert actual.status == 'ok' and actual.value is False, actual.reasons
    actual = calibration.execute_scenario(tmp_path, binding, {'x': 2})
    assert actual.status == 'ok' and actual.value is True, actual.reasons


def test_scenario_enum_identity_is_real_member_not_its_string_value(tmp_path):
    binding = scenario(tmp_path, enum=True)
    bind_scenario(tmp_path, binding)
    enum = importlib.import_module('kinds').QuoteCase
    actual = calibration.execute_scenario(tmp_path, binding, {'quote': enum.CHANGED})
    assert actual.status == 'ok' and actual.value is False, actual.reasons
    forged = object.__new__(enum)
    forged._name_, forged._value_ = 'CHANGED', 'not-the-value'
    actual = calibration.execute_scenario(tmp_path, binding, {'quote': forged})
    assert actual.status == 'grey' and actual.value is None
    copied = object.__new__(enum)
    copied._name_, copied._value_ = enum.CHANGED.name, enum.CHANGED.value
    actual = calibration.execute_scenario(tmp_path, binding, {'quote': copied})
    assert actual.status == 'grey' and actual.value is None


def test_scenario_only_declared_native_error_can_be_refused(tmp_path):
    binding = scenario(tmp_path, refusal=True)
    bind_scenario(tmp_path, binding)
    actual = calibration.execute_scenario(tmp_path, binding, {'x': -1})
    assert actual.status == 'ok' and isinstance(actual.value, Raised), actual.reasons
    assert type(actual.value.error) is ValueError and str(actual.value.error) == 'native negative refusal'
    fresh = scenario(tmp_path, extra="    raise ValueError('test harness failure')\n")
    bind_scenario(tmp_path, fresh)
    actual = calibration.execute_scenario(tmp_path, fresh, {'x': 2})
    assert actual.status in {'red', 'grey'} and not isinstance(actual.value, Raised)


def test_scenario_does_not_choose_first_or_last_reading(tmp_path):
    binding = scenario(tmp_path, extra='    choice(x)\n')
    bind_scenario(tmp_path, binding)
    actual = calibration.execute_scenario(tmp_path, binding, {'x': 4})
    assert actual.status == 'grey' and actual.value is None


def test_scenario_runtime_failure_is_not_a_business_refusal(tmp_path, monkeypatch):
    binding = scenario(tmp_path)
    scope, _ = bind_scenario(tmp_path, binding)
    def failed(*args, **kwargs): raise ValueError('real replay infrastructure failure')
    monkeypatch.setattr(scope.runtime, 'replay', failed)
    actual = calibration.execute_scenario(tmp_path, binding, {'x': 2})
    assert actual.status in {'red', 'grey'} and actual.value is None
    assert 'replay infrastructure failure' in ' '.join(actual.reasons)


def test_scenario_checks_requested_logical_inputs_for_joint_witnesses(tmp_path):
    binding = scenario(tmp_path)
    bind_scenario(tmp_path, binding)
    binding.requested_inputs = {'x': 99}
    actual = calibration.execute_scenario(tmp_path, binding, {'x': 2})
    assert actual.status == 'grey' and actual.value is None
    assert 'input did not match' in ' '.join(actual.reasons)


def test_scenario_never_uses_test_return_or_rule_predicate_as_actual(tmp_path):
    binding = scenario(tmp_path, extra='    return True\n')
    class ExplosiveRule:
        id = 'RULE'
        def eval(self, *args): raise AssertionError('rule predicate used as actual')
    relation = binding.flow.relations[0]
    binding.flow.relations = (Relation(ExplosiveRule(), relation.inputs, relation.actual, relation.on),)
    bind_scenario(tmp_path, binding)
    actual = calibration.execute_scenario(tmp_path, binding, {'x': 4})
    assert actual.status == 'ok' and actual.value is False, actual.reasons


def test_enum_source_binding_must_be_the_actual_native_class(tmp_path):
    binding = scenario(tmp_path, enum=True)
    file = tmp_path / 'test_case.py'
    file.write_text(file.read_text()+"\nfrom enum import Enum\nQuoteCase = Enum('QuoteCase', {'EXACT':'exact','CHANGED':'changed'})\n")
    index = anchors.collect_sources(tmp_path, [('policy.py','policy'),('test_case.py','test_case',True)])
    binding.anchor_index, binding.scenario = index, index.named('CASE')[0]
    bind_scenario(tmp_path, binding)
    changed = importlib.import_module('kinds').QuoteCase.CHANGED
    actual = calibration.execute_scenario(tmp_path, binding, {'quote': changed})
    assert actual.status == 'grey' and actual.value is None
    assert 'source type' in ' '.join(actual.reasons)


def test_real_probe_plugin_does_not_write_ordinary_cache_or_project_map(tmp_path):
    binding = scenario(tmp_path)
    file = tmp_path / 'pyproject.toml'; file.write_text(file.read_text()+'addopts="-p flowguard.intent.plugin"\n')
    bind_scenario(tmp_path, binding)
    actual = calibration.execute_scenario(tmp_path, binding, {'x': 4})
    assert actual.status == 'ok' and actual.value is False, actual.reasons
    assert not (tmp_path / '.flowguard' / 'cache').exists(), list((tmp_path / '.flowguard').rglob('*'))


def test_same_sdk_mutant_is_applied_after_real_collection_and_restored(tmp_path):
    # Observe this SDK's actual loader in this process. A second copied SDK and
    # a private interpreter are retired; no package is installed or replaced.
    import tempfile
    from flowguard.intent import loader
    root = Path(loader.__file__).resolve().parents[2]
    (root / '.pytest_cache').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='native-sdk-', dir=root / '.pytest_cache') as folder:
        native = Path(folder) / 'test_native_sdk.py'
        projection = Path(folder) / 'sdk_projection.py'
        projection.write_text('# flowguard: sensor PROJECTION(answer: bool) -> accepted: bool\ndef projected(answer: bool) -> bool:\n    return answer\n')
        native.write_text('''import ast
import pytest
from flowguard.intent import loader
from sdk_projection import projected
# flowguard: event CASE(expression: str)
@pytest.mark.parametrize('expression', ['1'])
def test_case(expression: str):
    answer = loader.is_literal(ast.parse(expression, mode='eval').body)
    assert type(projected(answer)) is bool
''')
        index = anchors.collect_sources(root, [('flowguard/intent/loader.py','flowguard.intent.loader'),
            (native.relative_to(root).as_posix(),'test_native_sdk',True),
            (projection.relative_to(root).as_posix(),'sdk_projection')])
        target, event = index.named('PROJECTION')[0], index.named('CASE')[0]
        flow = Flow('F','actual SDK verifier', (Node('case','CASE',start=True),Node('answer','PROJECTION',phase='return',caller='case',end=True)),
                    (('case','answer'),), relations=(Relation('R',{'expression':Read('case','arg.expression')},Read('answer'),on='answer'),))
        binding = SimpleNamespace(flow=flow, scenario=event, anchor=target, anchor_index=index, field_map={'expression':'expression'},
            testnode=native.relative_to(root).as_posix()+'::test_case[1]', observed_rule='R', relation_indices=(0,),
            actual_targets=(target.target,), targets=(target.target,loader.is_literal.__module__+':is_literal'))
        scope, item = bind_scenario(root,binding)
        assert loader.is_literal(ast.Constant(1)) is True
        mutant=next(m for m in sites.mutants_of(sites.sites_of(loader.is_literal),set())
                    if m.how=='negate' and m.site.text=='isinstance(node, ast.Constant)')
        code=sites.mutant_code(loader.is_literal,mutant)
        original=loader.is_literal.__code__
        with sites.installed(loader.is_literal,code):
            actual=calibration._observe_scenario_current(root,binding,{'expression':'1'})
            assert actual.status=='ok' and actual.value is False,actual.reasons
            assert loader.is_literal.__code__ is code
            with calibration.session(Runtime(root),[item],nextitem=scope.nextitem):
                unprepared=calibration._observe_scenario_current(root,binding,{'expression':'1'})
                assert unprepared.status=='grey' and 'prepared' in ' '.join(unprepared.reasons)
        assert loader.is_literal.__code__ is original and loader.is_literal(ast.Constant(1)) is True


def test_scenario_parameter_point_type_mismatch_is_red(tmp_path):
    binding = scenario(tmp_path)
    bind_scenario(tmp_path, binding)
    actual = calibration.execute_scenario(tmp_path, binding, {'x': 'not-an-int'})
    assert actual.status == 'red' and actual.value is None
    assert 'parameter type' in ' '.join(actual.reasons)


def test_repeated_current_scenario_keeps_the_same_real_items_and_imports(tmp_path):
    binding = scenario(tmp_path)
    scope, item = bind_scenario(tmp_path, binding)
    native = importlib.import_module('policy')
    for x, expected in [(4,False),(2,True),(4,False)]:
        result = calibration._observe_scenario_current(tmp_path,binding,{'x':x})
        assert result.status=='ok' and result.value is expected,result.reasons
        assert calibration._context(tmp_path,binding.testnode)==(scope,item)
        assert importlib.import_module('policy') is native


def test_native_plugin_and_calibration_share_one_verified_source_owner(tmp_path):
    binding = scenario(tmp_path)
    file = tmp_path / 'test_case.py'
    file.write_text(file.read_text().replace('# flowguard: event CASE(x: int)', '# flowguard: event CASE(x: int; request)').replace('def test_case(x: int):','def test_case(x: int, request):')+
                    '    from flowguard.intent import calibration as native_backend\n    assert request.config.pluginmanager.get_plugin("flowguard.intent.plugin") is not None\n    assert native_backend.probe_context(request.config)\n')
    index = anchors.collect_sources(tmp_path,[('policy.py','policy'),('test_case.py','test_case',True)])
    binding.anchor_index,binding.scenario = index,index.named('CASE')[0]
    scope,item = bind_scenario(tmp_path,binding)
    actual = calibration.execute_scenario(tmp_path,binding,{'x':4})
    assert actual.status=='ok' and actual.value is False,actual.reasons
    assert item.config is scope.items[0].config


def test_super_method_mutant_keeps_the_actual_anchor_code_identity(tmp_path):
    binding = scenario(tmp_path)
    (tmp_path/'policy.py').write_text('''class Base:
    def offset(self): return 0
class Policy(Base):
    # flowguard: sensor choice(x: count) -> allowed: bool
    def choice(self, x: int) -> bool:
        return x + super().offset() <= 3
''')
    case=tmp_path/'test_case.py';case.write_text(case.read_text().replace('from policy import choice','from policy import Policy').replace('answer=choice(x)','answer=Policy().choice(x)'))
    index=anchors.collect_sources(tmp_path,[('policy.py','policy'),('test_case.py','test_case',True)])
    binding.anchor_index,binding.scenario,binding.anchor = index,index.named('CASE')[0],index.named('choice')[0]
    binding.actual_targets=binding.targets=(binding.anchor.target,)
    bind_scenario(tmp_path,binding)
    fn=importlib.import_module('policy').Policy.choice
    mutant=next(m for m in sites.mutants_of(sites.sites_of(fn),set()) if m.how=='flip')
    code=sites.mutant_code(fn,mutant);original=fn.__code__
    with sites.installed(fn,code):
        actual=calibration._observe_scenario_current(tmp_path,binding,{'x':3})
        assert actual.status=='ok' and actual.value is False,actual.reasons
        assert fn.__code__ is code and code.co_qualname==fn.__qualname__
    assert fn.__code__ is original

"""Scenario observations use actual items in the existing pytest session."""
import ast
from contextlib import ExitStack
import importlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from flowguard.intent import anchors, calibration, sites
from flowguard.intent.flow import Flow, Node, Read, Relation
from flowguard.intent.cells import Raised
from flowguard.intent.runtime import Runtime
from tests.intent_engine._source_fixture import source_sessions
from tests.intent_engine._protocol_controls import bind_scenario

def scenario(tmp_path, *, enum=False, refusal=False, extra='', value=2, call=None, code=None):
    if enum:
        (tmp_path/'kinds.py').write_text('from enum import Enum\nclass QuoteCase(Enum):\n    EXACT="exact"\n    CHANGED="changed"\n')
        (tmp_path/'policy.py').write_text('''from kinds import QuoteCase
# flowguard: sensor choice(quote: kind) -> allowed: bool
def choice(quote: QuoteCase) -> bool:
    return quote is QuoteCase.EXACT
''')
        declaration='quote: QuoteCase'; values='QuoteCase.EXACT'; imports='from kinds import QuoteCase\n'; call='choice(quote)'; field='quote'
    else:
        (tmp_path/'policy.py').write_text(code or '''# flowguard: sensor choice(x: count) -> allowed: bool
def choice(x: int) -> bool:
    if x < 0: raise ValueError('native negative refusal')
    return x <= 3
''')
        declaration='x: int';values=str(value);imports='';call=call or 'choice(x)';field='x'
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
    identifier='QuoteCase.EXACT' if enum else str(value)
    return SimpleNamespace(flow=model,scenario=entry,anchor=target,anchor_index=index,
                           field_map={field:field},testnode='test_case.py::test_case['+identifier+']',
                           observed_rule='RULE',relation_indices=tuple(range(len(relations))),actual_targets=(target.target,),targets=(target.target,))


def test_scenario_gets_actual_production_result_not_test_none_or_predicate(tmp_path):
    binding = scenario(tmp_path)
    bind_scenario(tmp_path, binding)
    actual = calibration._observe_scenario_current(tmp_path, binding, {'x': 2})
    assert actual.status == 'ok' and actual.value is True, actual.reasons
    # Another input is put into the call the scenario test made and evaluated sealed (design 4.5, 8):
    # the production function's own result, never the test's None, the rule predicate or a second run.
    actual = calibration._observe_scenario_current(tmp_path, binding, {'x': 4})
    assert actual.status == 'ok' and actual.value is False, actual.reasons


@pytest.mark.parametrize('call,code,reason', [
    # The test computes the argument: another x is not the same expression's value.
    ('choice(x + 0)', None, 'not compared: the scenario test computes the x argument of choice from x; '
                            'the sealed environment does not run the test'),
    # The production function reads a binding the sealed environment does not have (design 4.5 whitelist).
    ('choice(x)', 'LIMIT = int("3")\n# flowguard: sensor choice(x: count) -> allowed: bool\n'
                  'def choice(x: int) -> bool:\n    return x <= LIMIT\n', 'uses unavailable binding LIMIT'),
])
def test_another_scenario_input_is_not_compared_when_the_sealed_call_cannot_take_it(tmp_path, call, code, reason):
    binding = scenario(tmp_path, call=call, code=code)
    bind_scenario(tmp_path, binding)
    actual = calibration._observe_scenario_current(tmp_path, binding, {'x': 2})
    assert actual.status == 'ok' and actual.value is True, actual.reasons       # the recorded input is observed
    actual = calibration._observe_scenario_current(tmp_path, binding, {'x': 4})
    assert actual.status == 'grey' and actual.value is None and actual.reasons == (reason,), actual.reasons


HELPERS = "STORE = {}\nLIMIT = 2\nARGUMENTS = [2]\ndef put(value):\n    STORE['value'] = value\n"


@pytest.mark.parametrize('call,read,parameter', [
    # The test fills a dict through an alias; at x=4 the real call is choice(4), which is False.
    ("None\n    box = {}\n    alias = box\n    alias['value'] = x\n    answer = choice(box['value'])", "box['value']", 'x'),
    # A helper of the test module stores x in a module dict; the real call at x=4 is choice(4) again.
    ("None\n    put(x)\n    answer = choice(STORE['value'])", "STORE['value']", 'x'),
    # A module name: another call could change it, and its value at another input was not recorded.
    ('choice(LIMIT)', 'LIMIT', 'x'),
    # Arguments unpacked from a module list do not bind to a parameter at all.
    ('choice(*ARGUMENTS)', '*ARGUMENTS', 'unpacked'),
])
def test_an_argument_that_is_not_a_literal_or_an_unchanged_input_is_not_compared_at_another_input(tmp_path, call, read,
                                                                                                    parameter):
    # The recorded call's arguments are reused only where the test's own expression gives the same value at every
    # input; any other argument may carry the changed input in a way the test's source does not show.
    binding = scenario(tmp_path, call=call, extra=HELPERS)
    bind_scenario(tmp_path, binding)
    actual = calibration._observe_scenario_current(tmp_path, binding, {'x': 2})
    assert actual.status == 'ok' and actual.value is True, actual.reasons       # the recorded input is observed
    actual = calibration._observe_scenario_current(tmp_path, binding, {'x': 4})
    assert actual.status == 'grey' and actual.value is None and actual.reasons == (
        f'not compared: the scenario test passes {read} as the {parameter} argument of choice; only a literal, or an '
        'input of a fixed value that the test never assigns, is known at another input',), actual.reasons


CHOSEN = 'not compared: the scenario test chooses whether to call choice by x; what it does at another input was not recorded'
LOOP = ('not compared: the scenario test calls choice in a loop that reads x; how often it calls it at another input '
        'was not recorded')
BEFORE = ('not compared: the scenario test reads x before its call of choice, in code the sealed point does not '
          'evaluate; what it does then at another input was not recorded')


@pytest.mark.parametrize('call,reason', [
    # At x=4 the real test calls choice(9), which is False, not the recorded choice(2).
    ("None\n    if x <= 3:\n        answer = choice(2)\n    else:\n        answer = choice(9)", CHOSEN),
    # At x=4 the real test calls choice(0), which is True, not choice(4).
    ("None\n    if x <= 3:\n        answer = choice(x)\n    else:\n        answer = choice(0)", CHOSEN),
    # A conditional expression and a boolean operand decide the same way whether choice runs.
    ('choice(2) if x <= 3 else choice(9)', CHOSEN),
    ('x <= 3 and choice(2)', CHOSEN),
    ("None\n    match x:\n        case 2:\n            answer = choice(2)", CHOSEN),
    # A loop over the input decides how often choice runs.
    ("None\n    for limit in (x,):\n        answer = choice(2)", LOOP),
    # An earlier return, assert or call on the input may end the test before its call.
    ("None\n    if x > 3:\n        return\n    answer = choice(2)", BEFORE),
    ("None\n    assert x <= 3\n    answer = choice(2)", BEFORE),
    ("None\n    str(x)\n    answer = choice(2)", BEFORE),
])
def test_a_call_the_changed_input_may_steer_is_not_compared_at_another_input(tmp_path, call, reason):
    # What the test does at another input is what its source does with that input; only the calls it makes the
    # same way at every input are put in place and evaluated sealed.
    binding = scenario(tmp_path, call=call)
    bind_scenario(tmp_path, binding)
    actual = calibration._observe_scenario_current(tmp_path, binding, {'x': 2})
    assert actual.status == 'ok' and actual.value is True, actual.reasons       # the recorded input is observed
    actual = calibration._observe_scenario_current(tmp_path, binding, {'x': 4})
    assert actual.status == 'grey' and actual.value is None and actual.reasons == (reason,), actual.reasons


TWO = """# flowguard: sensor choice(x: count, y: count) -> allowed: bool
def choice(x: int, y: int = 0) -> bool:
    return x <= y
"""


@pytest.mark.parametrize('call,reason', [
    # partial(choice, 3)(x) calls choice(3, x): at x=4 the real call is choice(3, 4), which is True. Read
    # against choice's own parameters, the call expression would put 4 into choice's x.
    ("None\n    f = functools.partial(choice, 3)\n    answer = f(x)",
     "not compared: the recorded call of choice has x=3 while the scenario test's input x is 2; the call does not "
     "pass that input straight to choice"),
    # partial(choice, 2)(x) at x=2 is choice(2, 2), so the values agree; at x=4 the real call is choice(2, 4).
    ("None\n    f = functools.partial(choice, 2)\n    answer = f(x)",
     'not compared: the scenario test calls choice through f, not by a module name for the function itself; how '
     'that passes its arguments was not recorded'),
])
def test_a_call_expression_that_is_not_the_anchor_itself_is_not_compared_at_another_input(tmp_path, call, reason):
    binding = scenario(tmp_path, call=call, code=TWO, extra='import functools\n')
    bind_scenario(tmp_path, binding)
    recorded = calibration._observe_scenario_current(tmp_path, binding, {'x': 2})
    assert recorded.status == 'ok', recorded.reasons
    actual = calibration._observe_scenario_current(tmp_path, binding, {'x': 4})
    assert actual.status == 'grey' and actual.value is None and actual.reasons == (reason,), actual.reasons


def test_a_call_of_the_anchor_through_its_module_is_put_in_place_at_another_input(tmp_path):
    binding = scenario(tmp_path, call='policy.choice(x)', extra='import policy\n')
    bind_scenario(tmp_path, binding)
    actual = calibration._observe_scenario_current(tmp_path, binding, {'x': 4})
    assert actual.status == 'ok' and actual.value is False, actual.reasons      # the real test calls choice(4)


def test_a_literal_argument_is_the_recorded_call_at_every_input(tmp_path):
    # choice(2) does not read x: at x=4 the real test calls choice(2) again, which is True.
    binding = scenario(tmp_path, call='choice(2)')
    bind_scenario(tmp_path, binding)
    for x in (2, 4):
        actual = calibration._observe_scenario_current(tmp_path, binding, {'x': x})
        assert actual.status == 'ok' and actual.value is True, (x, actual.reasons)


def test_scenario_test_that_assigns_its_input_is_not_compared_at_another_input(tmp_path):
    binding = scenario(tmp_path, call='choice(x)\n    x = 0')
    bind_scenario(tmp_path, binding)
    actual = calibration._observe_scenario_current(tmp_path, binding, {'x': 4})
    assert actual.status == 'grey' and actual.reasons == (
        'not compared: the scenario test assigns x; another input cannot be put into its calls',), actual.reasons


def test_a_sealed_point_that_raises_is_read_through_the_declared_refusal_node(tmp_path):
    # The test ran with x=2 and returned; at x=-1 the sealed call raises, the error leaves the test (no try or
    # with block around the call), and the Flow reads it at its raise node, as the real run would.
    binding = scenario(tmp_path, refusal=True)
    bind_scenario(tmp_path, binding)
    actual = calibration._observe_scenario_current(tmp_path, binding, {'x': -1})
    assert actual.status == 'ok' and isinstance(actual.value, Raised), actual.reasons
    assert type(actual.value.error) is ValueError and str(actual.value.error) == 'native negative refusal'
    guarded = scenario(tmp_path, refusal=True, call='None\n    try:\n        answer = choice(x)\n    except ValueError:\n        raise')
    bind_scenario(tmp_path, guarded)
    actual = calibration._observe_scenario_current(tmp_path, guarded, {'x': -1})
    assert actual.status == 'grey' and actual.reasons == (
        'not compared: choice raises with these inputs inside a try or with block of the scenario test; '
        'what the test does then was not recorded',), actual.reasons


def test_scenario_enum_identity_is_real_member_not_its_string_value(tmp_path):
    binding = scenario(tmp_path, enum=True)
    bind_scenario(tmp_path, binding)
    enum = importlib.import_module('kinds').QuoteCase
    actual = calibration._observe_scenario_current(tmp_path, binding, {'quote': enum.EXACT})
    assert actual.status == 'ok' and actual.value is True, actual.reasons
    # The sealed environment has no project enum class: the other member is not compared, with why.
    actual = calibration._observe_scenario_current(tmp_path, binding, {'quote': enum.CHANGED})
    assert actual.status == 'grey' and actual.value is None and actual.reasons == ('uses attribute EXACT',), actual.reasons
    forged = object.__new__(enum)
    forged._name_, forged._value_ = 'CHANGED', 'not-the-value'
    actual = calibration._observe_scenario_current(tmp_path, binding, {'quote': forged})
    assert actual.status == 'grey' and actual.value is None
    copied = object.__new__(enum)
    copied._name_, copied._value_ = enum.CHANGED.name, enum.CHANGED.value
    actual = calibration._observe_scenario_current(tmp_path, binding, {'quote': copied})
    assert actual.status == 'grey' and actual.value is None


def test_scenario_only_declared_native_error_can_be_refused(tmp_path):
    # The test ran with x=-1: the production refusal it propagated is the declared outcome, not a failure.
    binding = scenario(tmp_path, refusal=True, value=-1)
    bind_scenario(tmp_path, binding)
    actual = calibration._observe_scenario_current(tmp_path, binding, {'x': -1})
    assert actual.status == 'ok' and isinstance(actual.value, Raised), actual.reasons
    assert type(actual.value.error) is ValueError and str(actual.value.error) == 'native negative refusal'
    fresh = scenario(tmp_path, extra="    raise ValueError('test harness failure')\n")
    bind_scenario(tmp_path, fresh)
    actual = calibration._observe_scenario_current(tmp_path, fresh, {'x': 2})
    assert actual.status == 'red' and not isinstance(actual.value, Raised)
    assert actual.reasons == ('real calibration test did not pass completely: call failed',), actual.reasons


def test_scenario_does_not_choose_first_or_last_reading(tmp_path):
    binding = scenario(tmp_path, extra='    choice(x)\n')
    bind_scenario(tmp_path, binding)
    actual = calibration._observe_scenario_current(tmp_path, binding, {'x': 4})
    assert actual.status == 'grey' and actual.value is None


def test_scenario_runtime_failure_is_not_a_business_refusal(tmp_path, monkeypatch):
    flow = importlib.import_module('flowguard.intent.flow')
    binding = scenario(tmp_path)
    bind_scenario(tmp_path, binding)
    def failed(*args, **kwargs): raise ValueError('real projection infrastructure failure')
    monkeypatch.setattr(flow, 'relation_observations', failed)
    actual = calibration._observe_scenario_current(tmp_path, binding, {'x': 2})
    assert actual.status == 'grey' and actual.value is None
    assert actual.reasons == ('scenario verification failed: ValueError: real projection infrastructure failure',), actual.reasons


def test_scenario_checks_requested_logical_inputs_for_joint_witnesses(tmp_path):
    binding = scenario(tmp_path)
    bind_scenario(tmp_path, binding)
    binding.requested_inputs = {'x': 99}
    actual = calibration._observe_scenario_current(tmp_path, binding, {'x': 2})
    assert actual.status == 'grey' and actual.value is None
    assert 'input did not match' in ' '.join(actual.reasons)


def test_scenario_never_uses_test_return_or_rule_predicate_as_actual(tmp_path):
    binding = scenario(tmp_path, extra='    return True\n', value=4)
    class ExplosiveRule:
        id = 'RULE'
        def eval(self, *args): raise AssertionError('rule predicate used as actual')
    relation = binding.flow.relations[0]
    binding.flow.relations = (Relation(ExplosiveRule(), relation.inputs, relation.actual, relation.on),)
    bind_scenario(tmp_path, binding)
    actual = calibration._observe_scenario_current(tmp_path, binding, {'x': 4})
    assert actual.status == 'ok' and actual.value is False, actual.reasons     # the production result, not the test's True


def test_enum_source_binding_must_be_the_actual_native_class(tmp_path):
    binding = scenario(tmp_path, enum=True)
    file = tmp_path / 'test_case.py'
    file.write_text(file.read_text()+"\nfrom enum import Enum\nQuoteCase = Enum('QuoteCase', {'EXACT':'exact','CHANGED':'changed'})\n")
    index = anchors.collect_sources(tmp_path, [('policy.py','policy'),('test_case.py','test_case',True)])
    binding.anchor_index, binding.scenario = index, index.named('CASE')[0]
    bind_scenario(tmp_path, binding)
    exact = importlib.import_module('kinds').QuoteCase.EXACT
    actual = calibration._observe_scenario_current(tmp_path, binding, {'quote': exact})
    assert actual.status == 'grey' and actual.value is None
    assert actual.reasons == ('enum parameter has no matching actual source type',), actual.reasons


def test_real_probe_plugin_does_not_write_ordinary_cache_or_project_map(tmp_path):
    binding = scenario(tmp_path)
    file = tmp_path / 'pyproject.toml'; file.write_text(file.read_text()+'addopts="-p flowguard.intent.plugin"\n')
    bind_scenario(tmp_path, binding)
    actual = calibration._observe_scenario_current(tmp_path, binding, {'x': 2})
    assert actual.status == 'ok' and actual.value is True, actual.reasons
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
            # The scenario was recorded before the mutant existed: its outcome is never reported as the mutant's.
            actual=calibration._observe_scenario_current(root,binding,{'expression':'1'})
            assert actual.status=='grey' and actual.value is None,actual.reasons
            assert actual.reasons==("the scenario was recorded before code instrumentation; its outcome is not the instrumented code's",)
            assert loader.is_literal.__code__ is code
            with calibration.session(Runtime(root),[item],nextitem=scope.nextitem):
                unprepared=calibration._observe_scenario_current(root,binding,{'expression':'1'})
                assert unprepared.status=='grey' and 'prepared' in ' '.join(unprepared.reasons)
        assert loader.is_literal.__code__ is original and loader.is_literal(ast.Constant(1)) is True


def test_scenario_parameter_point_type_mismatch_is_red(tmp_path):
    binding = scenario(tmp_path)
    bind_scenario(tmp_path, binding)
    actual = calibration._observe_scenario_current(tmp_path, binding, {'x': 'not-an-int'})
    assert actual.status == 'red' and actual.value is None
    assert 'parameter type' in ' '.join(actual.reasons)


def test_repeated_current_scenario_keeps_the_same_real_items_and_imports(tmp_path):
    binding = scenario(tmp_path)
    scope, item = bind_scenario(tmp_path, binding)
    native = importlib.import_module('policy')
    for x, expected in [(2,True),(4,False),(2,True)]:
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
    actual = calibration._observe_scenario_current(tmp_path,binding,{'x':2})
    assert actual.status=='ok' and actual.value is True,actual.reasons
    assert scope.runtime.outcomes == {}          # the native test's own probe_context assertion passed
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
        actual=calibration._observe_scenario_current(tmp_path,binding,{'x':2})
        assert actual.status=='grey' and actual.value is None,actual.reasons
        assert 'before code instrumentation' in actual.reasons[0]
        assert fn.__code__ is code and code.co_qualname==fn.__qualname__
    assert fn.__code__ is original

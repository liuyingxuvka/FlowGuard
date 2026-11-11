"""Deep observations retain source-bound points and exact factory provenance."""
from types import SimpleNamespace

import pytest

from flowguard.intent import anchors, calibration, sites
from flowguard.intent.cells import Raised
from flowguard.intent.flow import Flow, Node, Read, Relation
from tests.intent_engine._source_fixture import source_sessions
from tests.intent_engine._protocol_controls import bind_scenario
from tests.intent_engine.test_guard_regressions import make


def tuple_case(root, *, explicit_context=False, mapped=True):
    (root / 'pyproject.toml').write_text('[tool.pytest.ini_options]\npythonpath=["."]\n')
    (root / 'tuple_business.py').write_text('''# flowguard: sensor CHECK(values: tuple) -> accepted: bool
def choice(values: tuple) -> bool:
    return values == ('red',)
''')
    declaration = '; values' if explicit_context else 'values: tuple'
    (root / 'test_tuple_case.py').write_text('''import pytest
from tuple_business import choice
@pytest.fixture
def values(): return ()
# flowguard: event CASE(''' + declaration + ''')
def test_case(values: tuple):
    answer = choice(values)
    assert type(answer) is bool
''')
    index = anchors.collect_sources(root, [('tuple_business.py','tuple_business'),
        ('test_tuple_case.py','test_tuple_case',True)])
    event, target = index.named('CASE')[0], index.named('CHECK')[0]
    flow = Flow('F','assumed: actual tuple scenario',
        (Node('case','CASE',start=True),Node('answer','CHECK',phase='return',caller='case',end=True)),
        (('case','answer'),),relations=(Relation('R',{'values':Read('case','arg.values')},Read('answer'),on='answer'),))
    binding = SimpleNamespace(flow=flow,scenario=event,anchor=target,anchor_index=index,
        field_map={'values':'values'} if mapped else {}, testnode='test_tuple_case.py::test_case',
        observed_rule='R',relation_indices=(0,),actual_targets=(target.target,),targets=(target.target,))
    bind_scenario(root,binding)
    return binding


def test_declared_tuple_points_use_actual_native_tests_without_creating_a_kind(tmp_path):
    binding=tuple_case(tmp_path)
    parameter=binding.scenario.parameters[0]
    assert anchors.parameter_kind(parameter, ()) is None
    for point,expected in [((),False),(('red',),True)]:
        actual=calibration._observe_scenario_current(tmp_path,binding,{'values':point})
        assert actual.status=='ok' and actual.value is expected,actual.reasons
    with pytest.raises(ValueError):
        anchors._kind('tuple')


@pytest.mark.parametrize('explicit_context,mapped,point', [
    (True,True,('red',)), (False,False,('red',)), (False,True,(['red'],)),
])
def test_tuple_point_cannot_replace_explicit_unmapped_or_mutable_context(tmp_path,explicit_context,mapped,point):
    binding=tuple_case(tmp_path,explicit_context=explicit_context,mapped=mapped)
    actual=calibration._observe_scenario_current(tmp_path,binding,{'values':point})
    assert actual.status in {'red','grey'} and actual.value is None,actual
    assert 'context' in ' '.join(actual.reasons)


def test_real_probe_factory_is_observed_but_equal_unregistered_code_is_not(tmp_path):
    from flowguard.intent import probe
    code='def accept(flag): return flag and True\n'
    intent='''from flowguard.intent import rule
@rule('FLAG',decides='flag',fields={'flag':bool},source='assumed: actual flag')
def FLAG(flag): return flag
'''
    model,engine=make(tmp_path,code,intent,scenario_case=dict(rule='FLAG',target='accept',
        parameters={'flag':'bool'},source_parameters={'flag':'bool'},body='answer=app.accept(flag)\nassert type(answer) is bool'))
    home=model.rules['FLAG'].homes[0]
    function,points,_=engine.home_sites(home.target)
    original=function.__code__
    candidate=sites.probe_code(function,0,points,home=True)
    assert engine.call(home,{'flag':True},function,{}) is True
    probe.start()
    try:
        with sites.installed(function,candidate):
            assert sites.controlled_mutation(function,candidate)
            probe.CASE=0
            actual=engine.call(home,{'flag':True},function,{})
            assert actual is True,repr(actual)
    finally:
        records=probe.take()
    assert records and function.__code__ is original
    duplicate=candidate.replace()
    assert duplicate==candidate and duplicate is not candidate
    with sites.installed(function,duplicate):
        assert not sites.controlled_mutation(function,duplicate)
        rejected=engine.call(home,{'flag':True},function,{})
        assert isinstance(rejected,Raised) and 'unverified' in str(rejected.error)
    assert function.__code__ is original

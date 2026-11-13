"""Calibrated source syntax reuses real collected tests and their fresh fixtures."""
from pathlib import Path
import subprocess
import sys

from flowguard.intent import anchors, calibration


POLICY = '''from enum import Enum
class QuoteCase(Enum):
    EXACT = 'exact'
    CHANGED = 'changed'

# flowguard: sensor CHOICE(x: count) -> allowed: bool
def choice(x: int) -> bool:
    if x < 0: raise ValueError('native negative refusal')
    return x <= 3

# flowguard: sensor QUOTE(quote: kind) -> allowed: bool
def quote_allows(quote: QuoteCase) -> bool:
    return quote is QuoteCase.EXACT

# flowguard: sensor CALIBRATED(x: count) -> allowed: bool calibrated_by=test_native.py::test_sensor
def calibrated(x: int) -> bool:
    return x <= 3
'''

NATIVE = '''import pytest
from policy import choice, calibrated, quote_allows, QuoteCase

@pytest.fixture
def x(): return 2

@pytest.fixture
def cleanup():
    state = {'fail': False}
    yield state
    assert not state['fail'], 'actual fixture cleanup failure'

@pytest.fixture
def quote(): return QuoteCase.EXACT

# flowguard: event CASE(x: int)
def test_case(x: int):
    answer = choice(x)
    assert type(answer) is bool

# flowguard: event DUPLICATE(x: int)
def test_duplicate(x: int):
    choice(x)
    choice(x)

# flowguard: event HARNESS(x: int)
def test_harness(x: int):
    choice(x)
    if x == 4: raise ValueError('actual harness failure')

# flowguard: event CLEANUP(x: int; cleanup)
def test_cleanup(x: int, cleanup):
    choice(x)
    cleanup['fail'] = x == 4

# flowguard: event RETURN(x: int)
def test_return(x: int):
    choice(x)
    return True

# flowguard: event ENUM(quote: QuoteCase)
def test_enum(quote: QuoteCase):
    answer = quote_allows(quote)
    assert type(answer) is bool

def test_sensor():
    assert calibrated(2) is True

def test_audit(): pass
'''

AUDIT = '''from pathlib import Path
from types import SimpleNamespace
from enum import Enum
import ast
import pytest
import policy
from flowguard.intent import anchors, calibration, sites
from flowguard.intent.cells import Raised
from flowguard.intent.flow import Flow, Node, Read, Relation
from flowguard.intent.runtime import Runtime

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    if item.name == 'test_audit':
        root = Path(__file__).parent
        index = anchors.collect_sources(root, [('policy.py','policy'), ('test_native.py','test_native',True)])
        assert not index.issues,index.issues
        runtime = Runtime(root)
        def binding(name='CASE', test='test_case', target='CHOICE', field='x'):
            actual = index.named(target)[0]
            model = Flow('F_'+name,'actual source',
                (Node('case',name,start=True),Node('answer',target,phase='return',caller='case',end=True),Node('denied',target,phase='raise',caller='case',end=True)),
                (('case','answer'),('case','denied')),
                relations=(Relation('R',{field:Read('case','arg.'+field)},Read('answer'),on='answer'),Relation('R',{field:Read('case','arg.'+field)},Read('denied','error'),on='denied')))
            prepared = SimpleNamespace(flow=model,scenario=index.named(name)[0],anchor=actual,anchor_index=index,
                field_map={field:field},testnode='test_native.py::'+test,observed_rule='R',
                relation_indices=(0,1),actual_targets=(actual.target,),targets=(actual.target,))
            calibration._prepare_scenario(root, prepared)
            return prepared
        with calibration.session(runtime,item.session.items,nextitem=item):
            native = binding()
            changed = calibration._observe_scenario_current(root,native,{'x':4})
            assert changed.status=='ok' and changed.value is False,changed
            original = calibration._observe_scenario_current(root,native,{'x':2})
            assert original.status=='ok' and original.value is True,original
            denied = calibration._observe_scenario_current(root,native,{'x':-1})
            assert denied.status=='ok' and isinstance(denied.value,Raised),denied
            assert type(denied.value.error) is ValueError
            assert str(denied.value.error)=='native negative refusal'
            native.requested_inputs={'x':99}
            mismatch=calibration._observe_scenario_current(root,native,{'x':2})
            assert mismatch.status=='grey' and mismatch.value is None,mismatch
            native.requested_inputs={'x':4}
            wrong_type=calibration._observe_scenario_current(root,native,{'x':'bad'})
            assert wrong_type.status=='red' and wrong_type.value is None,wrong_type
            repeated=calibration._observe_scenario_current(root,binding('DUPLICATE','test_duplicate'),{'x':4})
            assert repeated.status=='grey' and repeated.value is None,repeated
            for name,test in [('HARNESS','test_harness'),('CLEANUP','test_cleanup')]:
                failed=calibration._observe_scenario_current(root,binding(name,test),{'x':4})
                assert failed.status=='red' and failed.value is None,failed
            returned=calibration._observe_scenario_current(root,binding('RETURN','test_return'),{'x':4})
            assert returned.status=='ok' and returned.value is False,returned
            enum_case=binding('ENUM','test_enum','QUOTE','quote')
            enum_ok=calibration._observe_scenario_current(root,enum_case,{'quote':policy.QuoteCase.CHANGED})
            assert enum_ok.status=='ok' and enum_ok.value is False,enum_ok
            wrong_class=Enum('QuoteCase',{'EXACT':'exact','CHANGED':'changed'},module='policy')
            enum_bad=calibration._observe_scenario_current(root,enum_case,{'quote':wrong_class.CHANGED})
            assert enum_bad.status=='grey' and enum_bad.value is None,enum_bad
            sensor=index.named('CALIBRATED')[0]
            point=calibration.execute(root,sensor,{'x':4})
            assert point.status=='ok' and point.value is False,point
            wrong_point=calibration.execute(root,sensor,{'x':'bad'})
            assert wrong_point.status=='red' and wrong_point.value is None,wrong_point
            original_code=policy.choice.__code__
            assert policy.choice(3) is True
            mutant=next(m for m in sites.mutants_of(sites.sites_of(policy.choice),set())
                        if m.how=='flip' and m.site.text=='x <= 3')
            code=sites.mutant_code(policy.choice,mutant)
            with sites.installed(policy.choice,code):
                native.requested_inputs={'x':3}
                observed=calibration._observe_scenario_current(root,native,{'x':3})
                assert observed.status=='ok' and observed.value is False,observed
                assert policy.choice.__code__ is code
            assert policy.choice.__code__ is original_code and policy.choice(3) is True
            native.requested_inputs={'x':2}
            with calibration.session(Runtime(root),item.session.items,nextitem=item):
                unprepared=calibration._observe_scenario_current(root,native,{'x':2})
                assert unprepared.status=='grey' and unprepared.value is None,unprepared
                assert 'prepared' in ' '.join(unprepared.reasons)
    yield
'''




def test_missing_real_session_never_builds_a_runner(tmp_path):
    (tmp_path/'policy.py').write_text(POLICY)
    (tmp_path/'test_native.py').write_text(NATIVE)
    index=anchors.collect_sources(tmp_path,[('policy.py','policy')])
    result=calibration.execute(tmp_path,index.named('CALIBRATED')[0],{'x':4})
    assert result.status=='grey' and result.value is None
    assert 'existing collected pytest session' in str(result.reasons)

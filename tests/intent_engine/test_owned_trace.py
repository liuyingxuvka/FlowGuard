"""Both real SDK observation scopes survive; a debugger remains external."""
from dataclasses import replace
from pathlib import Path
import sys

import pytest

from flowguard.intent import anchors, calibration
from flowguard.intent.cells import Raised
from flowguard.intent.flow import Capture
from tests.intent_engine.test_scenario_execution import scenario
from tests.intent_engine.test_calibration import project
from tests.intent_engine._protocol_controls import bind_anchor, bind_scenario
from tests.intent_engine._source_fixture import source_sessions




@pytest.mark.parametrize('value,actual', [(2,True),(4,False)])
def test_single_monitor_and_interceptor_share_the_same_owned_trace_rule(tmp_path,value,actual):
    anchor=project(tmp_path,'''# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
''','''from policy import limit
def test_native():
    assert limit(2) is True
''')
    scope,_=bind_anchor(tmp_path,anchor)
    import importlib
    module=importlib.import_module('policy')
    alias,original=module.limit,module.limit.__code__
    index=anchors.collect_sources(tmp_path,[('policy.py','policy')])
    ambient=sys.gettrace()
    # Ordinary coverage receives this actual direct call; the explicit runtime records
    # that same call once, privately, and replays nothing beside it.
    with Capture(tmp_path,index,'outer',_ordinary=True) as outer:
        owned=sys.gettrace()
        with scope.runtime.hook(module.limit,name='limit',private=True):
            result=alias(value)
        assert sys.gettrace() is owned
    assert sys.gettrace() is ambient
    assert result is actual
    assert module.limit is alias and alias.__code__ is original
    assert [(e.phase,e.occurrence)for e in outer.events]==[('call',1),('return',1)]
    assert outer.events[0].values['x']==value
    assert outer.events[1].result is actual and outer.issues==[]
    reading=scope.runtime.readings[-1]
    assert reading.actual==({'x':value},actual) and reading.actual[1] is actual and reading.rows==[]


def test_nested_captures_share_the_sdk_owner_and_restore_exact_ambient(tmp_path):
    binding=scenario(tmp_path)
    bind_scenario(tmp_path,binding)
    from flowguard.intent.config import load_config,setup_path
    from flowguard.intent.imports import prepare
    import importlib
    setup_path(load_config(tmp_path));prepare(tmp_path)
    module=importlib.import_module('policy')
    ambient=sys.gettrace()
    with Capture(tmp_path,binding.anchor_index,'outer') as outer:
        owned=sys.gettrace()
        with Capture(tmp_path,binding.anchor_index,'inner') as inner:
            assert module.choice(4) is False
        assert sys.gettrace() is owned
    assert sys.gettrace() is ambient
    assert outer.issues==inner.issues==[]
    assert [(e.phase,e.result,e.occurrence)for e in outer.events]==[('call',None,1),('return',False,1)]
    assert [(e.phase,e.result,e.occurrence)for e in inner.events]==[('call',None,1),('return',False,1)]




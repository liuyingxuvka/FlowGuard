"""The native harness suppresses only its own bootstrap metadata."""
from pathlib import Path

from flowguard.intent import anchors
from flowguard.intent.flow import Capture
from flowguard.intent.runtime import _PRIVATE
from flowguard.structure import paths
from tests.intent_engine._source_fixture import source_sessions
from tests.intent_engine._protocol_controls import bind_anchor
from tests.intent_engine.test_calibration import project


def test_bootstrap_is_private_but_real_project_boundary_call_remains_ordinary(tmp_path):
    anchor = project(tmp_path, '''# flowguard: sensor LIMIT(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
''', 'from policy import limit\ndef test_native(): assert limit(2) is True\n')
    root = Path(paths.__file__).resolve().parents[2]
    index = anchors.collect_sources(root, [('flowguard/structure/paths.py','flowguard.structure.paths')])
    assert not _PRIVATE.get()
    with Capture(root,index,'real-project-boundary',_ordinary=True) as captured:
        bind_anchor(tmp_path,anchor)
        assert not captured.events, 'bootstrap metadata must not satisfy ordinary coverage'
        assert not _PRIVATE.get(), 'bootstrap must restore observation scope before returning'
        assert paths.project_code(str(root/'flowguard/structure/paths.py'),root) is True
    assert [(event.anchor,event.phase) for event in captured.events] == [('PROJECT_SOURCE','call'),('PROJECT_SOURCE','return')]
    assert captured.events[-1].result is True and not captured.issues

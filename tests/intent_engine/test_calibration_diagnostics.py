"""An unavailable calibration preserves the actual nested pytest failure."""
from flowguard.intent import calibration
from tests.intent_engine.test_calibration import project


def test_calibration_collection_failure_keeps_the_native_error(tmp_path):
    anchor = project(tmp_path, """# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
""", """from policy import limit
raise ImportError('editable collection diagnostic control')
def test_native():
    assert limit(2) is True
""")
    result = calibration._child(dict(operation='stage', root=str(tmp_path),
        anchor=calibration.asdict(anchor), values=calibration._encode({}), stage='baseline'))
    assert result['status'] == 'grey' and 'outcome' not in result
    reason = '\n'.join(result['reasons'])
    assert 'ImportError: editable collection diagnostic control' in reason
    assert 'selected=0' in reason and 'outcomes=0' in reason


def test_collection_diagnostics_do_not_depend_on_warm_traceback_rendering(tmp_path):
    anchor = project(tmp_path, """# flowguard: sensor limit(x: count) -> allowed: bool calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
""", """from policy import limit
raise AssertionError('same native failure')
def test_native():
    assert limit(2) is True
""")
    first = calibration._stage(tmp_path, anchor, {}, 'baseline')
    second = calibration._stage(tmp_path, anchor, {}, 'baseline')
    assert first == second
    assert first['status'] == 'grey' and 'outcome' not in first
    assert 'AssertionError: same native failure' in '\n'.join(first['reasons'])

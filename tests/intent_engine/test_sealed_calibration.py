"""Explicit calibration keeps real fixture evidence beside source-only alternatives."""
import importlib

from flowguard.intent import calibration
from flowguard.intent.cells import Raised
from tests.intent_engine._protocol_controls import bind_anchor
from tests.intent_engine._source_fixture import source_sessions
from tests.intent_engine.test_calibration import project


def test_json_calibration_keeps_one_real_original_call_and_no_synthetic_rows(tmp_path):
    anchor = project(tmp_path, '''# flowguard: same LIMIT(x) calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
''', 'from policy import limit\ndef test_native(): assert limit(2) is True\n')
    scope, _ = bind_anchor(tmp_path, anchor)
    module = importlib.import_module('policy')
    original_code = module.limit.__code__
    calls = []
    with scope.runtime.record(predicate=lambda code: code is original_code, private=True,
                              entry_only=True, callback=lambda frame, event, arg: calls.append(frame.f_locals['x'])):
        observed = calibration.execute(tmp_path, anchor, {'x': 5})
    assert observed.status == 'ok' and observed.value is False, observed
    assert calls == []          # the one real call was the ordinary run's; the point ran sealed
    [reading] = scope.runtime.readings
    assert reading.actual == ({'x': 2}, True)
    assert reading.json_result is True and reading.rows == []


def test_fixture_changed_module_constant_cannot_be_replaced_by_a_sealed_answer(tmp_path):
    anchor = project(tmp_path, '''LIMIT = 3
# flowguard: same LIMIT_CHECK(x) calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= LIMIT
''', '''import pytest
import policy
SEEN = []
@pytest.fixture(autouse=True)
def limit_value(monkeypatch):
    monkeypatch.setattr(policy, 'LIMIT', 9)
def test_native():
    result = policy.limit(5)
    SEEN.append(result)
    assert result is True
''')
    scope, item = bind_anchor(tmp_path, anchor)
    observed = calibration.execute(tmp_path, anchor, {'x': 7})
    assert observed.status == 'grey' and observed.value is None, observed
    assert 'actual named-test outcome differs' in ' '.join(observed.reasons)
    assert scope.runtime.readings[-1].actual == ({'x': 5}, True)
    assert item.module.SEEN == [True]  # the one ordinary run; the refusal never ran the business call again


def test_non_json_fixture_context_is_unavailable_without_a_target_reading(tmp_path):
    anchor = project(tmp_path, '''# flowguard: same LIMIT(x; context) calibrated_by=test_policy.py::test_native
def limit(x: int, context) -> bool:
    return x <= 3
''', '''import pytest
from policy import limit
TOUCHED = []
class Context:
    def __repr__(self):
        TOUCHED.append('repr')
        raise AssertionError('context must not be inspected through repr')
    def __eq__(self, other):
        TOUCHED.append('eq')
        raise AssertionError('context must not be compared')
@pytest.fixture
def context(): return Context()
def test_native(context): assert limit(2, context) is True
''')
    scope, item = bind_anchor(tmp_path, anchor)
    observed = calibration.execute(tmp_path, anchor, {'x': 5})
    assert observed.status == 'grey' and observed.value is None, observed
    assert 'JSON' in ' '.join(observed.reasons)
    # The ordinary run's one reading keeps the real call without a JSON sample; nothing was compared.
    [reading] = scope.runtime.readings
    assert reading.sample is None and reading.reasons == ['not JSON data']
    # The real pytest refusal report may render repr; qualification never uses context equality.
    assert 'eq' not in item.module.TOUCHED


def test_calibrated_fields_belong_to_the_actual_call_not_the_requested_alternative(tmp_path):
    anchor = project(tmp_path, '''# flowguard: same LIMIT(x; config) calibrated_by=test_policy.py::test_native fields threshold=config['limit']
def limit(x: int, config: dict) -> bool:
    return x <= config['limit']
''', '''import pytest
from policy import limit
@pytest.fixture
def config(): return {'limit': 3}
def test_native(config): assert limit(2, config) is True
''')
    scope, _ = bind_anchor(tmp_path, anchor)
    observed = calibration.execute(tmp_path, anchor, {'x': 5})
    assert observed.status == 'ok' and observed.value is False, observed
    reading = scope.runtime.readings[-1]
    assert reading.actual == ({'x': 2, 'config': {'limit': 3}}, True)
    assert reading.fields == {'threshold': 3} and not reading.field_reasons
    assert reading.rows == [] and reading.field_rows == []


def test_non_json_actual_result_cannot_become_a_successful_sealed_reading(tmp_path):
    anchor = project(tmp_path, '''LIMIT = False
# flowguard: same LIMIT_CHECK(x) calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return LIMIT
''', '''import pytest
import policy
@pytest.fixture(autouse=True)
def limit_value(monkeypatch): monkeypatch.setattr(policy, 'LIMIT', object())
def test_native(): assert policy.limit(2) is policy.LIMIT
''')
    scope, _ = bind_anchor(tmp_path, anchor)
    observed = calibration.execute(tmp_path, anchor, {'x': 5})
    assert observed.status == 'grey' and observed.value is None, observed
    assert 'JSON' in ' '.join(observed.reasons)
    assert scope.runtime.readings[-1].sample is None


def test_a_builtin_refusal_is_the_requested_sealed_outcome_not_a_second_real_call(tmp_path):
    anchor = project(tmp_path, '''# flowguard: same LIMIT(x) calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    if x < 0: raise ValueError('negative input')
    return x <= 3
''', 'from policy import limit\ndef test_native(): assert limit(2) is True\n')
    scope, _ = bind_anchor(tmp_path, anchor)
    observed = calibration.execute(tmp_path, anchor, {'x': -1})
    assert observed.status == 'ok' and isinstance(observed.value, Raised), observed
    assert type(observed.value.error) is ValueError and str(observed.value.error) == 'negative input'
    assert scope.runtime.readings[-1].actual == ({'x': 2}, True)


def test_unavailable_actual_fields_do_not_become_a_successful_calibrated_reading(tmp_path):
    anchor = project(tmp_path, '''# flowguard: same LIMIT(x) calibrated_by=test_policy.py::test_native fields threshold=MISSING
def limit(x: int) -> bool:
    return x <= 3
''', 'from policy import limit\ndef test_native(): assert limit(2) is True\n')
    scope, _ = bind_anchor(tmp_path, anchor)
    observed = calibration.execute(tmp_path, anchor, {'x': 5})
    assert observed.status == 'grey' and observed.value is None, observed
    assert 'MISSING' in ' '.join(observed.reasons)
    reading = scope.runtime.readings[-1]
    assert reading.actual == ({'x': 2}, True) and reading.fields is None
    assert reading.rows == [] and reading.field_rows == []


def test_explicit_calibration_still_checks_actual_after_the_automatic_sample_limit(tmp_path):
    anchor = project(tmp_path, '''# flowguard: same LIMIT(x) calibrated_by=test_policy.py::test_native
def limit(x: int) -> bool:
    return x <= 3
''', 'from policy import limit\ndef test_native(): assert limit(2) is True\n')
    scope, _ = bind_anchor(tmp_path, anchor)
    module = importlib.import_module('policy')
    with scope.runtime.hook(module.limit, name='LIMIT'):
        for value in range(20):
            assert module.limit(value) is (value <= 3)
    assert scope.runtime.full(module.limit)
    before = len(scope.runtime.readings)
    observed = calibration.execute(tmp_path, anchor, {'x': 5})
    assert observed.status == 'ok' and observed.value is False, observed
    # The named test's call was recorded in its ordinary run, before the limit: no reading is added.
    assert len(scope.runtime.readings) == before
    assert scope.runtime.readings[0].actual == ({'x': 2}, True) and scope.runtime.readings[0].tests == {calibration._context(tmp_path, anchor.calibrated_by)[1].nodeid}
    assert scope.runtime.full(module.limit) and len(scope.runtime._seen[module.limit]) == 20

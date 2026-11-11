"""Source-only comparisons and observational hooks do not replay live calls."""
import importlib.util
import inspect
import json
import sys
from pathlib import Path

import pytest

from flowguard.intent import sites
from flowguard.intent.runtime import Runtime, sealed


def module(tmp_path, monkeypatch, source):
    path = tmp_path / 'sealed_candidate.py'
    path.write_text(source, encoding='utf-8')
    name = 'sealed_candidate_' + tmp_path.name.replace('-', '_')
    spec = importlib.util.spec_from_file_location(name, path)
    found = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, found)
    spec.loader.exec_module(found)
    return found


def test_sealed_uses_the_whole_def_defaults_helpers_and_fresh_constants():
    source = '''
LIMIT = 3
MARKS = []
raise RuntimeError('module initialization must never run')
def helper(n):
    return n <= LIMIT
def answer(n=3):
    return helper(n)
'''
    assert sealed(source, 'answer', [], {}) == {'status': 'ok', 'value': True}
    assert sealed(source, 'answer', [4], {}) == {'status': 'ok', 'value': False}
    assert sealed(source.replace('LIMIT = 3', 'LIMIT = 4'), 'answer', [4], {}) == {'status': 'ok', 'value': True}


def test_sealed_default_container_is_created_again_for_each_invocation():
    source = 'def answer(items=[]):\n    items += [1]\n    return len(items)\n'
    assert sealed(source, 'answer', [], {}) == {'status': 'ok', 'value': 1}
    assert sealed(source, 'answer', [], {}) == {'status': 'ok', 'value': 1}


@pytest.mark.parametrize('source', [
    'LIMIT = 1\ndef build_limit(): return 10\nLIMIT = build_limit()\ndef answer(x): return x + LIMIT\n',
    'LIMIT = 1\nif True:\n    LIMIT = 10\ndef answer(x): return x + LIMIT\n',
    'from math import floor as choose\nfrom builtins import abs as choose\ndef answer(x): return choose(x)\n',
    'from math import floor as choose\nif True:\n    from builtins import abs as choose\ndef answer(x): return choose(x)\n',
    'def helper(x): return x + 1\nhelper = factory()\ndef answer(x): return helper(x)\n',
    'def answer(x): return x + 1\nanswer = factory()\n',
    'DATA = {"n": 1}\nalias = DATA\nalias["n"] = 10\ndef answer(x): return x + DATA["n"]\n',
])
def test_unsupported_rebindings_cannot_recover_an_earlier_literal_import_or_function(source):
    answer = sealed(source, 'answer', [1], {})
    assert answer['status'] == 'unavailable'
    assert answer['reason'].startswith('uses unavailable binding ')


def test_a_later_supported_binding_can_replace_an_unsupported_one():
    source = 'LIMIT = build_limit()\nLIMIT = 10\ndef answer(x): return x + LIMIT\n'
    assert sealed(source, 'answer', [1], {}) == {'status': 'ok', 'value': 11}


@pytest.mark.parametrize('import_line, expression', [
    ('import math', 'math.floor(x)'), ('from math import floor as choose', 'choose(x)'),
])
def test_math_namespace_refuses_a_host_mock_without_consuming_its_calls(monkeypatch, import_line, expression):
    import math
    from unittest.mock import Mock
    replacement = Mock(return_value=999)
    monkeypatch.setattr(math, 'floor', replacement)
    assert math.floor(1.2) == 999
    source = import_line + '\ndef answer(x): return ' + expression + '\n'
    result = sealed(source, 'answer', [1.2], {})
    assert result['status'] == 'unavailable'
    assert replacement.call_count == 1
    assert replacement.call_args.args == (1.2,)


def test_native_math_members_still_compare_in_a_fresh_namespace():
    assert sealed('import math\ndef answer(x): return math.floor(x)\n', 'answer', [1.2], {}) == {
        'status': 'ok', 'value': 1,
    }


def test_unimported_standard_library_names_are_not_invented_globals():
    for name in ('math', 'Decimal', 'date', 'datetime', 'timedelta'):
        assert sealed(f'def answer(): return {name}\n', 'answer', [], {}) == {
            'status': 'unavailable', 'reason': 'uses ' + name,
        }
    assert sealed('def answer(x): return abs(x)\n', 'answer', [-2], {}) == {'status': 'ok', 'value': 2}


@pytest.mark.parametrize('source, qual', [
    ('@decorate\ndef answer(n): return n\n', 'answer'),
    ('async def answer(n): return n\n', 'answer'),
    ('def answer(n): yield n\n', 'answer'),
    ('class Owner:\n    def answer(n): return n\n', 'Owner.answer'),
    ('def answer(n=make_default()): return n\n', 'answer'),
])
def test_unavailable_source_shapes_are_not_executed(source, qual):
    assert sealed(source, qual, [2], {})['status'] == 'unavailable'


def test_missing_names_and_clock_reads_are_not_results(tmp_path):
    result = sealed('def answer(n): return send(n)\n', 'answer', [2], {})
    assert result == {'status': 'unavailable', 'reason': 'uses send'}
    result = sealed('from datetime import date\ndef answer(): return date.today().year\n', 'answer', [], {})
    assert result['status'] == 'unavailable'
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('name', ['send', 'SystemExit'])
def test_current_explicit_qualification_refuses_unknown_names_before_a_real_call(tmp_path, monkeypatch, name):
    found = module(tmp_path, monkeypatch, f'def answer(x): return {name}(x)\n')
    touched = []
    monkeypatch.setitem(vars(found), name, lambda value: touched.append(value) or True)
    runtime = Runtime(tmp_path, previous={})
    assert runtime.safety(found.answer, {'x': 2}) == 'uses ' + name
    assert sealed(Path(found.__file__).read_text(), 'answer', [2], {}) == {
        'status': 'unavailable', 'reason': 'uses ' + name,
    }
    assert touched == []


def test_only_explicit_current_execution_uses_the_active_bound_code(tmp_path, monkeypatch):
    found = module(tmp_path, monkeypatch, 'def answer(x): return x + 1\n')
    found.answer.__code__ = found.answer.__code__.replace(
        co_consts=tuple(2 if value == 1 else value for value in found.answer.__code__.co_consts))
    runtime = Runtime(tmp_path, previous={})
    bound = inspect.signature(found.answer).bind(2)
    assert runtime.safety(found.answer, bound.arguments) == ''
    assert runtime.guarded(found.answer, bound) == (3, '')
    assert runtime.guarded(found.answer, bound, current=True) == (4, '')


def test_sealed_exception_is_distinct_from_a_successful_result():
    result = sealed('def answer(n): raise ValueError("no result")\n', 'answer', [2], {})
    assert result == {'status': 'raised', 'error': {'type': 'ValueError', 'message': 'no result'}}


@pytest.mark.parametrize('name', ['BaseException', 'SystemExit', 'KeyboardInterrupt', 'GeneratorExit', 'BaseExceptionGroup'])
def test_process_control_exceptions_are_outside_the_closed_namespace(name):
    assert sealed(f'def answer(): raise {name}("stop")\n', 'answer', [], {}) == {
        'status': 'unavailable', 'reason': 'uses ' + name,
    }


def test_sealed_execution_does_not_become_an_ordinary_observation(tmp_path):
    runtime = Runtime(tmp_path, previous={})
    with runtime.record(predicate=lambda code: code.co_filename == '<flowguard-sealed>') as events:
        assert sealed('def answer(n): return n + 1\n', 'answer', [2], {}) == {'status': 'ok', 'value': 3}
    assert events == []


def test_hook_records_before_mutation_and_copies_the_real_json_result(tmp_path, monkeypatch):
    found = module(tmp_path, monkeypatch, 'CALLS=[]\ndef answer(items):\n    CALLS.append(1)\n    items += [1]\n    return items\n')
    runtime = Runtime(tmp_path, previous={})
    values, records = [], []
    with runtime.hook(found.answer, recorded=records.append):
        returned = found.answer(values)
    returned.append(2)
    assert values == [1, 2] and found.CALLS == [1]
    [reading] = records
    assert reading.sample == {'args': [[]], 'kwargs': {}, 'inputs': {'items': []}}
    assert reading.json_result == [1]
    assert reading.actual[1] is returned
    assert reading.index == 0


def test_opaque_argument_is_not_inspected_or_lost_from_the_real_reading(tmp_path, monkeypatch):
    found = module(tmp_path, monkeypatch, 'def answer(value): return True\n')
    touched = []
    class Opaque:
        def __repr__(self):
            touched.append('repr')
            raise AssertionError('metadata must not run this')
        def __iter__(self):
            touched.append('iter')
            raise AssertionError('metadata must not run this')
        def __eq__(self, other):
            touched.append('eq')
            raise AssertionError('metadata must not run this')
    value = Opaque()
    runtime = Runtime(tmp_path, previous={})
    with runtime.hook(found.answer):
        assert found.answer(value) is True
    reading = runtime.readings[0]
    assert reading.sample is None
    assert reading.actual_inputs['value'] is value
    assert reading.actual[0]['value'] is value
    assert reading.actual[1] is True and touched == []


def test_twenty_unique_samples_remove_the_hook_and_later_scopes_do_not_reinstall_it(tmp_path, monkeypatch):
    found = module(tmp_path, monkeypatch, 'def answer(n): return n+1\n')
    original_code = found.answer.__code__
    runtime = Runtime(tmp_path, previous={})
    with runtime.hook(found.answer):
        assert found.answer.__code__ is not original_code
        for n in range(20):
            assert found.answer(n) == n + 1
        assert found.answer.__code__ is original_code
        assert not any(name.startswith('__flowguard_calibration_') for name in vars(found))
        assert found.answer(99) == 100
    assert len(runtime.readings) == 20
    with runtime.hook(found.answer):
        assert found.answer.__code__ is original_code
        assert found.answer(100) == 101
    assert len(runtime.readings) == 20


def test_sampling_budget_counts_unique_inputs_instead_of_different_results(tmp_path, monkeypatch):
    found = module(tmp_path, monkeypatch, 'COUNT=0\ndef answer(n):\n    global COUNT\n    COUNT += 1\n    return COUNT\n')
    runtime = Runtime(tmp_path, previous={})
    original_code = found.answer.__code__
    with runtime.hook(found.answer):
        for index in range(25):
            runtime.test = 'test_' + str(index)
            assert found.answer(7) == index + 1
        assert not runtime.full(found.answer)
        assert found.answer.__code__ is not original_code
        for n in range(19):
            if n != 7:
                found.answer(n)
        assert not runtime.full(found.answer)
        found.answer(19)
        assert runtime.full(found.answer)
        assert found.answer.__code__ is original_code
    assert len(runtime.readings) == 44
    assert len(runtime._seen[found.answer]) == 20
    assert [reading.actual[1] for reading in runtime.readings[:25]] == list(range(1, 26))


def test_nested_real_calls_have_their_own_reading_indices(tmp_path, monkeypatch):
    found = module(tmp_path, monkeypatch, 'def answer(n):\n    return n if n == 0 else answer(n-1)+1\n')
    runtime = Runtime(tmp_path, previous={})
    captured = []
    with runtime.hook(found.answer, recorded=lambda reading: captured.append((reading.index, reading.sample['inputs']['n']))):
        assert found.answer(3) == 3
    assert captured == [(3, 0), (2, 1), (1, 2), (0, 3)]
    assert [runtime.readings[index].sample['inputs']['n'] for index, _ in captured] == [0, 1, 2, 3]


def test_recording_propagates_the_original_exception_object(tmp_path, monkeypatch):
    found = module(tmp_path, monkeypatch, 'ERROR=ValueError("native")\ndef answer(n): raise ERROR\n')
    runtime = Runtime(tmp_path, previous={})
    records = []
    with runtime.hook(found.answer, recorded=records.append):
        with pytest.raises(ValueError) as caught:
            found.answer(2)
    assert caught.value is found.ERROR
    assert records[0].sample == {'args': [2], 'kwargs': {}, 'inputs': {'n': 2}}
    assert records[0].actual[1].error is found.ERROR


def test_hook_metadata_does_not_consume_the_programs_mocked_clock(tmp_path, monkeypatch):
    import time
    found = module(tmp_path, monkeypatch, 'import time\ndef answer(): return time.perf_counter() + time.perf_counter()\n')
    runtime = Runtime(tmp_path, previous={})
    values = iter((2.0, 3.0))
    with runtime.hook(found.answer):
        with monkeypatch.context() as patch:
            patch.setattr(time, 'perf_counter', lambda: next(values))
            assert found.answer() == 5.0
    assert runtime.seconds >= 0
    assert runtime.readings[0].json_result == 5.0

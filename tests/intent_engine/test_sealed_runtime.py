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
            assert found.answer(7) == index + 1       # every real call runs and returns its own result
        assert not runtime.full(found.answer)
        assert found.answer.__code__ is not original_code
        for n in range(19):
            if n != 7:
                found.answer(n)
        assert not runtime.full(found.answer)
        found.answer(19)
        assert runtime.full(found.answer)
        assert found.answer.__code__ is original_code
    # One reading per distinct encoded input: the first call of input 7 is the one recorded.
    assert len(runtime.readings) == 20
    assert len(runtime._seen[found.answer]) == 20
    assert runtime.readings[0].actual[1] == 1
    assert runtime.readings[0].tests == {'test_' + str(index) for index in range(25)}


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


def test_repeated_identical_inputs_build_one_reading_per_distinct_input(tmp_path, monkeypatch):
    # The hot case: a function called many times with a few inputs. A repeated encoded input is looked up,
    # not recorded again (design 4.5); the tests that made each call are kept on its one reading.
    found = module(tmp_path, monkeypatch, 'def fee(days): return days * 3\n')
    runtime = Runtime(tmp_path, previous={})
    with runtime.hook(found.fee):
        total = 0
        for index in range(3000):
            runtime.test = 'test_' + str(index % 2)
            total += found.fee(index % 3)
    assert total == 3 * sum(index % 3 for index in range(3000))
    assert [reading.sample['inputs'] for reading in runtime.readings] == [{'days': 0}, {'days': 1}, {'days': 2}]
    assert [reading.tests for reading in runtime.readings] == [{'test_0', 'test_1'}] * 3
    assert not runtime.full(found.fee)


def _project_settings(tmp_path, settings, policy):
    (tmp_path / 'shop').mkdir()
    (tmp_path / 'shop/__init__.py').write_text('')
    (tmp_path / 'shop/settings.py').write_text(settings)
    (tmp_path / 'shop/policy.py').write_text(policy)
    runtime = Runtime(tmp_path, previous={})
    return runtime, policy, runtime.imports('shop/policy.py', 'shop.policy')


@pytest.mark.parametrize('policy, value', [
    ('from shop.settings import GRACE_DAYS\ndef allows(days): return days <= GRACE_DAYS\n', True),
    ('from shop.settings import GRACE_DAYS as G\ndef allows(days): return days <= G\n', True),
    ('from .settings import GRACE_DAYS\ndef allows(days): return days <= GRACE_DAYS\n', True),
    ('from shop.settings import LIMITS\ndef allows(days): return days <= LIMITS["grace"]\n', False),
    ('import shop.settings\ndef allows(days): return days <= shop.settings.GRACE_DAYS\n', True),
    ('import shop.settings as config\ndef allows(days): return days <= config.GRACE_DAYS\n', True),
    ('from shop import settings\ndef allows(days): return days <= settings.GRACE_DAYS\n', True),
])
def test_a_literal_constant_of_a_project_module_is_read_from_its_source(tmp_path, policy, value):
    runtime, source, imports = _project_settings(tmp_path, 'GRACE_DAYS = 3\nLIMITS = {"grace": 2}\n', policy)
    assert sealed(source, 'allows', [3], {}, imports) == {'status': 'ok', 'value': value}
    # Without the project resolver the name stays unavailable, as before.
    assert sealed(source, 'allows', [3], {})['status'] == 'unavailable'
    assert 'shop.settings' not in sys.modules       # nothing was imported


@pytest.mark.parametrize('settings, policy, reason', [
    ('GRACE_DAYS = compute()\n', 'from shop.settings import GRACE_DAYS\ndef allows(days): return days <= GRACE_DAYS\n',
     'uses unavailable binding GRACE_DAYS'),
    ('GRACE_DAYS = 3\nif FLAG:\n    GRACE_DAYS = 9\n', 'from shop.settings import GRACE_DAYS\ndef allows(days): return days <= GRACE_DAYS\n',
     'uses unavailable binding GRACE_DAYS'),
    ('def GRACE_DAYS(): return 3\n', 'from shop.settings import GRACE_DAYS\ndef allows(days): return days <= GRACE_DAYS()\n',
     'uses unavailable binding GRACE_DAYS'),
    ('from os import sep as GRACE_DAYS\n', 'from shop.settings import GRACE_DAYS\ndef allows(days): return days <= GRACE_DAYS\n',
     'uses unavailable binding GRACE_DAYS'),
    ('GRACE_DAYS = 3\n', 'from shop.missing import GRACE_DAYS\ndef allows(days): return days <= GRACE_DAYS\n',
     'uses unavailable binding GRACE_DAYS'),
    ('_GRACE = 3\n', 'from shop.settings import _GRACE\ndef allows(days): return days <= _GRACE\n',
     'uses unavailable binding _GRACE'),
    ('GRACE_DAYS = 3\n', 'import shop.settings as config\ndef allows(days): return days <= config.OTHER\n',
     'uses unavailable attribute OTHER'),
])
def test_anything_but_a_literal_project_constant_stays_not_compared(tmp_path, settings, policy, reason):
    runtime, source, imports = _project_settings(tmp_path, settings, policy)
    assert sealed(source, 'allows', [3], {}, imports) == {'status': 'unavailable', 'reason': reason}


def test_an_installed_module_of_the_same_name_is_never_read(tmp_path, monkeypatch):
    # `pathlib` is an interpreter module: the resolver finds only project files under the importer's root.
    runtime, source, imports = _project_settings(tmp_path, 'X = 1\n', 'from pathlib import sep\ndef allows(days): return sep\n')
    assert imports('pathlib', 0) is None and imports('shop.settings', 0)[2] == 'shop/settings.py'
    assert sealed(source, 'allows', [3], {}, imports) == {'status': 'unavailable', 'reason': 'uses unavailable binding sep'}


def test_the_baseline_version_reads_the_baseline_constant(tmp_path):
    (tmp_path / 'shop').mkdir()
    (tmp_path / 'shop/__init__.py').write_text('')
    (tmp_path / 'shop/settings.py').write_text('GRACE_DAYS = 7\n')
    policy = 'from shop.settings import GRACE_DAYS\ndef allows(days): return days <= GRACE_DAYS\n'
    (tmp_path / 'shop/policy.py').write_text(policy)
    runtime = Runtime(tmp_path, previous={'shop/settings.py': 'GRACE_DAYS = 3\n', 'shop/policy.py': policy})
    assert sealed(policy, 'allows', [5], {}, runtime.imports('shop/policy.py', 'shop.policy', old=True)) == {'status': 'ok', 'value': False}
    assert sealed(policy, 'allows', [5], {}, runtime.imports('shop/policy.py', 'shop.policy')) == {'status': 'ok', 'value': True}


def test_open_is_refused_before_the_call_starts(tmp_path, monkeypatch):
    from flowguard.intent import runtime as R
    target = tmp_path / 'written.txt'
    calls = []
    real = R._value
    monkeypatch.setattr(R, '_value', lambda fn, bound: calls.append(fn) or real(fn, bound))
    source = 'def answer(path):\n    open(path, "w")\n    return True\n'
    assert sealed(source, 'answer', [str(target)], {}) == {'status': 'unavailable', 'reason': 'uses open'}
    found = module(tmp_path, monkeypatch, source)
    assert Runtime(tmp_path, previous={}).safety(found.answer, {'path': str(target)}) == 'uses open'
    assert calls == [] and not target.exists()


@pytest.mark.parametrize('body, event', [
    ('open(path, "w").write("x")', 'uses open'),
    ('__import__("subprocess").run(["true"])', 'uses subprocess.Popen'),
    ('__import__("os").listdir(".")', 'uses os.listdir'),
])
def test_the_audit_hook_refuses_io_inside_the_bounded_call(tmp_path, monkeypatch, body, event):
    # The bounded call (`_value`) runs a sealed def or an explicit current function; a project helper the
    # static check cannot see still meets the audit hook, which refuses the operation before it happens.
    import subprocess
    subprocess.run(['true'], check=True)    # the modules the bodies reach are already imported
    target = tmp_path / 'written.txt'
    found = module(tmp_path, monkeypatch, f'def answer(path):\n    {body}\n    return True\n')
    runtime = Runtime(tmp_path, previous={})
    bound = inspect.signature(found.answer).bind(str(target))
    assert runtime.guarded(found.answer, bound, current=True) == (None, event)
    assert not target.exists()


def test_a_decorated_function_is_not_compared_even_with_a_same_file_decorator():
    source = 'def tag(f):\n    return abs\n@tag\ndef answer(n):\n    return n\n'
    assert sealed(source, 'answer', [-2], {}) == {'status': 'unavailable', 'reason': 'decorator, async or type parameters'}


def test_a_generator_is_not_compared_even_when_a_helper_consumes_it():
    source = 'def numbers(n):\n    yield n\n    yield n + 1\ndef answer(n):\n    return sum(numbers(n))\n'
    assert sealed(source, 'answer', [2], {}) == {'status': 'unavailable', 'reason': 'unsupported Yield'}


@pytest.mark.parametrize('source', [
    'LIMIT = 3\ndef answer(n=LIMIT):\n    return n\n',
    'def make():\n    return [1]\ndef answer(n=make()):\n    return n\n',
])
def test_a_non_literal_default_is_not_compared_even_when_it_could_be_evaluated(source):
    assert sealed(source, 'answer', [], {}) == {'status': 'unavailable', 'reason': 'non-literal default'}


def test_the_clock_raises_inside_the_sealed_environment():
    from flowguard.intent.runtime import Refused, _closed
    for expression, attribute in (('datetime.now()', 'now'), ('datetime.utcnow()', 'utcnow'),
                                  ('datetime.today()', 'today'), ('date.today()', 'today')):
        source = f'from datetime import date, datetime\ndef answer():\n    return {expression}\n'
        assert sealed(source, 'answer', [], {}) == {'status': 'unavailable', 'reason': 'uses attribute ' + attribute}
    assert sealed('import time\ndef answer():\n    return time.time()\n', 'answer', [], {}) == {
        'status': 'unavailable', 'reason': 'uses attribute time'}
    assert sealed('from time import time\ndef answer():\n    return time()\n', 'answer', [], {}) == {
        'status': 'unavailable', 'reason': 'uses unavailable binding time'}
    # Behind the attribute check, the sealed datetime classes themselves refuse to read the clock.
    namespace = _closed('from datetime import date, datetime\ndef answer():\n    return 1\n', 'answer').__globals__
    for read in (namespace['datetime'].now, namespace['datetime'].utcnow, namespace['datetime'].today, namespace['date'].today):
        with pytest.raises(Refused, match='uses current time'):
            read()
    assert namespace['date'](2026, 1, 2).isoformat() == '2026-01-02'

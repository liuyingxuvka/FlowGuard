"""Real anchor readings retain the guarantees of the retired diagnostic runner.

These models belong to a small ordinary program. No built-in SDK pipeline,
JSONL writer, child process or private pytest session supplies their evidence.
"""
import ast
from dataclasses import replace
import importlib.util
import io
from contextlib import redirect_stdout
import sys
import uuid

import pytest

from flowguard.intent.anchors import Index, collect_sources
from flowguard.intent.api import Rule
from flowguard.intent.flow import Capture, Flow, Node, Read, Relation, finite_check, runtime_check
from flowguard.intent.runtime import Runtime, _HUB, _PRIVATE
from flowguard.intent.sites import _recompile, installed


SOURCE = '''# flowguard: event RUN
def run(errors: int, policy_red: bool, test_code: int, run_batch: bool = True):
    loaded = load(errors)
    if run_batch:
        batch = run_tests(test_code)
    red = validate(policy_red)
    return 1 if loaded['errors'] or red or (run_batch and batch['returncode']) else 0
# flowguard: event LOAD
def load(errors: int): return {'errors': errors}
# flowguard: event BATCH
def run_tests(test_code: int): return {'returncode': test_code}
# flowguard: event VALIDATE
def validate(red: bool): return red
'''


def program(root, source=SOURCE):
    name = 'recorded_program_' + uuid.uuid4().hex
    path = root / (name + '.py')
    path.write_text(source)
    index = collect_sources(root, [(path.name, name)])
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return index, module


def pipeline():
    # Expectations are independent of the implementation in SOURCE.
    contracts = (
        Rule('LOAD_EXIT', 'bad_input_prevents_success', 'lesson: load errors prevent success',
             {'errors': int, 'exit_code': int}, lambda errors, exit_code: errors == 0 or exit_code != 0),
        Rule('VALIDATE_EXIT', 'invalid_policy_prevents_success', 'lesson: invalid policy prevents success',
             {'red': bool, 'exit_code': int}, lambda red, exit_code: not red or exit_code != 0),
        Rule('BATCH_EXIT', 'failed_batch_prevents_success', 'lesson: a failed batch prevents success',
             {'test_code': int, 'exit_code': int}, lambda test_code, exit_code: test_code == 0 or exit_code != 0),
    )
    return Flow('PIPELINE', 'lesson: actual stage results determine the public result',
                (Node('begin', 'RUN'), Node('loaded', 'LOAD', phase='return'),
                 Node('batch_start', 'BATCH'), Node('batch_end', 'BATCH', phase='return'),
                 Node('validation_start', 'VALIDATE'), Node('validated', 'VALIDATE', phase='return'),
                 Node('returned', 'RUN', phase='return', end=True),
                 Node('aborted', 'RUN', phase='raise', end=True)),
                (('begin', 'loaded'), ('begin', 'aborted'),
                 ('loaded', 'batch_start'), ('loaded', 'validation_start'), ('loaded', 'aborted'),
                 ('batch_start', 'batch_end'), ('batch_start', 'aborted'),
                 ('batch_end', 'batch_start'), ('batch_end', 'validation_start'), ('batch_end', 'aborted'),
                 ('validation_start', 'validated'), ('validation_start', 'aborted'),
                 ('validated', 'returned'), ('validated', 'aborted')),
                relations=(
                    Relation(contracts[0], {'errors': Read('loaded', 'result.errors'),
                                            'exit_code': Read('returned')}, on='returned'),
                    Relation(contracts[1], {'red': Read('validated'), 'exit_code': Read('returned')}, on='returned'),
                    Relation(contracts[2], {'test_code': Read('batch_end', 'result.returncode'),
                                            'exit_code': Read('returned')}, on='returned')))


def observed(root, values=(0, False, 0, True)):
    index, module = program(root)
    with Capture(root, index, 'real') as capture:
        actual = module.run(*values)
    assert not capture.issues
    return index, module, capture.events, actual


def test_real_stage_results_and_structural_exhaustion_remain_separate(tmp_path):
    index, _, events, actual = observed(tmp_path)
    assert actual == 0
    result = runtime_check(pipeline(), events, index)
    assert not result['red'] and result['checked_relations'] == 3
    assert result['verdict'] == 'grey' and any('unobserved edge' in reason for reason in result['grey'])
    finite = finite_check(pipeline(), index)
    assert finite['exhausted'] and finite['verdict'] == 'ok'
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    for event in events:
        anchor = next(entry for entry in index.named(event.anchor) if entry.target == event.site)
        assert event.file == str(tmp_path / anchor.file)
        assert event.source_digest == anchor.source_digest and event.case == 'real'


@pytest.mark.parametrize('values,rule_id', [((1, False, 0, True), 'LOAD_EXIT'),
                                         ((0, True, 0, True), 'VALIDATE_EXIT'),
                                         ((0, False, 1, True), 'BATCH_EXIT')])
def test_only_corrupting_the_actual_public_return_to_zero_is_red(tmp_path, values, rule_id):
    index, _, events, actual = observed(tmp_path, values)
    assert actual == 1 and not runtime_check(pipeline(), events, index)['red']
    corrupted = [replace(event, result=0) if event.anchor == 'RUN' and event.phase == 'return' else event
                 for event in events]
    result = runtime_check(pipeline(), corrupted, index)
    assert any(rule_id in reason for reason in result['red'])


@pytest.mark.parametrize('anchor,value', [('LOAD', {'errors': 'one'}), ('VALIDATE', 'red'),
                                        ('BATCH', {'returncode': 'one'}), ('RUN', 'zero')])
def test_wrong_actual_reading_types_remain_red(tmp_path, anchor, value):
    index, _, events, _ = observed(tmp_path)
    corrupted = [replace(event, result=value) if event.anchor == anchor and event.phase == 'return' else event
                 for event in events]
    assert any('actual type' in reason for reason in runtime_check(pipeline(), corrupted, index)['red'])


def test_a_missing_fixed_reading_is_grey_instead_of_invented_success(tmp_path):
    index, _, events, _ = observed(tmp_path)
    changed = [replace(event, result={}) if event.anchor == 'LOAD' and event.phase == 'return' else event
               for event in events]
    result = runtime_check(pipeline(), changed, index)
    assert not result['red'] and any('fixed reading field missing' in reason for reason in result['grey'])
    assert result['checked_relations'] == 2


def test_an_unrun_batch_cannot_supply_a_successful_reading(tmp_path):
    index, _, events, actual = observed(tmp_path, (0, False, 0, False))
    assert actual == 0 and not any(event.anchor == 'BATCH' for event in events)
    result = runtime_check(pipeline(), events, index)
    assert not result['red'] and result['checked_relations'] == 2
    assert any('batch_end: reading has 0 occurrences' in reason for reason in result['grey'])


def test_multiple_actual_readings_are_not_silently_first_or_last(tmp_path):
    index, _, events, actual = observed(tmp_path, (0, False, 1, True))
    assert actual == 1
    start = next(n for n, event in enumerate(events) if event.anchor == 'BATCH')
    stop = next(n for n, event in enumerate(events) if event.anchor == 'VALIDATE')
    second = [replace(event, occurrence=event.occurrence + 1) for event in events[start:stop]]
    changed = [*events[:stop], *second, *events[stop:]]
    changed = [replace(event, sequence=n, result=0) if event.anchor == 'RUN' and event.phase == 'return'
               else replace(event, sequence=n) for n, event in enumerate(changed, 1)]
    result = runtime_check(pipeline(), changed, index)
    assert not result['red'] and result['checked_relations'] == 2
    assert any('batch_end: reading has 2 occurrences' in reason for reason in result['grey'])


def test_deleting_or_reordering_real_observations_is_red(tmp_path):
    index, _, events, _ = observed(tmp_path)
    missing = [event for event in events if event.anchor != 'LOAD']
    missing = [replace(event, sequence=n) for n, event in enumerate(missing, 1)]
    assert runtime_check(pipeline(), missing, index)['red']
    moved = events[:]
    a = next(n for n, event in enumerate(moved) if event.anchor == 'LOAD' and event.phase == 'return')
    b = next(n for n, event in enumerate(moved) if event.anchor == 'BATCH' and event.phase == 'call')
    moved[a], moved[b] = moved[b], moved[a]
    moved = [replace(event, sequence=n) for n, event in enumerate(moved, 1)]
    assert runtime_check(pipeline(), moved, index)['red']


@pytest.mark.parametrize('failure', [ValueError('real failure'), KeyboardInterrupt()])
def test_actual_raise_or_interrupt_never_supplies_a_successful_return(tmp_path, failure):
    index, module = program(tmp_path, '# flowguard: event FAIL\ndef fail(error):\n    raise error\n')
    with pytest.raises(type(failure)) as caught:
        with Capture(tmp_path, index, 'aborted') as capture:
            module.fail(failure)
    assert caught.value is failure
    assert [(event.anchor, event.phase) for event in capture.events] == [('FAIL', 'call'), ('FAIL', 'raise')]
    assert capture.events[-1].error is failure


def test_a_replaced_function_cannot_claim_the_unchanged_source_reading(tmp_path):
    index, module = program(tmp_path, '# flowguard: event VALUE\ndef value(): return 3\n')
    original = module.value
    def change_body(function):
        function.body = [ast.Return(ast.Constant(37))]
    code = _recompile(original, ast.NodeTransformer(), lambda: True, change_body)
    assert (code.co_filename, code.co_firstlineno, code.co_qualname) == (
        original.__code__.co_filename, original.__code__.co_firstlineno, original.__code__.co_qualname)
    with installed(original, code):
        with Capture(tmp_path, index, 'replaced') as capture:
            assert module.value() == 37
    model = Flow('VALUE', 'lesson: one actual value',
                 (Node('start', 'VALUE'), Node('end', 'VALUE', phase='return')),
                 (('start', 'end'),))
    result = runtime_check(model, capture.events, index)
    assert result['verdict'] != 'ok' or capture.issues
    assert capture.issues or any('source' in reason or 'installed' in reason for reason in result['grey'])


def test_namesake_or_wrong_digest_cannot_borrow_a_real_source_identity(tmp_path):
    index, _, events, _ = observed(tmp_path)
    anchor = index.named('LOAD')[0]
    for changed in (replace(anchor, file='other.py', qual='other'), replace(anchor, source_digest='0' * 64)):
        bad = Index(tuple(changed if entry is anchor else entry for entry in index.entries))
        result = runtime_check(pipeline(), events, bad)
        assert result['verdict'] != 'ok'
        assert any('source identity' in reason for reason in result['grey'])
    duplicate = Index((*index.entries, anchor))
    with Capture(tmp_path, duplicate, 'ambiguous') as capture:
        # Source identity must be unique; an exact duplicate is not proof.
        for name in ('load',):
            assert getattr(sys.modules[anchor.module], name)(0) == {'errors': 0}
    assert capture.events == [] and capture.issues


def test_live_callback_sees_entry_before_the_real_function_body_finishes(tmp_path):
    source = '''# flowguard: event SAVE
def save(seen):
    assert seen == [('SAVE', 'call')]
    return 3
'''
    index, module = program(tmp_path, source)
    seen = []
    with Capture(tmp_path, index, 'live', on_event=lambda event: seen.append((event.anchor, event.phase))) as capture:
        assert module.save(seen) == 3
    assert seen == [('SAVE', 'call'), ('SAVE', 'return')]
    assert len(capture.events) == 2


def test_a_broken_optional_callback_does_not_replace_real_model_red(tmp_path):
    index, module = program(tmp_path)
    def broken(event):
        raise OSError('optional observer unavailable')
    with Capture(tmp_path, index, 'bad', on_event=broken) as capture:
        assert module.run(0, False, 0) == 0
    assert len(capture.events) == 8
    changed = [event for event in capture.events if event.anchor != 'LOAD']
    changed = [replace(event, sequence=n) for n, event in enumerate(changed, 1)]
    assert runtime_check(pipeline(), changed, index)['red']
    assert len(capture.diagnostic_issues) == 1 and 'OSError' in capture.diagnostic_issues[0]
    assert not capture.issues


def test_observer_keyboard_interrupt_is_not_swallowed_and_owner_is_released(tmp_path):
    index, module = program(tmp_path, '# flowguard: event VALUE\ndef value(): return 3\n')
    before = tuple(_HUB.records)
    def interrupted(event):
        raise KeyboardInterrupt('observer interrupted')
    with pytest.raises(KeyboardInterrupt, match='observer interrupted'):
        with Capture(tmp_path, index, 'interrupted', on_event=interrupted):
            module.value()
    assert tuple(_HUB.records) == before
    with Capture(tmp_path, index, 'after') as capture:
        assert module.value() == 3
    assert [(event.phase, event.result) for event in capture.events] == [('call', None), ('return', 3)]


def test_nested_recorders_keep_the_outer_owner_live_and_do_not_mix_cases(tmp_path):
    index, module = program(tmp_path, '# flowguard: event VALUE\ndef value(x: int): return x\n')
    before = tuple(_HUB.records)
    with Capture(tmp_path, index, 'outer') as outer:
        owner = tuple(_HUB.records)
        assert module.value(1) == 1
        with Capture(tmp_path, index, 'inner') as inner:
            assert module.value(2) == 2
        assert tuple(_HUB.records) == owner
        assert module.value(3) == 3
    assert tuple(_HUB.records) == before
    assert [event.result for event in outer.events if event.phase == 'return'] == [1, 2, 3]
    assert [event.result for event in inner.events if event.phase == 'return'] == [2]
    assert all(event.case == 'outer' for event in outer.events)
    assert all(event.case == 'inner' for event in inner.events)


def test_recording_a_call_creates_only_its_one_ordinary_anchor_event_pair(tmp_path):
    source = '# flowguard: sensor VALUE\ndef value(x: int) -> bool: return x <= 3\n'
    index, module = program(tmp_path, source)
    runtime = Runtime(tmp_path, previous={})
    with Capture(tmp_path, index, 'ordinary', _ordinary=True) as capture:
        with runtime.hook(module.value):
            assert module.value(2) is True
    assert [(event.phase, event.values['x']) for event in capture.events] == [('call', 2), ('return', 2)]
    reading, = runtime.readings
    assert reading.sample['inputs'] == {'x': 2} and reading.json_result is True and reading.rows == []
    assert not _PRIVATE.get() and not capture.issues


def test_recording_does_not_copy_an_opaque_context_or_its_large_ledger(tmp_path):
    index, module = program(tmp_path, '# flowguard: event VALUE\ndef value(context): return True\n')
    class Opaque:
        def __repr__(self):
            raise AssertionError('an observer must not invoke context repr')
    context = {'opaque': Opaque(), 'ledger': 'PRIVATE_LEDGER_' * 100_000}
    runtime = Runtime(tmp_path, previous={})
    with runtime.record({module.value.__code__: 'VALUE'}):
        assert module.value(context) is True
        assert module.value(context['opaque']) is True
    assert len(repr(runtime.events)) < 1000
    assert 'PRIVATE_LEDGER_' not in repr(runtime.events)
    assert runtime.events[0]['values'] == {'context': '<dict>'}
    assert runtime.events[2]['values'] == {'context': '<Opaque>'}
    assert runtime.events[-1]['value'] is True


def test_actual_declared_state_is_read_at_entry_and_completion(tmp_path):
    source = '''class Job:
    # flowguard: states Job.status = new | saved
    status = 'new'
    # flowguard: event SAVE
    def save(self, value: int):
        self.status = 'saved'
        return value
'''
    index, module = program(tmp_path, source)
    with Capture(tmp_path, index, 'state') as capture:
        assert module.Job().save(3) == 3
    assert capture.events[-1].before_states == {'Job.status': 'new'}
    assert capture.events[-1].states == {'Job.status': 'saved'}
    assert capture.events[-1].result == 3


def test_same_source_recursive_calls_keep_their_real_occurrence_pairing(tmp_path):
    source = '''# flowguard: event RUN
def run(depth: int):
    if depth:
        return run(depth - 1)
    return 0
'''
    index, module = program(tmp_path, source)
    with Capture(tmp_path, index, 'recursive') as capture:
        assert module.run(2) == 0
    assert [(event.phase, event.occurrence) for event in capture.events] == [
        ('call', 1), ('call', 2), ('call', 3), ('return', 3), ('return', 2), ('return', 1)]
    assert capture.events[-1].result == 0
    model = Flow('ONE', 'lesson: one run must return without nested runs',
                 (Node('begin', 'RUN'), Node('end', 'RUN', phase='return')), (('begin', 'end'),))
    assert runtime_check(model, capture.events, index)['red']


def test_a_real_project_rule_named_check_pipeline_is_an_ordinary_rule(tmp_path):
    from flowguard.intent import cli
    from tests.intent_engine.test_cli import project
    _, cfg = project(tmp_path)
    policy = cfg.intent / 'policy.py'
    policy.write_text(policy.read_text().replace("@rule('LIMIT',", "@rule('CHECK_PIPELINE',"))
    output = io.StringIO()
    with redirect_stdout(output):
        assert cli.show(cfg, 'CHECK_PIPELINE') == 0
    text = output.getvalue()
    assert 'RULE CHECK_PIPELINE: acceptance' in text
    assert 'built-in' not in text and 'check-flow.jsonl' not in text

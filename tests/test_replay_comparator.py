"""Keep the shared replay comparator independently checked after the old engine retires."""
from dataclasses import replace
import json
import pytest

from flowguard.conformance import replay_trace, select_covering_traces
from flowguard.replay import ReplayInput, ReplayObservation
from flowguard.trace import Trace, TraceStep


def expected():
    return Trace(initial_state=(), steps=(
        TraceStep('A', 'record', 'A', 1, (), ('A',), 'ok'),
        TraceStep('A', 'record', 'A', 1, ('A',), ('A',), 'ok'),
    ))


class Records:
    def __init__(self, *, duplicate=False):
        self.duplicate = duplicate
        self.inputs = []

    def reset(self, initial):
        self.items = list(initial)

    def apply_step(self, request):
        assert isinstance(request, ReplayInput)
        assert set(vars(request)) == {'external_input', 'function_name', 'function_input'}
        self.inputs.append(request)
        if self.duplicate or request.function_input not in self.items:
            self.items.append(request.function_input)
        return ReplayObservation('record', len(self.items), tuple(self.items), 'ok')


def test_correct_and_duplicate_implementations_share_the_independent_expected_trace():
    trace = expected()
    good = Records()
    assert replay_trace(trace, good).ok and len(good.inputs) == 2
    bad = replay_trace(trace, Records(duplicate=True))
    assert not bad.ok and bad.failed_step_index == 2
    assert len(bad.replayed_steps) == 2 and bad.expected_trace == trace
    assert bad.violations[0].rule_name == 'projected_state_matches'
    assert bad.violations[0].observed_step.observed_state == ('A', 'A')
    assert 'counterexample:' in bad.format_text()
    assert json.loads(bad.to_json_text())['failed_step_index'] == 2


@pytest.mark.parametrize('change,rule', [
    ({'new_state': ('forged',)}, 'projected_state_matches'),
    ({'function_output': 9}, 'projected_output_matches'),
    ({'label': 'forged'}, 'label_matches'),
])
def test_corrupt_expectation_is_not_given_to_the_adapter(change, rule):
    trace = expected()
    changed = replace(trace, steps=(replace(trace.steps[0], **change), *trace.steps[1:]))
    adapter = Records()
    report = replay_trace(changed, adapter)
    assert not report.ok and report.failed_step_index == 1
    assert report.violations[0].rule_name == rule
    assert adapter.items == ['A'] and len(adapter.inputs) == 1


@pytest.mark.parametrize('phase,index,rule', [('reset', 0, 'adapter_reset'), ('apply_step', 1, 'adapter_exception')])
def test_adapter_faults_remain_failed_reports_with_the_original_exception(phase, index, rule):
    adapter = Records()
    error = RuntimeError('actual adapter failed')
    def fail(*args):
        raise error
    setattr(adapter, phase, fail)
    report = replay_trace(expected(), adapter)
    assert not report.ok and report.failed_step_index == index
    assert report.violations[0].exception is error and report.violations[0].rule_name == rule


def test_covering_traces_preserve_the_duplicate_prefix_and_empty_input():
    full = expected()
    prefix = replace(full, steps=full.steps[:1])
    assert select_covering_traces([prefix, full]) == (full,)
    assert select_covering_traces([]) == ()
    assert select_covering_traces([full], limit=0) == ()

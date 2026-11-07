"""Result relations consume real consumer events, then test a false zero exit."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import queue
import threading

import pytest

from flowguard.intent import cli
from flowguard.intent.checkflow import CHECK_FLOW, CheckObservation
from flowguard.intent.config import load_config
from flowguard.intent.flow import runtime_check


@pytest.fixture(scope='module')
def actual_consumers(tmp_path_factory):
    observed = {}
    for case in ('good', 'source_error', 'load_error', 'pytest_error', 'no_pytest'):
        root = tmp_path_factory.mktemp('check-results-'+case)
        (root/'tests').mkdir()
        (root/'pyproject.toml').write_text('[tool.pytest.ini_options]\ntestpaths=["tests"]\n')
        (root/'tests/test_result.py').write_text(
            'def test_result():\n    assert ' + ('False' if case == 'pytest_error' else 'True') + '\n')
        (root/'tests/test_flowguard_intent.py').write_text(cli.SENTINEL)
        if case == 'source_error':
            (root/'app.py').write_text('# flowguard: event BROKEN(value: int)\ndef app():\n    return True\n')
        if case == 'load_error':
            (root/'tests/intent').mkdir()
            (root/'tests/intent/broken.py').write_text('raise ValueError("REAL_LOAD_ERROR")\n')
        cfg = load_config(root)
        with CheckObservation(cfg) as observation:
            status = observation.call(cli._checked, cfg, everything=case != 'no_pytest')
        observed[case] = dict(cfg=cfg, status=status, observation=observation)
        print(f'CONSUMER_EVIDENCE {case} {root}')
        print('ACTUAL_RESULT', case, status, json.dumps(observation.result, sort_keys=True))
    return observed


def replay(observation, events):
    return runtime_check(CHECK_FLOW, events, observation.index)


def final_zero(events):
    """Only corrupt the recorded public return; all other real readings stay."""
    return [replace(event, result=0) if event.anchor == 'CHECK_RUN' and event.phase == 'return' else event
            for event in events]


def test_real_normal_and_failure_results_agree_with_relations(actual_consumers):
    for case, actual in actual_consumers.items():
        observation = actual['observation']
        assert actual['status'] == 0 if case in ('good', 'no_pytest') else actual['status'] != 0
        assert not observation.result['red'], (case, observation.result)
        assert observation.result['checked_relations'] == (2 if case == 'no_pytest' else 3)
        assert observation.finite['exhausted'] and observation.finite['verdict'] == 'ok'
        assert observation.static['checked'] is False and observation.static['verdict'] == 'grey'
        # Structural exhaustion is separate from the still-uncovered runtime edges.
        assert observation.result['verdict'] == 'grey'


@pytest.mark.parametrize('case,rule_id', [
    ('source_error', 'CHECK_SOURCE_EXIT'),
    ('load_error', 'CHECK_LOAD_EXIT'),
    ('pytest_error', 'CHECK_PYTEST_EXIT'),
])
def test_only_replacing_the_real_final_result_with_zero_is_rejected(actual_consumers, case, rule_id):
    actual = actual_consumers[case]
    observation = actual['observation']
    assert actual['status'] != 0
    corrupted = final_zero(observation.events)
    result = replay(observation, corrupted)
    print('FINAL_ZERO_REPLAY', case, json.dumps(result, sort_keys=True))
    assert any(rule_id in reason for reason in result['red'])


@pytest.mark.parametrize('anchor,bad_result', [
    ('CHECK_LOAD', {'errors': 'one'}),
    ('CHECK_SOURCES', 'red'),
    ('CHECK_PYTEST', {'returncode': 'one'}),
    ('CHECK_RUN', 'zero'),
])
def test_wrong_reading_types_are_red(actual_consumers, anchor, bad_result):
    observation = actual_consumers['good']['observation']
    changed = [replace(event, result=bad_result) if event.anchor == anchor and event.phase == 'return' else event
               for event in observation.events]
    result = replay(observation, changed)
    assert any('actual type' in reason for reason in result['red'])


def test_missing_fixed_reading_is_grey(actual_consumers):
    observation = actual_consumers['good']['observation']
    changed = [replace(event, result={}) if event.anchor == 'CHECK_LOAD' and event.phase == 'return' else event
               for event in observation.events]
    result = replay(observation, changed)
    assert not result['red']
    assert any('fixed reading field missing' in reason for reason in result['grey'])


def test_no_pytest_reading_is_unverified_instead_of_a_claim_about_success(actual_consumers):
    observation = actual_consumers['no_pytest']['observation']
    assert not any(event.anchor == 'CHECK_PYTEST' for event in observation.events)
    assert any('pytest_end: reading has 0 occurrences' in reason for reason in observation.result['grey'])
    assert observation.result['checked_relations'] == 2


def test_multiple_batch_readings_are_not_silently_first_or_last(actual_consumers):
    observation = actual_consumers['pytest_error']['observation']
    events = observation.events
    first = next(i for i, event in enumerate(events) if event.anchor == 'CHECK_PYTEST' and event.phase == 'call')
    stop = next(i for i, event in enumerate(events) if event.anchor == 'CHECK_SOURCES' and event.phase == 'call')
    # Duplicate a real recorded batch solely to test reading multiplicity. This
    # is a replay counterexample, not a claim that the consumer ran two batches.
    second = [replace(event, occurrence=event.occurrence+1) for event in events[first:stop]]
    changed = [*events[:stop], *second, *events[stop:]]
    changed = [replace(event, sequence=i) for i, event in enumerate(final_zero(changed), 1)]
    result = replay(observation, changed)
    assert not result['red'], result
    assert any('pytest_end: reading has 2 occurrences' in reason for reason in result['grey'])
    assert result['checked_relations'] == 2


def test_static_limit_is_written_separately_from_runtime(actual_consumers):
    cfg = actual_consumers['good']['cfg']
    rows = [json.loads(line) for line in (cfg.cache/'check-flow.jsonl').read_text().splitlines()]
    assert rows[0]['finite']['exhausted']
    assert rows[0]['static']['checked'] is False
    assert rows[-1]['static']['grey'] == ['self static paths not checked']


def test_stage_stdout_is_flushed_before_real_loading_finishes(tmp_path):
    (tmp_path/'pyproject.toml').write_text('[tool.pytest.ini_options]\ntestpaths=["tests"]\n')
    (tmp_path/'tests/intent').mkdir(parents=True)
    (tmp_path/'tests/intent/slow.py').write_text(
        'from pathlib import Path\nimport time\ntime.sleep(1.5)\n'
        'Path("loaded-complete").write_text("complete")\n')
    sdk = Path(cli.__file__).resolve().parents[2]
    bootstrap = ('import sys;sys.path.insert(0,sys.argv.pop(1));'
                 'from flowguard.intent.checkflow import CheckObservation;'
                 'from flowguard.intent.cli import _checked;'
                 'from flowguard.intent.config import load_config;'
                 'cfg=load_config();'
                 'exec("with CheckObservation(cfg) as observation:\\n observation.call(_checked,cfg)")')
    process = subprocess.Popen([sys.executable, '-c', bootstrap, str(sdk)], cwd=tmp_path,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    pending = queue.Queue()
    def read_lines():
        for line in process.stdout:
            pending.put(line)
        pending.put(None)
    reader = threading.Thread(target=read_lines, daemon=True)
    reader.start()
    parts = []
    try:
        while True:
            line = pending.get(timeout=10)
            if line is None:
                pytest.fail('no loading start was emitted: ' + ''.join(parts))
            parts.append(line)
            if 'CHECK_LOAD #1 start' in line:
                assert process.poll() is None
                assert not (tmp_path/'loaded-complete').exists()
                break
        while (line := pending.get(timeout=10)) is not None:
            parts.append(line)
        process.wait(timeout=10)
        output = ''.join(parts)
        assert process.returncode == 0, output
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)
        reader.join(timeout=2)
    rows = [json.loads(line) for line in (tmp_path/'.flowguard/cache/check-flow.jsonl').read_text().splitlines()]
    completed = next(row for row in rows if row.get('anchor') == 'CHECK_LOAD' and row.get('phase') == 'return')
    duration = f"{completed['elapsed_ns']/1_000_000:.2f}ms"
    assert 'CHECK_LOAD #1 return elapsed=' + duration in output
    assert completed['elapsed_ns'] >= 1_400_000_000
    print('LOAD_LIVE_STDOUT', output)


def test_shared_writer_failure_is_unavailable_without_changing_real_return(tmp_path):
    cfg = load_config(tmp_path)
    (cfg.cache/'check-flow.jsonl').mkdir(parents=True)
    with CheckObservation(cfg) as observation:
        assert observation.call(cli._checked, cfg) == 0
    assert any('diagnostics unavailable' in issue for issue in observation.issues)
    assert not observation.result['red']
    assert any('diagnostics unavailable' in reason for reason in observation.result['grey'])


def test_diagnostic_stdout_failure_does_not_prevent_the_real_stage(tmp_path, monkeypatch):
    from flowguard.intent import cache
    from flowguard.intent.loader import load
    cfg = load_config(tmp_path)
    model, data = load(cfg), cache.read(cfg)
    class BrokenOutput:
        def write(self, text):
            raise OSError('diagnostic output closed')
        def flush(self):
            raise OSError('diagnostic output closed')
    with CheckObservation(cfg) as observation:
        with monkeypatch.context() as patch:
            patch.setattr(sys, 'stdout', BrokenOutput())
            actual = observation.call(cli._check_selection, cfg, model, data, False, None,
                                      cfg.root/'tests/test_flowguard_intent.py')
    assert len(actual) == 6
    assert [event.phase for event in observation.events] == ['call', 'return']
    assert len([issue for issue in observation.issues if 'stage output unavailable' in issue]) == 1

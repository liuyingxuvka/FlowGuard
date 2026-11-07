"""Independent checks over events emitted by the real check call boundaries."""
from dataclasses import replace
import json
import ast

import pytest

from flowguard.intent import cli
from flowguard.intent.checkflow import CHECK_FLOW, CheckObservation
from flowguard.intent.config import load_config
from flowguard.intent.flow import runtime_check


def records(cfg):
    return [json.loads(line) for line in (cfg.cache/'check-flow.jsonl').read_text().splitlines()]


def test_real_empty_check_is_timed_and_validated_once(tmp_path):
    cfg = load_config(tmp_path)
    assert cli.check(cfg, diagnose=True) == 0
    rows = records(cfg)
    assert rows[0]['finite']['exhausted'] and rows[0]['finite']['verdict'] == 'ok'
    assert rows[0]['nodes'] == 10
    assert sum(row['kind'] == 'validation' for row in rows) == 1
    events = [row for row in rows if row['kind'] == 'event']
    assert [row['sequence'] for row in events] == list(range(1, len(events)+1))
    assert [row['monotonic_ns'] for row in events] == sorted(row['monotonic_ns'] for row in events)
    assert all(row['elapsed_ns'] >= 0 for row in events if row['phase'] != 'call')
    assert rows[-1]['run_succeeded'] and not rows[-1]['result']['red']
    assert any('unobserved edge' in reason for reason in rows[-1]['result']['grey'])


def test_replacing_a_real_stage_cannot_supply_a_success_event(tmp_path, monkeypatch):
    cfg = load_config(tmp_path)
    monkeypatch.setattr(cli, '_check_sources', lambda cfg: False)
    assert cli.check(cfg, diagnose=True) == 1
    rows = records(cfg)
    assert any(row['kind'] == 'unverified' for row in rows)
    assert not any(row.get('anchor') == 'CHECK_SOURCES' for row in rows)
    assert any('loaded -> returned' in reason for reason in rows[-1]['result']['red'])
    assert not rows[-1]['run_succeeded']


@pytest.mark.parametrize('failure', [ValueError('real stage failure'), KeyboardInterrupt()])
def test_actual_raise_and_interrupt_never_emit_a_return(tmp_path, monkeypatch, failure):
    cfg = load_config(tmp_path)
    def failing(cfg):
        raise failure
    monkeypatch.setattr(cli, '_check_sources', failing)
    with pytest.raises(type(failure)):
        cli.check(cfg, diagnose=True)
    rows = records(cfg)
    assert rows[-1]['run_completed'] is False and rows[-1]['run_succeeded'] is False
    assert any(row.get('anchor') == 'CHECK_RUN' and row.get('phase') == 'raise' for row in rows)
    assert not any(row.get('anchor') == 'CHECK_RUN' and row.get('phase') == 'return' for row in rows)


def test_deleting_or_reordering_actual_observations_is_detected(tmp_path):
    cfg = load_config(tmp_path)
    with CheckObservation(cfg) as observation:
        assert observation.call(cli._checked, cfg) == 0
    assert not observation.result['red']
    missing = [event for event in observation.events if event.anchor != 'CHECK_LOAD']
    missing = [replace(event, sequence=n) for n, event in enumerate(missing, 1)]
    assert runtime_check(CHECK_FLOW, missing, observation.index)['red']
    moved = observation.events[:]
    loaded = next(n for n, event in enumerate(moved) if event.anchor == 'CHECK_LOAD' and event.phase == 'return')
    source = next(n for n, event in enumerate(moved) if event.anchor == 'CHECK_SOURCES' and event.phase == 'call')
    moved[loaded], moved[source] = moved[source], moved[loaded]
    moved = [replace(event, sequence=n) for n, event in enumerate(moved, 1)]
    assert runtime_check(CHECK_FLOW, moved, observation.index)['red']


def test_supported_code_replacement_is_unverified_and_still_executes(tmp_path):
    from flowguard.intent.sites import _recompile, installed
    cfg = load_config(tmp_path)
    original = cli._checked
    def replace_body(function):
        function.body = [ast.Return(ast.Constant(37))]
    code = _recompile(original, ast.NodeTransformer(), lambda: True, replace_body)
    assert code.co_filename == original.__code__.co_filename
    assert code.co_firstlineno == original.__code__.co_firstlineno
    assert code.co_qualname == original.__code__.co_qualname
    with installed(original, code):
        assert cli.check(cfg, diagnose=True) == 37
    rows = records(cfg)
    assert any('installed code body' in row.get('message', '') for row in rows)
    assert not any(row.get('anchor') == 'CHECK_RUN' for row in rows)
    assert rows[-1]['coverage_verdict'] == 'grey'
    assert not rows[-1]['run_succeeded']


def test_only_canonical_sdk_model_sources_count_as_modelled(tmp_path, monkeypatch):
    from flowguard.intent.anchors import Index
    from flowguard.intent.checkflow import _source_index
    root = __import__('pathlib').Path(cli.__file__).resolve().parents[2]
    names = {node.reference for node in CHECK_FLOW.nodes}
    canonical = [anchor for anchor in _source_index().entries if anchor.name in names]
    summary = dict(rules={}, distincts=[])
    assert cli._unmodelled(Index(tuple(canonical)), summary, root=root) == []
    wrong = replace(canonical[0], file='other.py', qual='other_function')
    assert wrong.name in cli._unmodelled(Index((*canonical, wrong)), summary, root=root)
    wrong_digest = replace(canonical[0], source_digest='0'*64)
    assert wrong_digest.name in cli._unmodelled(Index((wrong_digest,)), summary, root=root)
    assert cli._unmodelled(Index(tuple(canonical)), summary, root=tmp_path)
    # A namesake inside the SDK's very source slice is ambiguous too.
    from flowguard.intent import checkflow
    duplicate = replace(canonical[0], qual='different_function')
    ambiguous = Index((*canonical, duplicate))
    monkeypatch.setattr(checkflow, '_source_index', lambda: ambiguous)
    assert duplicate.name in cli._unmodelled(ambiguous, summary, root=root)


def test_stage_observation_does_not_copy_the_cache_ledger(tmp_path):
    from flowguard.intent import cache
    from flowguard.intent.loader import load
    cfg = load_config(tmp_path)
    data = cache.read(cfg)
    private_payload = 'SHOULD_NOT_BE_LOGGED_' * 100_000
    data['unused'] = private_payload
    model = load(cfg)
    with CheckObservation(cfg) as observation:
        observation.call(cli._check_selection, cfg, model, data, False, None,
                         cfg.root/'tests/test_flowguard_intent.py')
    raw = (cfg.cache/'check-flow.jsonl').read_text()
    assert 'SHOULD_NOT_BE_LOGGED_' not in raw
    assert len(raw.encode()) < 20_000

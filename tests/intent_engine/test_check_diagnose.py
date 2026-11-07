"""The public diagnostic flag observes the same check without selecting tests."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from flowguard.intent import cache, checkflow, cli
from flowguard.intent.config import load_config
from test_cli import project


@pytest.mark.parametrize('everything', [False, True])
def test_default_check_never_constructs_diagnostic_observer_or_index(tmp_path, monkeypatch, everything):
    (tmp_path / 'test_plain.py').write_text('def test_plain(): assert True\n')
    cfg = load_config(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('default check must not construct diagnostic state')
    monkeypatch.setattr(checkflow, 'CheckObservation', forbidden)
    monkeypatch.setattr(checkflow, '_source_index', forbidden)
    assert cli.check(cfg, everything=everything) == 0
    path = cfg.cache / 'check-flow.jsonl'
    target_log = cfg.cache / 'anchor-events.jsonl'
    assert not path.exists()
    assert not target_log.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('previous diagnostic output\n')
    target_log.write_text('previous target diagnostic output\n')
    assert cli.check(cfg, everything=everything) == 0
    assert path.read_text() == 'previous diagnostic output\n'
    assert target_log.read_text() == 'previous target diagnostic output\n'


def projection(cfg):
    data = cache.read(cfg)
    return dict(results={rule: {item: payload['verdict'] for item, payload in value['items'].items()}
                         for rule, value in data['results'].items()},
                readings={test: {key: value[key] for key in ('outcome', 'kind', 'reason', 'phase')}
                          for test, value in data['tests'].items()},
                dependencies=data['deps'], ordinary_dependencies=data['test_deps'], traces=data['traces'],
                collected={file: value['tests'] for file, value in data['test_collection'].items()})


@pytest.mark.parametrize('wrong,expected', [(False, 0), (True, 1)])
def test_public_flag_keeps_actual_cli_outcomes_selection_dependencies_and_exit(tmp_path, wrong, expected):
    root, cfg = project(tmp_path, wrong=wrong)
    cli.init(cfg)
    (root / 'tests/test_actual.py').write_text(
        f'from {root.name} import accept\ndef test_actual(): assert not accept(4)\n')
    sdk = str(Path(cli.__file__).resolve().parents[2])
    bootstrap = 'import sys;sys.path.insert(0,sys.argv.pop(1));from flowguard.__main__ import main;raise SystemExit(main(sys.argv[1:]))'
    def run(diagnose, full):
        command = [sys.executable, '-c', bootstrap, sdk, 'check', *(['--all'] if full else []),
                   *(['--diagnose'] if diagnose else [])]
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=30)
        assert result.returncode == expected, (command, result.stdout, result.stderr)
        if diagnose:
            rows = [json.loads(line) for line in (cfg.cache/'check-flow.jsonl').read_text().splitlines()]
            assert rows[-1]['run_succeeded'] == (expected == 0)
            assert not rows[-1]['result']['red']
            if full:
                target_rows = [json.loads(line) for line in (cfg.cache/'anchor-events.jsonl').read_text().splitlines()]
                assert target_rows[0]['kind'] == 'session' and target_rows[0]['append'] is False
        else:
            assert not (cfg.cache/'check-flow.jsonl').exists()
            assert not (cfg.cache/'anchor-events.jsonl').exists()
        return projection(cfg), result.stdout
    cold = []
    for diagnose in (False, True):
        if cfg.cache.exists():
            shutil.rmtree(cfg.cache)
        value, output = run(diagnose, True)
        assert 'tests/test_actual.py::test_actual' in output
        cold.append(value)
    assert cold[0] == cold[1]
    baseline = tmp_path / 'warm-cache'
    (cfg.cache/'check-flow.jsonl').unlink()
    (cfg.cache/'anchor-events.jsonl').unlink()
    shutil.copytree(cfg.cache, baseline)
    baseline_stamps = {test: value['stamp'] for test, value in cache.read(cfg)['tests'].items()}
    warm = []
    selected = []
    for diagnose in (False, True):
        shutil.rmtree(cfg.cache)
        shutil.copytree(baseline, cfg.cache)
        value, output = run(diagnose, False)
        assert '0 rules rerun, 1 reused' in output
        changed = {test for test, value in cache.read(cfg)['tests'].items()
                   if value['stamp'] != baseline_stamps.get(test)}
        selected.append(changed)
        warm.append(value)
    assert warm[0] == warm[1] == cold[0]
    # Failed ordinary tests must keep rerunning in both modes; diagnostics cannot reuse that red as a pass.
    assert selected[0] == selected[1] == ({'tests/test_actual.py::test_actual'} if wrong else set())

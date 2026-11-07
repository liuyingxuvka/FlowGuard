"""Optional output failures cannot replace a completed public check result."""
import builtins
import io
import json

import pytest

from flowguard.intent import cli, diagnostics
from flowguard.intent.config import load_config


def break_final_reporting(monkeypatch):
    failed = []
    closed = io.StringIO()
    closed.close()

    def report(*args, **kwargs):
        text = str(args[0]) if args else ''
        if text.startswith(('red check flow:', 'grey check flow:', 'Check flow: coverage grey;')):
            failed.append(text)
            kwargs['file'] = closed
        return builtins.print(*args, **kwargs)

    monkeypatch.setattr(diagnostics, 'print', report, raising=False)
    # An unavailable diagnostic stdout must not trigger a failing stderr fallback.
    class ClosedDiagnosticStderr:
        def write(self, value):
            raise OSError('diagnostic stderr is unavailable')
        def flush(self):
            raise OSError('diagnostic stderr is unavailable')
    monkeypatch.setattr(cli.sys, 'stderr', ClosedDiagnosticStderr())
    return failed


@pytest.mark.parametrize('wrong,expected', [(False, 0), (True, 1)])
def test_real_public_good_and_bad_check_keep_exit_when_final_diagnostic_output_fails(tmp_path, monkeypatch, wrong, expected):
    (tmp_path/'tests').mkdir()
    (tmp_path/'pyproject.toml').write_text('[tool.pytest.ini_options]\ntestpaths=["tests"]\n')
    (tmp_path/'tests/test_result.py').write_text(f'def test_result(): assert {not wrong}\n')
    (tmp_path/'tests/test_flowguard_intent.py').write_text(cli.SENTINEL)
    cfg = load_config(tmp_path)
    failed = break_final_reporting(monkeypatch)
    assert cli.check(cfg, everything=True, diagnose=True) == expected
    assert failed
    rows = [json.loads(line) for line in (cfg.cache/'check-flow.jsonl').read_text().splitlines()]
    validation = next(row for row in rows if row['kind'] == 'validation')
    assert validation['run_succeeded'] == (expected == 0)
    assert not validation['result']['red']
    assert rows[-1] == dict(kind='diagnostic-unavailable', output='stdout', error='ValueError')


def test_diagnostic_output_failure_cannot_mask_self_model_red(tmp_path, monkeypatch):
    cfg = load_config(tmp_path)
    monkeypatch.setattr(cli, '_check_sources', lambda cfg: False)
    failed = break_final_reporting(monkeypatch)
    assert cli.check(cfg, diagnose=True) == 1
    assert failed and failed[0].startswith('red check flow:')
    rows = [json.loads(line) for line in (cfg.cache/'check-flow.jsonl').read_text().splitlines()]
    validation = next(row for row in rows if row['kind'] == 'validation')
    assert validation['result']['red']
    assert validation['run_succeeded'] is False

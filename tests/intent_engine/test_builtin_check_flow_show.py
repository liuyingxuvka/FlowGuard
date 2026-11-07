"""Reading the one built-in check model neither runs nor verifies it."""
from types import SimpleNamespace

from flowguard.intent import checkflow, cli, diagnostics
from flowguard.intent.config import load_config
from test_cli import project


def test_builtin_check_pipeline_show_is_bounded_and_has_no_diagnostic_side_effects(tmp_path, monkeypatch, capsys):
    cfg = load_config(tmp_path)
    def forbidden(*args, **kwargs):
        raise AssertionError('reading the built-in model must not execute or index it')
    monkeypatch.setattr(cli, 'build', forbidden)
    for name in ['CheckObservation', 'EventLog', '_source_index', 'finite_check', 'runtime_check']:
        monkeypatch.setattr(checkflow, name, forbidden)
    monkeypatch.setattr(checkflow, 'time', SimpleNamespace(monotonic_ns=forbidden, time_ns=forbidden))
    monkeypatch.setattr(diagnostics, 'time', SimpleNamespace(monotonic_ns=forbidden, time_ns=forbidden))
    before = {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert cli.show(cfg, 'CHECK_PIPELINE') == 0
    text = capsys.readouterr().out
    assert len(text.encode()) < 2048
    assert 'FLOW CHECK_PIPELINE' in text and 'nodes (10)' in text and 'relations (3)' in text
    assert all(node.name in text and node.reference in text for node in checkflow.CHECK_FLOW.nodes)
    assert 'checkflow.py:' in text and 'check-flow.jsonl' in text
    assert 'Historical logs do not verify the current run' in text
    assert before == {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert cli.show(cfg, 'CHECK_PIPELINE', full=True) == 0
    assert 'model source:' in capsys.readouterr().out
    assert before == {str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


def test_real_project_rule_named_check_pipeline_keeps_precedence(tmp_path, monkeypatch, capsys):
    root, cfg = project(tmp_path)
    policy = cfg.intent/'policy.py'
    policy.write_text(policy.read_text().replace("@rule('LIMIT',", "@rule('CHECK_PIPELINE',"))
    def forbidden(*args, **kwargs):
        raise AssertionError('a real project rule must keep its existing show path')
    monkeypatch.setattr(cli, '_builtin_check_flow_lines', forbidden)
    assert cli.show(cfg, 'CHECK_PIPELINE') == 0
    text = capsys.readouterr().out
    assert 'RULE CHECK_PIPELINE: acceptance' in text and 'built-in' not in text

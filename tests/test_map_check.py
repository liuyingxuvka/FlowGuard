"""Tests of the model and its real native implementation."""
import pytest
from pathlib import Path


def test_identical_info_grouped_into_one_line(capsys, tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from flowguard.map import cli
    from flowguard.map.common import Finding, print_findings
    notes = [Finding("info", "same", f"c{i}", "note") for i in range(24)]
    warnings = [Finding("warn", "same", f"w{i}", "warning") for i in range(3)]
    counts = print_findings(notes + warnings, "lint", as_json=False, limit=80)
    text = capsys.readouterr().out
    assert counts == {"error": 0, "warn": 3, "info": 24}
    assert sum(line.startswith("INFO") for line in text.splitlines()) == 1
    assert "INFO same x24: c0, c1, c10, c11, c12, c13, c14, c15 (+16 more; python -m flowguard map lint --json)" in text
    assert sum(line.startswith("WARN") for line in text.splitlines()) == 3
    print_findings(notes, "lint", as_json=True, limit=1)
    assert len(json.loads(capsys.readouterr().out)["findings"]) == 24
    # Exercise release's real output boundary: findings precede real model execution.
    import runpy
    from types import SimpleNamespace
    helpers = runpy.run_path(str(Path(__file__).parents[1] / ".flowguard/models/model_runs.py"))
    helpers["make_fixture"](tmp_path)
    monkeypatch.setattr(cli, "run_check", lambda *a, **kw: [Finding("info", "same", str(i), "note") for i in range(24)])
    assert cli.cmd_verify(tmp_path, SimpleNamespace(limit=80, jobs=1, shards=None)) == 0
    output = capsys.readouterr().out
    assert sum(line.startswith("INFO same x24:") for line in output.splitlines()) == 1
    assert "PASS  first" in output and "PASS  second" in output

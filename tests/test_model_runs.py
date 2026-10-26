"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_jobs_output_equals_sequential(tmp_path, capsys):
    from pathlib import Path
    from flowguard.map import cli
    import re
    import runpy
    source = Path(__file__).resolve().parents[1] / ".flowguard/models/model_runs.py"
    if not source.exists():
        source = source.parent.parent / "target/models/model_runs.py"
    fixture = runpy.run_path(str(source))["make_fixture"]
    fixture(tmp_path)
    outputs = []
    for jobs in (1, 3, 3):
        assert cli.main(["models", "--root", str(tmp_path), "--jobs", str(jobs)]) == 0
        output = capsys.readouterr().out
        outputs.append(re.sub(r"\s+\d+(?:\.\d+)?s", " <time>", output))
    assert outputs[0] == outputs[1] == outputs[2]


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


def test_pass_is_one_line_fail_keeps_rules():
    from flowguard.map.proof import ModelResult, render_results
    result = ModelResult("probe", "probe.py", rules=["works"], known_bad=["broken"], seconds=1.2, test_seconds=0.3,
                         hazards=["advisory"], closed_hazards=["old"])
    text = render_results([result], all_hazards=True)
    assert text.splitlines() == [f"PASS  {'probe':32} 1.2s  tests 0.3s", "models: 1 passed, 0 failed"]
    result.status = "fail"; result.problems = ["native mismatch"]
    text = render_results([result])
    assert "rules: works; known-bad: broken" in text and "native mismatch" in text
    assert "hazard" not in text


def test_sequence_soft_limit_warns(tmp_path):
    import json
    from _fg_helpers import proof__size_project as _size_project
    from flowguard.map.proof import run_models,render_results
    _size_project(tmp_path,events=3,length=7)
    result=run_models(tmp_path,['sized'])[0]
    assert result.status=='pass' and result.sequences==3279
    assert len([w for w in result.warnings if w.startswith('large_model:')])==1
    assert 'warning: large_model: 3,279 explored sequences' in render_results([result])
    import json
    p=tmp_path/'.flowguard/map.json';data=json.loads(p.read_text());data['accepted_debts']=[dict(code='large_model',component='sized',reason='one bounded table')];p.write_text(json.dumps(data))
    result=run_models(tmp_path,['sized'])[0]
    assert result.status=='pass' and not any(w.startswith('large_model:') for w in result.warnings)


def test_sequence_hard_limit_fails_the_model(tmp_path):
    from _fg_helpers import proof__size_project as _size_project
    from flowguard.map.proof import run_models
    data=_size_project(tmp_path,events=4,length=7)
    result=run_models(tmp_path,['sized'])[0]
    assert result.status=='fail' and result.sequences==21844
    assert any('over the hard limit 10,000' in problem for problem in result.problems)
    from flowguard.map.cli import main
    assert main(['--root',str(tmp_path),'models','sized'])==1
    from flowguard.map.target import main as target_main
    assert target_main(['--root',str(tmp_path),'start','Enforce size'])==0
    assert target_main(['--root',str(tmp_path),'add','sized'])==0
    assert target_main(['--root',str(tmp_path),'check'])==1


def test_time_over_the_limit_is_one_info(tmp_path):
    from _fg_helpers import proof__size_project as _size_project
    from flowguard.map.proof import run_models,render_results
    _size_project(tmp_path,seconds=0.000001)
    result=run_models(tmp_path,['sized'])[0]
    assert result.status=='pass'
    lines=[line for line in render_results([result]).splitlines() if line.startswith('INFO large_model')]
    assert len(lines)==1 and 'with its bound tests (advice limit 1e-06s)' in lines[0]

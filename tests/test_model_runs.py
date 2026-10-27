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




def test_pass_is_one_line_fail_keeps_rules():
    from flowguard.map.proof import ModelResult, render_results
    result = ModelResult("probe", "probe.py", rules=["works"], known_bad=["broken"], seconds=1.2, test_seconds=0.3)
    text = render_results([result])
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


@pytest.mark.parametrize('verdict',('proof','anchors','ports','tests'))
def test_model_fails_when_any_verdict_fails(tmp_path,verdict):
    from _fg_helpers import target__target_life_cycle_fixture_helpers
    from flowguard.map.proof import run_models,render_results
    if verdict=='ports':
        target__target_life_cycle_fixture_helpers('_target_fixture')['make_port_project'](tmp_path,'undeclared_write')
        results=run_models(tmp_path,['desk'])
        assert results[0].status=='fail' and any('undeclared_write' in p for p in results[0].problems)
        assert 'FAIL  desk' in render_results(results)
        return
    target__target_life_cycle_fixture_helpers('model_runs')['make_fixture'](tmp_path)
    path=tmp_path/'.flowguard/models/first.py';source=path.read_text()
    if verdict=='proof':source=source.replace('"two": make(2)','"two": make(1)')
    elif verdict=='anchors':source=source.replace('actual = load_anchor(IMPLEMENTED_BY["Run"], root=Path.cwd())()','actual = 1')
    else:
        source+='\nTESTED_BY={"one":["tests/test_native.py:test_first"]}\n'
        test=tmp_path/'tests/test_native.py';test.parent.mkdir();test.write_text('from native import first_value\ndef test_first(): assert first_value()==2\n')
    path.write_text(source)
    results=run_models(tmp_path,['first','second'],tests=verdict=='tests')
    assert [(r.model,r.status) for r in results]==[('first','fail'),('second','pass')]
    assert 'FAIL  first' in render_results(results)

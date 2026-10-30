"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


from _fg_helpers import (
    proof__size_project as _size_project,
    flowguard_port421_probe as probe,
    flowguard_port421_project as project,
    flowguard_port421_rewrite as rewrite,
    target__target_life_cycle_fixture_helpers,
)

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
    from flowguard.map.proof import run_models,render_results
    _size_project(tmp_path,events=3,length=7)
    result=run_models(tmp_path,['sized'])[0]
    assert result.status=='pass' and result.sequences==3279
    assert len([w for w in result.warnings if w.startswith('large_model:')])==1
    assert 'warning: large_model: 3,279 explored sequences' in render_results([result])
    import json
    p=tmp_path/'.flowguard/map.json';data=json.loads(p.read_text());data['accepted_debts']=[dict(expires='9999-12-31', code='large_model',component='sized',reason='one bounded table')];p.write_text(json.dumps(data))
    result=run_models(tmp_path,['sized'])[0]
    assert result.status=='pass' and not any(w.startswith('large_model:') for w in result.warnings)


def test_sequence_hard_limit_fails_the_model(tmp_path, capsys):
    data = _size_project(tmp_path, events=4, length=7)
    from flowguard.map.cli import main
    assert main(['--root', str(tmp_path), 'models', 'sized']) == 1
    output = capsys.readouterr().out
    assert "FAIL  sized" in output and "over the hard limit 10,000" in output and "21,844" in output
    from flowguard.map.target import main as target_main
    assert target_main(['--root',str(tmp_path),'start','Enforce size'])==0
    assert target_main(['--root',str(tmp_path),'add','sized'])==0
    assert target_main(['--root',str(tmp_path),'check'])==1


def test_time_over_the_limit_is_one_info(tmp_path):
    from flowguard.map.proof import run_models,render_results
    _size_project(tmp_path,seconds=0.000001)
    result=run_models(tmp_path,['sized'])[0]
    assert result.status=='pass'
    lines=[line for line in render_results([result]).splitlines() if line.startswith('INFO large_model')]
    assert len(lines) == 1 and lines[0].startswith('INFO large_model x1: sized ')
    assert 'model + bound tests over the 1e-06s advice' in lines[0]


@pytest.mark.parametrize('verdict',('proof','anchors','ports','tests'))
def test_model_fails_when_any_verdict_fails(tmp_path,verdict):
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

from dataclasses import fields, is_dataclass, replace
from pathlib import Path
import json
import runpy
from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory
from flowguard.map.mapfile import load_map
from flowguard.map.port import model_port, port_findings, upward
from flowguard.map.tree import build_tree

def test_undeclared_write_and_output_checks(tmp_path):
    from dataclasses import fields, is_dataclass, replace
    from pathlib import Path
    import json
    import runpy
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map
    from flowguard.map.port import model_port, port_findings, upward
    from flowguard.map.tree import build_tree
    for case, model, code, warning in (("undeclared_write", "desk", "undeclared_write", False),
            ("undeclared_output", "lending", "output_undeclared", False),
            ("unreached_output", "lending", "output_unreached", True)):
        root = tmp_path / case
        project(root, case)
        result = probe(root, model)
        assert result.status == ("pass" if warning else "fail"), result
        assert any(code in line for line in (result.warnings if warning else result.problems)), result
    from flowguard.map.port import changed_fields
    assert changed_fields(0, 1) == ()
    assert changed_fields({"a": 1}, {"a": 1, "b": []}) == ("b",)
    root = tmp_path / "no_declared_writes"
    project(root, "undeclared_write")
    rewrite(root, "desk", '    reads=("request",)\n    writes=("request",)\n', '    reads=("request",)\n')
    # A block without writes has no C1 promise; its parent still gets static S0c.
    assert not any("undeclared_write:" in line for line in probe(root).problems)


def test_handoff_value_must_be_received_as_an_event(tmp_path):
    from dataclasses import fields, is_dataclass, replace
    from pathlib import Path
    import json
    import runpy
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map
    from flowguard.map.port import model_port, port_findings, upward
    from flowguard.map.tree import build_tree
    root = tmp_path / "good"
    project(root)
    assert probe(root).status == "pass"
    for case in ("missing_receipt", "wrong_receiving_field"):
        root = tmp_path / case
        project(root, case)
        result = probe(root)
        assert result.status == "fail" and any("handoff_output_unhandled:" in p for p in result.problems), result
    # A new value's presence in a different invocation cannot supply its missing renamed receipt.
    root = tmp_path / "renamed"
    project(root)
    rewrite(root, "lending", '("lent","refused")}', '("lent","refused","waitlisted")}')
    rewrite(root, "desk", '"answer":"answer"', '"answer":("answer",{"lent":"lent","refused":"refused","waitlisted":"refused"})')
    result = probe(root)
    assert any("waitlisted" in p and "handoff_output_unhandled" in p for p in result.problems), result


def test_keeps_classes_and_parent_outputs(tmp_path):
    from dataclasses import fields, is_dataclass, replace
    from pathlib import Path
    import json
    import runpy
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map
    from flowguard.map.port import model_port, port_findings, upward
    from flowguard.map.tree import build_tree
    from flowguard.map.port import keeps_classes
    root = tmp_path / "good"
    project(root)
    rewrite(root, "desk", "max_sequence_length=1", "max_sequence_length=3")
    result = probe(root)
    assert result.status == "pass", result
    kinds = keeps_classes("desk")
    assert kinds["request"] == "input" and kinds["reply"] == "aggregate", kinds
    for case, code in (("domain_keeps", "keeps_not_orchestration"), ("parent_output", "parent_output_not_from_child")):
        root = tmp_path / case
        project(root, case)
        result = probe(root)
        assert result.status == "fail" and any(code in p for p in result.problems), result


def test_conformance_runs_one_fixture_project(monkeypatch):
    import runpy
    from pathlib import Path
    from flowguard.map import proof
    directory = Path(__file__).parents[1] / ".flowguard"
    model = directory / "target/models/model_runs.py"
    if not model.exists():
        model = directory / "models/model_runs.py"
    monkeypatch.syspath_prepend(str(directory / "models"))
    conformance = runpy.run_path(str(model))["conformance"]
    actual = proof.run_models
    calls = []

    def counted(root, *args, **kwargs):
        calls.append((root, kwargs.get("jobs", 1)))
        return actual(root, *args, **kwargs)

    monkeypatch.setattr(proof, "run_models", counted)
    conformance()
    assert len(calls) == 2
    assert calls[0][0] == calls[1][0]
    assert [jobs for root, jobs in calls] == [1, 2]

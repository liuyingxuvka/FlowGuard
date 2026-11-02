"""Focused release checks for the target promotion/commit seam."""
import json

from _fg_helpers import (
    map_git as git,
    flowguard_map_contracts421_project as basic_project,
)


def test_release_refuses_deleted_unstaged_target(tmp_path, capsys):
    from flowguard.__main__ import main

    basic_project(tmp_path)
    assert main(["map", "confirm", "all", "--root", str(tmp_path)]) == 0
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "user.name=probe", "-c", "user.email=probe@example.invalid", "commit", "-qm", "seed")
    assert main(["target", "start", "describe app", "--root", str(tmp_path)]) == 0
    assert main(["target", "add", "component:app", "--root", str(tmp_path)]) == 0
    path = tmp_path / ".flowguard/target/map.json"
    data = json.loads(path.read_text())
    data["components"][0]["summary"] = "Serve the application answer"
    path.write_text(json.dumps(data))
    git(tmp_path, "add", ".flowguard/target")
    git(tmp_path, "-c", "user.name=probe", "-c", "user.email=probe@example.invalid", "commit", "-qm", "target")
    assert main(["target", "promote", "--root", str(tmp_path)]) == 0
    assert main(["map", "confirm", "all", "--root", str(tmp_path)]) == 0
    capsys.readouterr()
    assert main(["release", "--shards", "1", "--root", str(tmp_path)]) == 1
    output = capsys.readouterr().out
    assert "target_deleted_not_staged: .flowguard/target/ files are deleted on disk but still committed" in output
    assert "suite: not run" in output and "verify: FAIL" in output
    git(tmp_path, "add", "-A", ".flowguard")
    assert main(["release", "--root", str(tmp_path)]) == 0



def test_open_target_is_release_warning(tmp_path, capsys):
    from flowguard.__main__ import main

    basic_project(tmp_path)
    assert main(["map", "confirm", "all", "--root", str(tmp_path)]) == 0
    assert main(["target", "start", "open app", "--root", str(tmp_path)]) == 0
    assert main(["target", "add", "component:app", "--root", str(tmp_path)]) == 0
    path = tmp_path / ".flowguard/target/map.json"
    data = json.loads(path.read_text())
    data["components"][0]["summary"] = "A planned app description"
    path.write_text(json.dumps(data))
    capsys.readouterr()
    assert main(["release", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.splitlines()[0] == ('warning: target "open app" exists: release checks only the current tree; '
                                                    'promote or drop the target before releasing')


DIAL = '''
from flowguard.flow import Model, need
m = Model("dial")
m.field("pos", range(0, 3), 0)

@m.action()
def up(s):
    need(s["pos"] < 2, "at the top")
    s["pos"] += 1

@m.action()
def down(s):
    need(s["pos"] > 0, "at the bottom")
    s["pos"] -= 1
MODEL = m
'''


def test_release_runs_the_flow_models_full_check(tmp_path, capsys):
    """Release checks the flow models of .flowguard/flow/ completely, mutants included, besides the
    legacy models: a conflict stops it (in --json too, whose stdout keeps its one verdict line)."""
    import shutil
    from pathlib import Path
    from flowguard.__main__ import main

    basic_project(tmp_path)
    assert main(["map", "confirm", "all", "--root", str(tmp_path)]) == 0
    capsys.readouterr()
    assert main(["release", "--root", str(tmp_path)]) == 0
    assert "flow: no flow models in .flowguard/flow/" in capsys.readouterr().out.splitlines()
    flow = tmp_path / ".flowguard/flow"
    flow.mkdir()
    shutil.copy(Path(__file__).parent / "flow/data/planted/rental_naive.py", flow / "rental.py")
    assert main(["release", "--root", str(tmp_path)]) == 1
    lines = capsys.readouterr().out.splitlines()
    assert "flow: 1 new conflict; complete" in lines and lines[-1].startswith("verify: FAIL")
    assert any(line.startswith("flow: NEW STUCK rental: ") for line in lines)
    assert main(["release", "--json", "--root", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    [line] = captured.out.splitlines()
    verdict = json.loads(line)
    assert verdict["verdict"] == "FAIL" and dict(level="error", code="flow_models", subject="flow") in verdict["codes"]
    assert "flow: 1 open conflict; complete" in captured.err.splitlines()
    (flow / "rental.py").write_text(DIAL, encoding="utf-8")
    assert main(["release", "--root", str(tmp_path)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert any(line.startswith("flow: clean, complete") for line in lines) and lines[-1].startswith("verify: PASS")
    assert json.loads((tmp_path / ".flowguard/conflicts.json").read_text(encoding="utf-8"))["conflicts"] == []


MERGED = "<<<<<<< HEAD\n{\"conflicts\": []}\n=======\n{\"conflicts\": []}\n>>>>>>> other\n"


def test_release_stops_in_one_line_on_an_unreadable_conflicts_file(tmp_path, capsys):
    """Acceptance A1: a merge-marked .flowguard/conflicts.json stops the release before any check
    with the file and its restore step on one line, exit 2 (never a traceback, never a failed gate)."""
    from flowguard.__main__ import main

    basic_project(tmp_path)
    assert main(["map", "confirm", "all", "--root", str(tmp_path)]) == 0
    (tmp_path / ".flowguard/flow").mkdir()
    (tmp_path / ".flowguard/flow/dial.py").write_text(DIAL, encoding="utf-8")
    (tmp_path / ".flowguard/conflicts.json").write_text(MERGED, encoding="utf-8")
    capsys.readouterr()
    assert main(["release", "--root", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    [line] = captured.err.splitlines()
    assert line.startswith("error: flow models: .flowguard/conflicts.json cannot be read (it holds git merge markers)")
    assert "git checkout --ours -- .flowguard/conflicts.json" in line
    assert main(["release", "--json", "--root", str(tmp_path)]) == 2
    verdict = json.loads(capsys.readouterr().out)
    assert verdict["verdict"] == "FAIL" and verdict["codes"][0]["code"] == "runtime_error"


def test_an_internal_error_in_the_flow_gate_stops_the_release_with_exit_2(tmp_path, capsys, monkeypatch):
    """Acceptance A1: the engine failing inside release is "internal error: ...", exit 2, not
    exit 1 (a gate that found a conflict)."""
    from flowguard.__main__ import main
    from flowguard.flow import jobs

    def boom(*args, **kwargs):
        raise KeyError("id")

    basic_project(tmp_path)
    assert main(["map", "confirm", "all", "--root", str(tmp_path)]) == 0
    (tmp_path / ".flowguard/flow").mkdir()
    (tmp_path / ".flowguard/flow/dial.py").write_text(DIAL, encoding="utf-8")
    monkeypatch.setattr(jobs, "plan", boom)
    capsys.readouterr()
    assert main(["release", "--root", str(tmp_path)]) == 2
    err = capsys.readouterr().err
    assert "error: flow models: internal error: KeyError: 'id' (tests/test_release_gate.py:" in err
    assert "Traceback" not in err


def test_release_without_a_legacy_map_runs_the_flow_gate_and_the_suite(tmp_path, capsys):
    """Acceptance A2: a project with only .flowguard/flow/ (no legacy map.json) gets the flow
    gate (check --full) and, with --shards, its whole test suite; release says plainly that no
    legacy map exists instead of stopping with "no map"."""
    import shutil
    from pathlib import Path
    from flowguard.__main__ import main

    flow = tmp_path / ".flowguard/flow"
    flow.mkdir(parents=True)
    shutil.copy(Path(__file__).parent / "flow/data/planted/rental_naive.py", flow / "rental.py")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_ok.py").write_text("def test_ok():\n    assert 1 + 1 == 2\n", encoding="utf-8")
    capsys.readouterr()
    assert main(["release", "--root", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert "no map at" not in captured.out + captured.err and "map scan first" not in captured.out + captured.err
    assert lines[0] == ("legacy map: none (.flowguard/map.json does not exist), so there is no map check, lint or "
                        "legacy model to run; the flow models are checked, and the tests with --shards")
    assert "flow: 1 new conflict; complete" in lines and any(line.startswith("flow: NEW STUCK rental: ") for line in lines)
    assert "suite: not run (fix the failures above first)" not in lines          # no --shards: not asked
    assert lines[-1].startswith("verify: FAIL")
    (flow / "rental.py").write_text(DIAL, encoding="utf-8")
    assert main(["release", "--root", str(tmp_path)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert any(line.startswith("flow: clean, complete") for line in lines)
    assert lines[-1] == ("verify: PASS (no test ran: without a legacy map no test is bound to a model; run the whole "
                         "suite with python -m flowguard release --shards 4, or in CI)")
    assert main(["release", "--shards", "1", "--root", str(tmp_path)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert "suite: status: pass  executed 1 of 1" in "\n".join(lines) and lines[-1] == "verify: PASS"
    (tests / "test_ok.py").write_text("def test_ok():\n    assert 1 + 1 == 3\n", encoding="utf-8")
    assert main(["release", "--shards", "1", "--json", "--root", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    [line] = captured.out.splitlines()
    verdict = json.loads(line)
    assert verdict["verdict"] == "FAIL" and dict(level="error", code="suite_failed", subject="suite") in verdict["codes"]
    assert dict(level="info", code="no_legacy_map", subject="map") in verdict["codes"]


def test_release_with_neither_map_nor_flow_models_still_names_the_first_step(tmp_path, capsys):
    from flowguard.__main__ import main

    (tmp_path / ".flowguard").mkdir()
    assert main(["release", "--root", str(tmp_path)]) == 2
    assert "no map at" in capsys.readouterr().err

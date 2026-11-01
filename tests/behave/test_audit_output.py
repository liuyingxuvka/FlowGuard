"""The public audit output follows real execution and current source identity."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from flowguard.behave.engine import prove
from flowguard.behave.project import replay
from flowguard.behave.report import render
from flowguard.behave.skeleton import derive
from .test_explore import program
from .test_gc6_crash import CSV_PROGRAM

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot behavior needs Python 3.12")
ROOT = Path(__file__).resolve().parents[2]


def command(*args):
    return subprocess.run([sys.executable, "-m", "flowguard.behave", *map(str, args)],
                          cwd=ROOT, capture_output=True, text=True)


def test_unhit_edit_and_actual_cap_are_scoped_in_one_json_line(program):
    for args in (("init", "-q"), ("config", "user.name", "Fixture"), ("config", "user.email", "fixture@example.invalid"),
                 ("add", "program.py"), ("commit", "-qm", "baseline")):
        subprocess.run(["git", "-C", str(program), *args], check=True, capture_output=True)
    path = program / "program.py"
    path.write_text(path.read_text() + "\ndef unused_entry():\n    return 7\n")
    (program / ".flowguard").mkdir()
    (program / ".flowguard/skeleton.py").write_text(
        "budget(world='small', seeds=[9], steps=2, node_cap=1, why='finite output control')\n")
    run = command("audit", "--root", program, "--world", "small", "--json")
    assert run.returncode == 0, run.stderr
    assert len(run.stdout.splitlines()) == 1
    shown = json.loads(run.stdout)
    assert shown["word"] == shown["verdict"] == "UNCHECKED" and shown["exit"] == 0
    assert shown["change_lines"][0] == 0 and shown["change_lines"][1] > 0
    assert shown["extent"]["capped"] > 0
    assert "hit_lines" not in shown["coverage"]
    assert shown["inputs"]["contexts"][0]["options"]["node_cap"] == 1
    assert shown["inputs"]["contexts"][0]["options"]["seed"] == 9
    assert {"new", "existing", "explored", "least", "moved", "tree", "items", "next"} <= shown.keys()
    view = command("why", "--root", program, "--coverage", "--json")
    assert view.returncode == 0, view.stderr
    facts = json.loads(view.stdout)
    assert facts["state"] == "recorded" and facts["coverage"]["unhit_lines"]
    assert facts["coverage"]["hit_lines"]
    assert facts["coverage"]["modules"]["program.py"][0] < facts["coverage"]["modules"]["program.py"][1]
    path.write_text(path.read_text().replace("return 7", "return 8"))
    stale = command("why", "--root", program, "--coverage", "--json")
    assert stale.returncode == 1
    assert json.loads(stale.stdout)["state"] == "unchecked"


def test_why_cli_replays_real_crash_and_then_observes_the_fix(tmp_path):
    path = tmp_path / "program.py"
    path.write_text(CSV_PROGRAM)
    candidate, = replay(derive(tmp_path), [], operation="crashes")["candidates"]
    proof = prove(tmp_path, candidate)
    assert proof["matched"]
    original = command("why", proof["id"], "--root", tmp_path)
    assert original.returncode == 0, original.stderr
    assert "AttributeError" in original.stdout and "replayed now: still fails at step 1" in original.stdout
    assert not any(line.startswith("{") for line in original.stdout.splitlines())
    path.write_text(CSV_PROGRAM.replace("for key, value in raw.items()}", "for key, value in raw.items() if key is not None}"))
    fixed = command("why", proof["id"], "--root", tmp_path, "--json")
    assert fixed.returncode == 0, fixed.stderr
    result = json.loads(fixed.stdout)
    assert not result["matched"] and result["state"] == "no-longer-reproduces"


@pytest.mark.parametrize("args", [("--steps", "0"), ("--node-cap", "-1"), ("--seeds", "a")])
def test_bad_audit_budget_is_a_usage_error(args):
    result = command("audit", *args)
    assert result.returncode == 2 and not result.stdout


def test_partial_phases_do_not_complete_a_world_or_clear_the_audit():
    phases = ["walk", "crash", "agreement", "reach", "stuck"]
    extent = {"complete": True, "capped": False, "successful": 2,
              "successful_step_budget": 2, "reason": "complete"}
    facts = {"extent": extent, "footprint": {"reusable": True, "untracked": []},
             "execution": {"calls": [{"result": "full execution stays out of default output"}]}}
    complete = {"world": "default", "seed": 0, "facts": facts}
    partial = {"world": "small", "seed": 1, "start": {}, "options": {"steps": 2},
               "identity": "partial-input", "reused": False, "elapsed_seconds": 0.2, "facts": facts}
    result = {"identity": "source", "runs": [complete], "items": [], "errors": [],
              "missing_checks": [], "facts_reused": 0,
              "coverage": {"hit_functions": ["program:run"], "known_functions": 1,
                           "front_doors": [], "ui": "none", "modules": {"program.py": [1, 1]},
                           "changed_lines": [["program.py", 1]], "unhit_lines": []}}
    assert json.loads(render(result, as_json=True))["word"] == "CLEAR"
    progress = [{"world": "default", "seed": 0, "done": phases, "pending": [], "reused": []},
                {"world": "small", "seed": 1, "done": phases[:2], "pending": phases[2:],
                 "reused": ["walk"], "reason": "native child failed: 124"}]
    result.update(partial_runs=[partial], phase_progress=progress)
    shown = json.loads(render(result, as_json=True))
    assert shown["word"] == "UNCHECKED" and shown["exit"] == 0
    assert shown["extent"]["world_runs"] == 1
    assert shown["phase_progress"] == progress
    assert shown["partial_runs"] == [{key: value for key, value in partial.items() if key != "facts"}
                                     | {"extent": extent}]
    text = render(result)
    assert text.startswith("UNCHECKED") and "1 completed world/seed runs; 1 partial" in text
    assert "done: walk, crash; pending: agreement, reach, stuck; reused: walk" in text
    assert "reason: native child failed: 124" in text
    assert "full execution stays out" not in text and "RUNNING" not in text
    # Failure before the first completed phase has progress, but no partial facts.
    result.update(partial_runs=[], phase_progress=[{**progress[1], "done": [], "pending": phases}])
    assert json.loads(render(result, as_json=True))["word"] == "UNCHECKED"

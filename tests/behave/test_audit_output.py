"""The public audit output follows real execution and current source identity."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from flowguard.behave.engine import prove
from flowguard.behave.project import replay
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

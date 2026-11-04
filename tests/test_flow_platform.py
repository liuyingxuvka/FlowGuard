"""The Linux flow engine must not break legacy commands on other platforms."""
import json
import os
from pathlib import Path
import subprocess
import sys

from _fg_helpers import flowguard_map_contracts421_project as basic_project


REPO = Path(__file__).resolve().parents[1]
UNSUPPORTED = "flow-model checks currently support Linux only"
SCRIPT = '''
import contextlib, io, json, sys
class NoFcntl:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "fcntl":
            raise ModuleNotFoundError("simulated platform has no fcntl", name="fcntl")
sys.modules.pop("fcntl", None)
sys.meta_path.insert(0, NoFcntl())
from flowguard.__main__ import main
from flowguard.flow import jobs
request = json.loads(sys.stdin.read())
if request["unsupported"]:
    actual_platform = sys.platform
    sys.platform = "win32"
    problem = jobs.platform_problem()
    sys.platform = actual_platform
    assert problem == "flow-model checks currently support Linux only"
    jobs.platform_problem = lambda: problem
out, err = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
    try:
        code = main(request["arguments"])
    except SystemExit as stopped:
        code = stopped.code
print(json.dumps({"code": code, "out": out.getvalue(), "err": err.getvalue()}))
'''


def run(root, *arguments, unsupported=False):
    result = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        input=json.dumps({"arguments": [*arguments, "--root", str(root)],
                          "unsupported": unsupported}),
        cwd=root, env={**os.environ, "PYTHONPATH": str(REPO)},
        text=True, encoding="utf-8", capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_missing_fcntl_does_not_break_legacy_commands(tmp_path):
    basic_project(tmp_path)
    for arguments in (("--help",), ("status",), ("where", "app.py"), ("release",)):
        result = run(tmp_path, *arguments)
        assert result["code"] == 0, result
        assert "Traceback" not in result["out"] + result["err"]
        assert UNSUPPORTED not in result["out"] + result["err"]


def test_non_linux_flow_commands_refuse_without_loading_or_changing_conflicts(tmp_path):
    basic_project(tmp_path)
    models = tmp_path / ".flowguard/flow"
    models.mkdir()
    (models / "saved.py").write_text('raise AssertionError("the model must not run")\n')
    record = tmp_path / ".flowguard/conflicts.json"
    record.write_text(json.dumps({"conflicts": [
        {"id": "F-saved", "kind": "STUCK", "model": "saved", "subject": "tool T1",
         "text": "a confirmed conflict", "sources": []}], "unknown": [], "models": {}, "closed": []}))
    original = record.read_bytes()
    for arguments in (("check",), ("show",), ("release",)):
        result = run(tmp_path, *arguments, unsupported=True)
        assert result["code"] == 2, result
        lines = (result["out"] + result["err"]).splitlines()
        assert len(lines) == 1 and UNSUPPORTED in lines[0], result
        assert "Traceback" not in lines[0]
        assert record.read_bytes() == original
    status = run(tmp_path, "status", unsupported=True)
    assert status["code"] == 0 and "F-saved" in status["out"], status
    assert UNSUPPORTED in status["out"], status
    assert record.read_bytes() == original


def test_non_linux_release_names_a_damaged_record_before_execution_limit(tmp_path):
    basic_project(tmp_path)
    models = tmp_path / ".flowguard/flow"
    models.mkdir()
    (models / "saved.py").write_text('raise AssertionError("must not execute")\n')
    record = tmp_path / ".flowguard/conflicts.json"
    record.write_text("{}")
    result = run(tmp_path, "release", "--json", unsupported=True)
    assert result["code"] == 2
    assert "conflicts.json cannot be read" in result["err"]
    assert json.loads(result["out"])["codes"][0]["subject"] == "flow"
    assert record.read_text() == "{}"

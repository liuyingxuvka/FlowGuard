"""Printed advice is a portable command; editing instructions remain human text."""
import json
import os
from pathlib import Path
import re
import shlex
import subprocess

import pytest

from _fg_helpers import (
    target_SHELF_TARGET as SHELF_TARGET,
    target_shelf_project as shelf_project,
    view_locate_fixture as locate_fixture,
)
from test_requests import _call


def _next(output, root):
    from flowguard.__main__ import _verb_parser
    from flowguard.map.cli import build_parser
    from flowguard.map.common import ADVICE_IDS

    items = []
    for line in output.splitlines():
        if not line.startswith("next["):
            continue
        match = re.fullmatch(r"next\[([a-z_]+)\]: (.+)", line)
        assert match, line
        identifier, command = match.groups()
        assert identifier in ADVICE_IDS
        argv = shlex.split(command)
        assert argv[:3] == ["python", "-m", "flowguard"], argv
        assert not any("<" in arg or ">" in arg or arg in {"then", "&&", ";"} for arg in argv)
        parser = build_parser() if argv[3] == "map" else _verb_parser(argv[3])
        parsed = parser.parse_args(argv[4:])
        assert Path(parsed.root).is_absolute() and Path(parsed.root) == root.resolve()
        items.append(dict(id=identifier, command=command))
    assert items, output
    return items


def _human(output):
    return "\n".join(line for line in output.splitlines() if not line.startswith("next["))


def _replay(item, elsewhere):
    argv = shlex.split(item["command"])
    assert argv[3] in {"read", "status", "map", "target"}
    if argv[3] == "target":
        assert argv[4] == "check"  # Replaying advice must not promote or stage a target.
    if argv[3] == "map":
        assert argv[4] in {"scan", "digest", "find", "show", "models", "check", "lint"}
    elsewhere.mkdir(exist_ok=True)
    environment = dict(os.environ)
    repository = str(Path(__file__).resolve().parents[1])
    environment["PYTHONPATH"] = os.pathsep.join(filter(None, [repository, environment.get("PYTHONPATH")]))
    return subprocess.run(argv, cwd=elsewhere, env=environment,
                          capture_output=True, text=True, timeout=90)


def test_request_without_map_advises_real_scan_and_digest(tmp_path, capsys):
    root = tmp_path / "中文 plain folder"
    root.mkdir()
    source = root / "owner request.txt"
    original = "续借保持为三次。\r\nPreserve owner bytes.\n".encode()
    source.write_bytes(original)
    (root / "app.py").write_text("def run(): return 1\n", encoding="utf-8")
    code, output, errors = _call(root, capsys, "req", "add", str(source), "--id", "R1")
    assert code == 0 and not errors
    item, = _next(output, root)
    argv = shlex.split(item["command"])
    assert argv[3:5] == ["map", "scan"] and "--write" not in argv
    requests = root / ".flowguard/requests"
    snapshot = {path.name: path.read_bytes() for path in requests.iterdir() if path.is_file()}
    assert original in snapshot.values()
    scan = _replay(item, tmp_path / "other cwd")
    assert scan.returncode == 0, (scan.stdout, scan.stderr)
    digest, = _next(scan.stdout, root)
    assert shlex.split(digest["command"])[3:6] == ["map", "digest", "all"]
    replay = _replay(digest, tmp_path / "other cwd")
    assert replay.returncode == 0, (replay.stdout, replay.stderr)
    assert source.read_bytes() == original
    assert snapshot == {path.name: path.read_bytes() for path in requests.iterdir() if path.is_file()}


def test_target_start_error_and_json_share_executable_advice(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    code, output, errors = _call(root, capsys, "target", "start", "change lending safely")
    assert code == 0 and not errors
    start, = _next(output, root)
    assert "target add" in _human(output) and "edit" in _human(output)
    assert _replay(start, tmp_path / "other cwd").returncode == 0
    code, output, errors = _call(root, capsys, "target", "check")
    assert code == 1 and not errors and "ERROR " in output
    item, = _next(output, root)
    assert "fix the target design" in _human(output)
    result = _replay(item, tmp_path / "other cwd")
    assert result.returncode in {0, 1}, (result.stdout, result.stderr)
    json_code, structured, errors = _call(root, capsys, "target", "check", "--json")
    assert json_code == code and not errors and len(structured.splitlines()) == 1
    payload = json.loads(structured)
    assert payload["verdict"] == "FAIL" and payload["codes"]
    assert {key: payload["next"][key] for key in ("id", "command")} == item
    assert _call(root, capsys, "target", "check")[0] == 1


def test_target_todo_advice_executes_without_completing_the_plan(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    assert _call(root, capsys, "target", "start", "holds")[0] == 0
    for node in ("loans", "lending"):
        assert _call(root, capsys, "target", "add", node)[0] == 0
    directory = root / ".flowguard/target"
    for relative in ("map.json", "models/lending.py"):
        (directory / relative).write_text(SHELF_TARGET[relative], encoding="utf-8")
    code, output, errors = _call(root, capsys, "target", "check")
    assert code == 3 and not errors and "TO-DO model lending:" in output
    assert "LoanService.hold" in output and "test_hold_gets_returned_copy" in output
    item, = _next(output, root)
    assert "write the code and tests" in _human(output)
    result = _replay(item, tmp_path / "other cwd")
    assert result.returncode in {0, 3}, (result.stdout, result.stderr)
    assert _call(root, capsys, "target", "check")[0] == 3


@pytest.mark.parametrize("case", ["bound", "unbound", "owned", "unowned"])
def test_find_location_preserves_binding_help_and_portable_next(tmp_path, capsys, case):
    root = tmp_path / "中文 lookup"
    helper = locate_fixture()
    helper["fixture"](root)
    code, output, errors = _call(root, capsys, "read", "--find", helper["CASES"][case])
    assert code == 0 and not errors
    human = _human(output)
    if case == "bound":
        assert "bound to: owner (rule safe)" in human
        return  # Bound tests already show their code/model location without advice.
    item, = _next(output, root)
    assert {"unbound": "TESTED_BY", "owned": "target add owner", "unowned": "add the rule"}[case] in human
    replay = _replay(item, tmp_path / "other cwd")
    assert replay.returncode == 0, (replay.stdout, replay.stderr)


def test_find_words_keeps_extend_guidance_outside_the_command(tmp_path, capsys):
    root = tmp_path / "lookup"
    locate_fixture()["fixture"](root)
    code, output, errors = _call(root, capsys, "read", "--find", "owned", "operations")
    assert code == 0 and not errors and "extend the owner" in _human(output)
    item, = _next(output, root)
    assert _replay(item, tmp_path / "other cwd").returncode == 0


@pytest.mark.parametrize("open_target", [False, True])
def test_template_advice_names_real_models_or_target_check(tmp_path, capsys, open_target):
    from flowguard.__main__ import main

    root = shelf_project(tmp_path)
    capsys.readouterr()
    if open_target:
        assert _call(root, capsys, "target", "start", "add a behaviour model")[0] == 0
    assert main(["template", "behaviour", "--write", str(root)]) == 0
    items = _next(capsys.readouterr().out, root)
    assert {item["id"] for item in items} == ({"check"} if open_target else {"models"})
    result = _replay(items[0], tmp_path / "other cwd")
    assert result.returncode != 0, (result.stdout, result.stderr)
    assert 'anchor file missing: shop/orders.py' in result.stdout + result.stderr

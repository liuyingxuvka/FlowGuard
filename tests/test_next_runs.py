"""Every next step that promote and status print runs as printed and leaves the project committed and clean."""
from __future__ import annotations

import json
import os
import subprocess

import pytest

from _fg_helpers import (
    target__load_map as _load_map,
    target__target_life_cycle_fixture_helpers as _fixture_helpers,
    target__write_map as _write_map,
)

pytestmark = pytest.mark.skipif(os.name == "nt", reason="runs the printed POSIX shell text")


def _cli(root, capsys, *arguments):
    from flowguard.__main__ import main
    code = main([*arguments, "--root", str(root)])
    output = capsys.readouterr()
    return code, output.out, output.err


def _git(root, *arguments):
    return subprocess.run(["git", "-c", "user.name=probe", "-c", "user.email=probe@example.invalid",
                           "-C", str(root), *arguments], check=True, capture_output=True, text=True).stdout


def _next_lines(output):
    return [line for line in output.splitlines() if line.startswith(("next[", "NEXT next["))]


def _run_printed(line, cwd):
    command = line.removeprefix("NEXT ").split("]: ", 1)[1]
    return subprocess.run(command, shell=True, cwd=cwd, capture_output=True, text=True)


def _ready_to_promote(tmp_path, capsys):
    """A committed shelf project with a clean target, a code edit, a new test and an unrelated file."""
    helpers = _fixture_helpers("target_findings")
    root = helpers["make_project"](tmp_path / "next project")
    current = _load_map(root)
    current["components"][1]["files"].append("shelf/new*.py")
    _write_map(root, current)
    (root / "shelf/new helper.py").write_text("def extra():\n    return 'new helper'\n")
    assert _cli(root, capsys, "map", "confirm", "all")[0] == 0
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "seed")
    helpers["stage_target"](root)
    target_model = root / ".flowguard/target/models/shelf_rule.py"
    target_model.write_text(target_model.read_text() +
                            '\nTESTED_BY = {"one_loan_step": ["tests/test_added.py:test_step"]}\n')
    (root / "shelf/catalog.py").write_text("def capacity():\n    return 1\n\n# current change\n")
    (root / "tests/test_added.py").write_text("from shelf.loans import advance\ndef test_step():\n    assert advance(0) == 1\n")
    (root / "scratch.txt").write_text("unrelated\n")
    capsys.readouterr()
    return root


def _commit_and_assert_clean(root, tmp_path, capsys):
    _git(root, "commit", "-qm", "Extend the shelf with one loan step, in my own words")
    assert _git(root, "status", "--porcelain").splitlines() == ["?? scratch.txt"]
    assert not (root / ".flowguard/target").exists()
    for arguments in (("map", "check", "--strict"), ("release",)):
        code, output, errors = _cli(root, capsys, *arguments)
        assert code == 0, (arguments, output, errors)
        assert not any(line.startswith(("ERROR", "WARN")) and ("stale" in line or "draft" in line)
                       for line in output.splitlines()), output


def test_status_without_target_names_no_failing_command(tmp_path, capsys):
    root = _fixture_helpers("target_findings")["make_project"](tmp_path / "plain")
    code, output, _ = _cli(root, capsys, "status")
    assert code == 0
    assert "target check" not in output and "verdicts:" not in output, output
    for line in _next_lines(output):
        assert _run_printed(line, tmp_path).returncode == 0, line


def test_promote_prints_one_next_that_leaves_the_project_clean(tmp_path, capsys):
    root = _ready_to_promote(tmp_path, capsys)
    code, output, errors = _cli(root, capsys, "target", "promote")
    assert code == 0 and not errors, output
    lines = _next_lines(output)
    assert len(lines) == 1, output
    result = _run_printed(lines[0], tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    _commit_and_assert_clean(root, tmp_path, capsys)


def test_promote_json_next_leaves_the_project_clean(tmp_path, capsys):
    root = _ready_to_promote(tmp_path, capsys)
    code, output, errors = _cli(root, capsys, "target", "promote", "--json")
    assert code == 0 and not errors, output
    step = json.loads(output)["next"]
    result = subprocess.run(step["command"], shell=True, cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    _commit_and_assert_clean(root, tmp_path, capsys)


def test_status_next_after_promote_runs_verbatim(tmp_path, capsys):
    root = _ready_to_promote(tmp_path, capsys)
    assert _cli(root, capsys, "target", "promote")[0] == 0
    code, output, _ = _cli(root, capsys, "status")
    assert code == 0
    lines = [line for line in output.splitlines() if line.startswith("NEXT ")]
    assert len(lines) == 1, output
    assert "your own message" in output
    result = _run_printed(lines[0], tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    _commit_and_assert_clean(root, tmp_path, capsys)


def test_status_does_not_guess_files_for_a_record_without_a_file_list(tmp_path, capsys):
    from flowguard.map.mapfile import load_map
    from flowguard.map.records import prepare_change, publish_change
    root = _fixture_helpers("target_findings")["make_project"](tmp_path / "older record")
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "seed")
    prepared = prepare_change(root, goal="promoted by an older FlowGuard", links=[], base={}, inputs={},
                              merged=load_map(root), model_bytes={}, deleted=[], checked="Fixture record.")
    prepared["record"].pop("stage", None)
    prepared["json"] = (json.dumps(prepared["record"], ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    publish_change(root, prepared)
    code, output, _ = _cli(root, capsys, "status")
    assert code == 0
    assert f"change {prepared['id']} records no file list" in output, output
    assert not _next_lines(output), output


def test_promote_stops_before_applying_when_git_cannot_list_the_files(tmp_path, capsys, monkeypatch):
    from flowguard.map import impact_history
    root = _ready_to_promote(tmp_path, capsys)
    original = impact_history.read_git_paths
    def broken(path, *arguments):
        if "--cached" in arguments:
            raise subprocess.CalledProcessError(128, ["git", *arguments], stderr=b"index is locked")
        return original(path, *arguments)
    monkeypatch.setattr(impact_history, "read_git_paths", broken)
    before = (root / ".flowguard/map.json").read_bytes()
    code, output, errors = _cli(root, capsys, "target", "promote")
    assert code == 2 and "cannot list the files to stage" in errors, (output, errors)
    assert (root / ".flowguard/target").exists() and (root / ".flowguard/map.json").read_bytes() == before
    assert not list((root / ".flowguard/changes").glob("*.json")) if (root / ".flowguard/changes").exists() else True


def test_promote_stops_before_applying_when_git_cannot_diff_the_target_base(tmp_path, capsys, monkeypatch):
    from flowguard.map import impact_history
    root = _ready_to_promote(tmp_path, capsys)
    original = impact_history.read_git_paths
    def broken(path, *arguments):
        if arguments[:1] == ("diff",) and "--no-renames" not in arguments:
            raise subprocess.CalledProcessError(128, ["git", *arguments], stderr=b"bad object in the base")
        return original(path, *arguments)
    monkeypatch.setattr(impact_history, "read_git_paths", broken)
    before = (root / ".flowguard/map.json").read_bytes()
    code, output, errors = _cli(root, capsys, "target", "promote")
    assert code == 2 and "bad object in the base" in errors, (output, errors)
    assert (root / ".flowguard/target").exists() and (root / ".flowguard/map.json").read_bytes() == before

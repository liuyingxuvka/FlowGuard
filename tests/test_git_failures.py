"""An object Git cannot read, or a Git that refuses to run, is that failure: never a file absent at the base,
a folder without Git, or a target started at HEAD."""
from __future__ import annotations

import os

import pytest

from flowguard.map.mapfile import MapError
from test_reported_failures import _failing_git, _git


def _drop_blob(root, revision, path):
    """Delete the loose object of one file at a commit, as a damaged or partial clone lacks it."""
    blob = _git(root, "rev-parse", f"{revision}:{path}").decode().strip()
    (root / ".git/objects" / blob[:2] / blob[2:]).unlink()


def test_a_missing_base_blob_stops_the_touch_check_instead_of_crediting_the_line(tmp_path):
    from _fg_helpers import target__fg403_helpers as gap_helpers
    from flowguard.map import target as native
    from flowguard.map.mapfile import load_map
    from flowguard.map.plan import check_plan
    from flowguard.map.targetfile import build_target_view, load_target
    root = tmp_path / "repo"
    root.mkdir()
    gap_helpers()["make_project"](root, gap_helpers()["regular_source"]())
    _git(root, "init", "-q")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "function baseline")
    assert native.start_target(root, "change the function") == 0
    assert native.add_to_target(root, "one") == 0
    target = load_target(root)
    view = build_target_view(root, load_map(root), target)
    (root / ".flowguard/target/PLAN.txt").write_text('touch: native.py:value because "check it"\n', encoding="utf-8")
    assert [item.code for item in check_plan(root, target, view)[1]] == ["plan_item_not_done"]
    _drop_blob(root, "HEAD", "native.py")
    with pytest.raises(MapError, match="git cat-file failed"):
        check_plan(root, target, view)


def _committed_shelf_project(tmp_path):
    from _fg_helpers import target__target_life_cycle_fixture_helpers as fixture_helpers
    from flowguard.__main__ import main
    root = tmp_path / "repo"
    fixture_helpers()["make_project"](root)
    assert main(["map", "confirm", "all", "--root", str(root)]) == 0
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    return root


@pytest.mark.parametrize("path", ["shelf/loans.py", ".flowguard/models/shelf_rule.py", ".flowguard/map.json"])
def test_a_missing_base_blob_stops_change_instead_of_reading_a_new_file(tmp_path, capsys, path):
    """Named files skip git diff; their old text then comes from the base commit alone."""
    from flowguard.__main__ import main
    root = _committed_shelf_project(tmp_path)
    changed = root / path
    changed.write_bytes(changed.read_bytes().rstrip(b"\n") + (b" \n" if path.endswith(".json") else b"\n# edited\n"))
    _git(root, "add", "-A")  # the index holds the new bytes, so only the base blob is missing
    _drop_blob(root, "HEAD", path)
    capsys.readouterr()
    code = main(["change", path, "--root", str(root)])
    output = capsys.readouterr()
    assert code == 2 and "git cat-file failed" in output.err, (output.out, output.err)


def test_change_in_a_folder_without_git_needs_no_git_executable(tmp_path, capsys, monkeypatch):
    from _fg_helpers import target__target_life_cycle_fixture_helpers as fixture_helpers
    from flowguard.__main__ import main
    root = tmp_path / "plain"
    fixture_helpers()["make_project"](root)
    assert main(["map", "confirm", "all", "--root", str(root)]) == 0
    (root / "shelf/loans.py").write_text("from shelf.catalog import capacity\n\ndef advance(value):\n"
                                         "    return capacity() + value\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path / "no-bin"))
    capsys.readouterr()
    for arguments in (["change"], ["change", "shelf/loans.py"]):
        assert main([*arguments, "--root", str(root)]) == 0, (arguments, capsys.readouterr())
        output = capsys.readouterr()
        assert "git executable not found" not in output.err and "changed functions" not in output.out, output


def test_a_repository_git_cannot_give_a_work_tree_is_an_error_not_a_folder_without_git(tmp_path, capsys):
    """With core.bare set in a checkout, Git refuses work-tree commands; FlowGuard says so instead of no Git."""
    from flowguard.__main__ import main
    from flowguard.map.common import git_common_directory
    root = _committed_shelf_project(tmp_path)
    _git(root, "config", "core.bare", "true")
    with pytest.raises(MapError, match="must be run in a work tree"):
        git_common_directory(root)
    capsys.readouterr()
    for command in (["status"], ["map", "check", "--strict"]):
        assert main([*command, "--root", str(root)]) == 2, command
        assert "must be run in a work tree" in capsys.readouterr().err, command


@pytest.mark.skipif(os.name == "nt", reason="a POSIX shell script stands in for a failing git")
def test_a_failing_git_listing_stops_status_and_staging_with_gits_own_message(tmp_path, monkeypatch):
    """The disposable-index reader raises with Git's own message, never Python's exit-status sentence."""
    from flowguard.map import records
    from flowguard.map.impact_history import read_git_paths
    from flowguard.map.target import _staging_paths
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    _git(root, "tag", "v1.0.0")
    _failing_git(tmp_path, monkeypatch, "ls-tree")
    with pytest.raises(MapError, match="git ls-tree failed in .*simulated ls-tree failure"):
        records.since_release(root, [], read_git_paths)
    monkeypatch.undo()
    _failing_git(tmp_path, monkeypatch, "--cached")
    with pytest.raises(MapError, match="cannot list the files to stage: git ls-files failed in .*simulated --cached failure"):
        _staging_paths(root, {"components": []}, {}, set())


def test_a_damaged_target_base_is_named_by_target_check_and_status(tmp_path, capsys):
    """A base.json that does not parse is that error, never a target started at HEAD."""
    from flowguard.__main__ import main
    root = _committed_shelf_project(tmp_path)
    assert main(["target", "start", "change loans", "--root", str(root)]) == 0
    base = root / ".flowguard/target/base.json"
    base.write_text("{", encoding="utf-8")
    capsys.readouterr()
    for command in (["target", "check"], ["status"]):
        assert main([*command, "--root", str(root)]) == 2, command
        errors = capsys.readouterr().err
        assert "target_base_invalid" in errors and str(base) in errors, (command, errors)

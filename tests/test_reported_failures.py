"""A failure FlowGuard cannot answer around is reported as that failure, never read as an absent or unknown state."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import types
from pathlib import Path

import pytest

from flowguard.map.mapfile import MapError


def _git(root, *args):
    return subprocess.run(["git", "-c", "user.name=probe", "-c", "user.email=probe@example.invalid",
                           "-C", str(root), *args], check=True, capture_output=True).stdout


def _plain_folder_request(tmp_path):
    from flowguard.map.requests import store_request
    root = tmp_path / "plain"
    (root / ".flowguard").mkdir(parents=True)
    store_request(root, b"Keep the limit at 3.\n", identifier="R1")
    return root


def _broken_index_repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    (root / ".git/index").write_bytes(b"DIRCgarbage")
    return root


# records: the release snapshot, the Git executable, before-images, change records, the release boundary

def test_an_invalid_release_snapshot_is_one_error_not_edited_requests(tmp_path):
    from flowguard.map import records
    from flowguard.map.requests import request_findings
    root = _plain_folder_request(tmp_path)
    records.save_release_snapshot(root)
    (root / ".flowguard/release-base/records.json").write_text("{", encoding="utf-8")
    with pytest.raises(MapError, match="release_snapshot_invalid"):
        request_findings(root)
    with pytest.raises(MapError, match="release_snapshot_invalid"):
        records.record_findings(root)


def test_a_missing_git_executable_is_an_error_not_a_copy_without_git(tmp_path, monkeypatch):
    from flowguard.map.requests import request_findings, store_request
    root = tmp_path / "repo"
    (root / ".flowguard").mkdir(parents=True)
    _git(root, "init", "-q")
    store_request(root, b"Keep the limit at 3.\n", identifier="R1")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "r1")
    monkeypatch.setenv("PATH", str(tmp_path / "no-bin"))
    with pytest.raises(MapError, match="git executable not found"):
        request_findings(root)


def test_a_before_image_that_does_not_parse_is_named_as_unknown(tmp_path):
    from flowguard.map.records import _diff_provenance
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "a.py").write_text("def f(:\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    base = _git(root, "rev-parse", "HEAD").decode().strip()
    (root / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    implemented, _, note = _diff_provenance(root, {"git": base}, {}, ["a.py"])
    assert implemented == [] and "Unknown function identities: a.py" in note, note


def test_an_unreadable_change_record_is_named_by_status_and_blocks_the_snapshot(tmp_path):
    from flowguard import __version__
    from flowguard.map import records, status
    from flowguard.map.impact_history import read_git_paths
    root = _plain_folder_request(tmp_path)
    records.write_once(root, ".flowguard/changes/20261101-0000-abcdef.json", b"{}")
    screen = status.render_status(status.collect_status(root, read_git_paths=read_git_paths, version=__version__))
    assert "change record 20261101-0000-abcdef unreadable" in screen, screen
    with pytest.raises(MapError, match="20261101-0000-abcdef"):
        records.save_release_snapshot(root)


def test_a_damaged_release_boundary_names_its_cause(tmp_path):
    from flowguard.map import records
    from flowguard.map.impact_history import read_git_paths
    root = _plain_folder_request(tmp_path)
    records.save_release_snapshot(root)
    (root / ".flowguard/release-base/covered.json").write_text("[]", encoding="utf-8")
    history = records.since_release(root, records.change_records(root), read_git_paths)
    assert history["changes"] is None and "covered.json" in history["known_from"], history["known_from"]


def test_record_and_sidecar_validators_name_every_malformed_shape(tmp_path):
    from flowguard.map.records import _change_record
    from flowguard.map.requests import _metadata
    sidecar = tmp_path / "R1.json"
    base = {"id": "R1", "kind": "request", "sha256": "0" * 64, "bytes": 3}
    for broken in (base, {**base, "received": 7}):
        sidecar.write_text(json.dumps(broken), encoding="utf-8")
        with pytest.raises(ValueError):
            _metadata(sidecar, "R1")
    root = tmp_path / "plain"
    record = root / ".flowguard/changes/20261101-0000-abcdef.json"
    record.parent.mkdir(parents=True)
    item = dict(kind="change", goal="g", requests=[], base=None, tree="0" * 64, checked="c",
                plan=[], rules=[], acceptances=[], existing_cleared=[], implemented_by=[], new_actions=[],
                corrections=[])
    from flowguard.map.records import write_once
    write_once(root, record.relative_to(root), json.dumps(item).encode())
    with pytest.raises(ValueError):
        _change_record(root, "20261101-0000-abcdef", set())


def test_a_programming_error_while_reading_owner_words_is_not_shown_as_invalid(tmp_path, monkeypatch):
    from flowguard.map import requests
    root = _plain_folder_request(tmp_path)
    def broken(path, identifier):
        raise KeyError("injected")
    monkeypatch.setattr(requests, "_metadata", broken)
    with pytest.raises(KeyError, match="injected"):
        requests.owner_words(root, records=[])


# Git: decided once; a failing Git in a Git repository is an error with Git's own message

def test_status_reports_a_failing_git_instead_of_no_git(tmp_path):
    from flowguard.map.status import _git_header
    from flowguard.map.impact_history import read_git_paths
    root = _broken_index_repo(tmp_path)
    with pytest.raises(MapError, match="index"):
        _git_header(root, read_git_paths, [])


def test_target_seam_reports_a_failing_git_instead_of_no_git(tmp_path):
    from flowguard.map.targetfile import target_seam
    root = _broken_index_repo(tmp_path)
    with pytest.raises(MapError, match="index"):
        target_seam(root, {"components": [], "flows": []})


def test_commit_citations_in_a_repository_without_commits_are_known_to_be_none(tmp_path):
    from flowguard.map.requests import request_citations
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    assert request_citations(root, []) == ({}, True)


# the legacy target route

def test_an_invalid_target_map_fails_map_check(tmp_path, capsys):
    from flowguard.__main__ import main
    root = tmp_path / "p"
    (root / ".flowguard/target").mkdir(parents=True)
    (root / ".flowguard/map.json").write_text(json.dumps({"schema": "flowguard.map.v1", "components": [], "flows": []}),
                                              encoding="utf-8")
    (root / ".flowguard/target/map.json").write_text("{", encoding="utf-8")
    code = main(["map", "check", "--strict", "--root", str(root)])
    output = capsys.readouterr().out
    assert code == 1 and "target_invalid" in output, output


def test_a_damaged_or_older_target_base_says_to_restart_the_target(tmp_path):
    from flowguard.map.targetfile import target_helper_baseline
    base = tmp_path / ".flowguard/target/base.json"
    base.parent.mkdir(parents=True)
    for text in ("{", json.dumps({"schema": "older", "started": "2026-01-01T00:00:00+00:00"})):
        base.write_text(text, encoding="utf-8")
        with pytest.raises(MapError, match="restart the target"):
            target_helper_baseline(tmp_path)


def test_touch_problems_carry_their_cause(tmp_path):
    from flowguard.map.plan import _touch_problem
    problem = _touch_problem(tmp_path, "../outside.py", "f")
    assert "outside.py" in problem, problem


def test_a_malformed_stored_glossary_stops_the_lookup_with_its_error(tmp_path):
    from flowguard.map.plan import _glossaries
    (tmp_path / ".flowguard/requests").mkdir(parents=True)
    (tmp_path / ".flowguard/requests/G1.json").write_text("{", encoding="utf-8")
    with pytest.raises(MapError, match="G1"):
        _glossaries(tmp_path)


def test_a_model_whose_rules_cannot_be_read_is_named(tmp_path, monkeypatch):
    from flowguard.map import plan
    entry = types.SimpleNamespace(kind="contract", path=".flowguard/models/m.py", id="m")
    monkeypatch.setattr(plan, "model_registry", lambda root, data, view=None: types.SimpleNamespace(entries=[entry]))
    monkeypatch.setattr(plan, "resolve_model_path", lambda root, path, view=None: tmp_path / "m.py")
    (tmp_path / "m.py").write_text("x = 1\n", encoding="utf-8")
    def broken(*args, **kwargs):
        raise SyntaxError("injected: rules unreadable")
    monkeypatch.setattr(plan, "StaticModel", broken)
    result = plan.rule_info(tmp_path, types.SimpleNamespace(models={"m.py"}), None, current_data={}, only_target=False)
    assert "injected" in json.dumps(result, default=str), result


# other owners: debts, where, model runs, text rules, the child import shim

def test_a_malformed_pyproject_is_named_not_read_as_no_version(tmp_path):
    from flowguard.map.debts import evaluate_debts
    (tmp_path / "pyproject.toml").write_text("[project\nversion = \n", encoding="utf-8")
    data = {"accepted_debts": [{"code": "x", "component": "*", "reason": "r", "expires": "v1.0.0"}]}
    with pytest.raises(MapError, match="pyproject.toml"):
        evaluate_debts(tmp_path, data)


def test_an_impossible_debt_date_says_so(tmp_path):
    from flowguard.map.debts import evaluate_debts
    data = {"accepted_debts": [{"code": "x", "component": "*", "reason": "r", "expires": "2026-02-30"}]}
    state = evaluate_debts(tmp_path, data).states[0]
    assert state.status == "invalid" and "2026-02-30" in state.detail, state


def test_where_stops_on_an_invalid_map(tmp_path):
    from flowguard.map.derived import where
    (tmp_path / ".flowguard").mkdir()
    (tmp_path / ".flowguard/map.json").write_text("{", encoding="utf-8")
    (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    with pytest.raises(MapError):
        where(tmp_path)


def test_a_before_image_that_does_not_parse_is_the_stated_reason(tmp_path):
    from flowguard.map.derived import _changed_since
    root = tmp_path / "repo"
    (root / ".flowguard/changes").mkdir(parents=True)
    _git(root, "init", "-q")
    (root / "a.py").write_text("def f(:\n", encoding="utf-8")
    (root / ".flowguard/changes/R.json").write_text("{}", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    (root / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    state = _changed_since(root, "R", {"path": "a.py", "function": "f"}, {})
    assert state["state"] == "unknown" and "does not parse" in state["reason"], state


def test_model_runs_stop_on_an_invalid_map(tmp_path):
    from flowguard.map.proof import ModelResult, run_bound_tests, run_model
    (tmp_path / ".flowguard/models").mkdir(parents=True)
    (tmp_path / ".flowguard/map.json").write_text("{", encoding="utf-8")
    (tmp_path / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_a.py").write_text("from a import f\n\ndef test_a():\n    assert f() == 1\n", encoding="utf-8")
    model = tmp_path / ".flowguard/models/m.py"
    model.write_text('MODEL_ID = "m"\nIMPLEMENTED_BY = {"A": "a.py:f"}\nTESTED_BY = {"a_holds": ["tests/test_a.py:test_a"]}\n',
                     encoding="utf-8")
    with pytest.raises(MapError):
        run_model(tmp_path, model, timeout=20)
    result = ModelResult("m", model.relative_to(tmp_path).as_posix())
    run_bound_tests(tmp_path, model, result, timeout=60)
    assert result.status == "error" and any("not valid JSON" in problem for problem in result.problems), result


def test_an_unsplittable_argparse_program_is_an_unknown_entry():
    from flowguard.map.textrules import _commands
    raw = {"files": {"cli.py": {"entrypoints": [{"via": "argparse", "parser_symbol": "p", "name": "run", "line": 3}]}}}
    unknown = []
    assert _commands(raw, {"cli.py": {"p": {"tool 'x"}}}, unknown) == {}
    assert unknown and unknown[0]["path"] == "cli.py" and "tool 'x" in unknown[0]["reason"], unknown


def test_the_child_package_shim_is_one_route_and_a_refused_link_is_an_error(monkeypatch):
    from flowguard.map import common
    monkeypatch.setenv("PYTHONPATH", "")
    monkeypatch.setattr(common, "_CHILD_PACKAGE_DIRECTORY", None)
    shim = Path(common._child_package_import_root()) / "flowguard"
    assert shim.is_symlink() and shim.resolve() == Path(common.__file__).resolve().parents[1]
    monkeypatch.setattr(common, "_CHILD_PACKAGE_DIRECTORY", None)
    def refused(self, *args, **kwargs):
        raise OSError(1, "Operation not permitted")
    monkeypatch.setattr(Path, "symlink_to", refused)
    with pytest.raises(MapError, match="Operation not permitted"):
        common._child_package_import_root()


# Git failing inside a Git repository stops the integrity check with Git's own message

RECORD = "20261101-0000-abcdef"
RECORD_ITEM = dict(kind="change", goal="g", requests=[], base=None, tree="0" * 64, checked="c",
                   promoted="2026-11-01T00:00:00+00:00", plan=[], rules=[], acceptances=[], existing_cleared=[],
                   implemented_by=[], new_actions=[], corrections=[])


def _failing_git(tmp_path, monkeypatch, subcommand):
    """Put a git first on PATH that fails one subcommand with its own message and runs the real Git otherwise."""
    import shutil
    real = shutil.which("git")
    directory = tmp_path / f"failing-{subcommand}-bin"
    directory.mkdir()
    script = directory / "git"
    script.write_text(f'#!/bin/sh\nfor argument in "$@"; do\n  if [ "$argument" = "{subcommand}" ]; then\n'
                      f'    echo "fatal: simulated {subcommand} failure" >&2\n    exit 128\n  fi\ndone\n'
                      f'exec {shlex.quote(real)} "$@"\n', encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}{os.environ['PATH']}")


def _write_record(root):
    from flowguard.map import records
    records.prepare_directory(root, records.CHANGE_DIR, (".json",))
    records.write_once(root, records.CHANGE_DIR / (RECORD + ".json"), json.dumps(RECORD_ITEM).encode())
    return root / records.CHANGE_DIR / (RECORD + ".json")


def _edit_one_byte(path):
    raw = path.read_bytes()
    path.write_bytes(raw.replace(b'"g"', b'"h"', 1) if b'"g"' in raw else raw.replace(b"3", b"4", 1))


@pytest.mark.skipif(os.name == "nt", reason="a POSIX shell script stands in for a failing git")
@pytest.mark.parametrize("checkout", ["fresh_clone", "original"])
def test_a_failing_git_log_stops_the_record_check_instead_of_reading_no_history(tmp_path, monkeypatch, checkout):
    from flowguard.map.records import record_findings
    origin = tmp_path / "origin"
    origin.mkdir()
    _git(origin, "init", "-q")
    _write_record(origin)
    _git(origin, "add", "-A")
    _git(origin, "commit", "-qm", "record")
    root = origin
    if checkout == "fresh_clone":
        root = tmp_path / "clone"
        subprocess.run(["git", "clone", "-q", str(origin), str(root)], check=True, capture_output=True)
    _edit_one_byte(root / ".flowguard/changes" / (RECORD + ".json"))
    _failing_git(tmp_path, monkeypatch, "log")
    with pytest.raises(MapError, match="simulated log failure"):
        record_findings(root)


@pytest.mark.skipif(os.name == "nt", reason="a POSIX shell script stands in for a failing git")
def test_a_failing_git_listing_stops_the_request_check_instead_of_reading_no_files(tmp_path, monkeypatch):
    from flowguard.map.requests import request_findings, store_request
    root = tmp_path / "repo"
    (root / ".flowguard").mkdir(parents=True)
    _git(root, "init", "-q")
    store_request(root, b"Keep the limit at 3.\n", identifier="R1")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "r1")
    _failing_git(tmp_path, monkeypatch, "ls-files")
    with pytest.raises(MapError, match="simulated ls-files failure"):
        request_findings(root)


@pytest.mark.skipif(os.name == "nt", reason="a POSIX shell script stands in for a failing git")
def test_a_failing_git_describe_stops_the_release_boundary_instead_of_reading_no_tag(tmp_path, monkeypatch):
    from flowguard.map import records
    from flowguard.map.impact_history import read_git_paths
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    _git(root, "tag", "v1.0.0")
    _failing_git(tmp_path, monkeypatch, "describe")
    with pytest.raises(MapError, match="simulated describe failure"):
        records.since_release(root, [], read_git_paths)


@pytest.mark.skipif(os.name == "nt", reason="a POSIX shell script stands in for a failing git")
def test_a_failing_git_log_stops_the_where_change_view_instead_of_reading_no_history(tmp_path, monkeypatch):
    from flowguard.map.derived import _changed_since
    root = tmp_path / "repo"
    (root / ".flowguard/changes").mkdir(parents=True)
    _git(root, "init", "-q")
    (root / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    (root / ".flowguard/changes/R.json").write_text("{}", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    _failing_git(tmp_path, monkeypatch, "log")
    with pytest.raises(MapError, match="simulated log failure"):
        _changed_since(root, "R", {"path": "a.py", "function": "f"}, {})


@pytest.mark.parametrize("kind", ["request", "record"])
def test_fix_advice_in_a_folder_without_git_suggests_no_git_command(tmp_path, kind):
    from flowguard.map.records import record_findings
    from flowguard.map.requests import request_findings
    root = _plain_folder_request(tmp_path)
    if kind == "request":
        _edit_one_byte(root / ".flowguard/requests/R1.md")
        findings = request_findings(root)
    else:
        _edit_one_byte(_write_record(root))
        findings = record_findings(root)
    errors = [finding.message for finding in findings if finding.level == "error"]
    assert errors, findings
    for message in errors:
        assert "git -C" not in message and "checkout --" not in message, message


@pytest.mark.skipif(os.name == "nt", reason="a POSIX shell script stands in for a failing git")
def test_a_failing_git_stops_target_start_instead_of_recording_a_folder_base(tmp_path, monkeypatch):
    from flowguard.map import target as native
    root = tmp_path / "repo"
    (root / ".flowguard").mkdir(parents=True)
    (root / ".flowguard/map.json").write_text(json.dumps({"schema": "flowguard.map.v1", "components": [], "flows": []}),
                                              encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    _failing_git(tmp_path, monkeypatch, "--verify")
    with pytest.raises(MapError, match="simulated --verify failure"):
        native.start_target(root, "change something")
    assert not (root / ".flowguard/target/base.json").exists()


@pytest.mark.skipif(os.name == "nt", reason="a POSIX shell script stands in for a failing git")
def test_a_failing_git_stops_promote_instead_of_giving_no_git_advice(tmp_path, capsys, monkeypatch):
    from flowguard.map import target as native
    from _fg_helpers import target__target_life_cycle_fixture_helpers as helpers_of
    helpers = helpers_of("target_findings")
    root = helpers["make_project"](tmp_path / "project")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    helpers["stage_target"](root)
    before = (root / ".flowguard/map.json").read_bytes()
    _failing_git(tmp_path, monkeypatch, "--is-inside-work-tree")
    code = native.promote_target(root)
    captured = capsys.readouterr()
    assert code == 2 and "simulated --is-inside-work-tree failure" in captured.err, (captured.out, captured.err)
    assert (root / ".flowguard/target").exists() and (root / ".flowguard/map.json").read_bytes() == before


@pytest.mark.skipif(os.name == "nt", reason="a POSIX shell script stands in for a failing git")
def test_a_failing_git_diff_stops_change_selection_instead_of_the_no_git_route(tmp_path, monkeypatch):
    from flowguard.map.impact import changed_files
    root = tmp_path / "repo"
    (root / ".flowguard").mkdir(parents=True)
    (root / ".flowguard/map.json").write_text(json.dumps({"schema": "flowguard.map.v1", "components": [], "flows": []}),
                                              encoding="utf-8")
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    _failing_git(tmp_path, monkeypatch, "diff")
    with pytest.raises(MapError, match="simulated diff failure"):
        changed_files(root, "HEAD")


# Git that fails inside a repository is never read as "no Git", "before the first commit" or "no origin"

def test_a_repository_git_refuses_to_open_is_an_error_not_a_folder_without_git(tmp_path, monkeypatch, capsys):
    """Git exits 128 both outside any repository and for a repository it refuses (dubious ownership)."""
    from flowguard.__main__ import main
    from flowguard.map.common import git_common_directory
    from flowguard.map.requests import store_request
    root = tmp_path / "repo"
    (root / ".flowguard").mkdir(parents=True)
    (root / ".flowguard/map.json").write_text(json.dumps({"schema": "flowguard.map.v1", "components": [], "flows": []}),
                                              encoding="utf-8")
    (root / "pkg").mkdir()
    _git(root, "init", "-q")
    store_request(root, b"Keep the limit at 3.\n", identifier="R1")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "r1")
    plain = tmp_path / "plain"
    plain.mkdir()
    monkeypatch.setenv("GIT_TEST_ASSUME_DIFFERENT_OWNER", "1")  # Git's own switch for a repository owned by another user
    for place in (root, root / "pkg"):
        with pytest.raises(MapError, match="dubious ownership"):
            git_common_directory(place)
    assert git_common_directory(plain) is None
    for command in (["status"], ["map", "check", "--strict"]):
        assert main([*command, "--root", str(root)]) == 2, command
        assert "dubious ownership" in capsys.readouterr().err, command
    before = sorted(path.name for path in (root / ".flowguard/requests").iterdir())
    source = tmp_path / "words.md"
    source.write_text("Keep the limit at 4.\n", encoding="utf-8")
    assert main(["req", "add", str(source), "--id", "R2", "--root", str(root)]) == 2
    assert "dubious ownership" in capsys.readouterr().err
    assert sorted(path.name for path in (root / ".flowguard/requests").iterdir()) == before


def test_a_broken_branch_is_an_error_not_a_repository_before_its_first_commit(tmp_path, capsys):
    from flowguard.__main__ import main
    from flowguard.map.common import git_head
    unborn = tmp_path / "unborn"
    unborn.mkdir()
    _git(unborn, "init", "-q")
    assert git_head(unborn) is None
    root = tmp_path / "repo"
    (root / ".flowguard").mkdir(parents=True)
    (root / ".flowguard/map.json").write_text(json.dumps({"schema": "flowguard.map.v1", "components": [], "flows": []}),
                                              encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    branch = _git(root, "symbolic-ref", "HEAD").decode().strip()
    (root / ".git" / branch).write_text("zzzz\n", encoding="ascii")
    with pytest.raises(MapError, match="broken"):
        git_head(root)
    for command in (["map", "check", "--strict"], ["release"], ["where", "anything"]):
        assert main([*command, "--root", str(root)]) == 2, command
        assert "broken" in capsys.readouterr().err, command


@pytest.mark.skipif(os.name == "nt", reason="a POSIX shell script stands in for a failing git")
def test_a_failing_git_blame_stops_the_text_origin_instead_of_reading_no_origin(tmp_path, monkeypatch):
    from flowguard.map import textrules
    root = tmp_path / "repo"
    (root / ".flowguard").mkdir(parents=True)
    (root / ".flowguard/map.json").write_text(json.dumps({"schema": "flowguard.map.v1", "components": [], "flows": []}),
                                              encoding="utf-8")
    (root / "NOTES.md").write_text("# Notes\n\nThe shelf must keep `limit_respected` true.\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "base")
    (root / "NEW.md").write_text("# New\n\nThe new page names `limit_respected` too.\n", encoding="utf-8")
    result = textrules.report(root)
    committed, = [row for row in result["texts"] if row["path"] == "NOTES.md" and "limit_respected" in row["text"]]
    uncommitted, = [row for row in result["texts"] if row["path"] == "NEW.md" and "limit_respected" in row["text"]]
    chosen, = textrules.select(result, "source:" + committed["id"])["texts"]
    assert chosen["provenance"]["state"] == "git", chosen
    chosen, = textrules.select(result, "source:" + uncommitted["id"])["texts"]
    assert chosen["provenance"]["state"] == "unknown", chosen  # a file no commit holds has no Git origin
    _failing_git(tmp_path, monkeypatch, "blame")
    with pytest.raises(MapError, match="simulated blame failure"):
        textrules.select(result, "source:" + committed["id"])


@pytest.mark.skipif(os.name == "nt", reason="a POSIX shell script stands in for a failing git")
def test_a_failing_git_listing_stops_the_inventory_instead_of_walking_the_folder(tmp_path, monkeypatch):
    from flowguard.map.inventory import list_files
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    (root / ".gitignore").write_text("build/\n", encoding="utf-8")
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    (root / "build").mkdir()
    (root / "build/generated.py").write_text("y = 2\n", encoding="utf-8")
    assert list_files(root) == [".gitignore", "a.py"]
    _failing_git(tmp_path, monkeypatch, "ls-files")
    with pytest.raises(MapError, match="simulated ls-files failure"):
        list_files(root)


def test_a_folder_outside_any_repository_needs_no_git_executable(tmp_path, monkeypatch, capsys):
    from flowguard.__main__ import main
    root = tmp_path / "plain"
    (root / ".flowguard").mkdir(parents=True)
    (root / ".flowguard/map.json").write_text(json.dumps({"schema": "flowguard.map.v1", "components": [], "flows": []}),
                                              encoding="utf-8")
    (root / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path / "no-bin"))
    for command in (["status"], ["map", "check", "--strict"], ["where", "f"]):
        assert main([*command, "--root", str(root)]) == 0, (command, capsys.readouterr())
        assert "git executable not found" not in capsys.readouterr().err, command


def test_a_folder_inside_the_git_directory_is_a_folder_without_git(tmp_path):
    """A cache under .git/ has no work tree: Git says so, and its files are walked instead of listed by Git."""
    from flowguard.map.common import git_common_directory
    from flowguard.map.inventory import list_files
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    cache = root / ".git/flowguard/cache/snapshot"
    (cache / "src").mkdir(parents=True)
    (cache / "src/program.py").write_text("x = 1\n", encoding="utf-8")
    assert git_common_directory(root) == (root / ".git").resolve()
    assert git_common_directory(cache) is None
    assert list_files(cache) == ["src/program.py"]


# Git old text: an object Git cannot read is that failure, never a file that did not exist at the base

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

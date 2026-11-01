"""Status shows the owner's newest words; planner text is retired once; the first command of a session shows status."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from test_requests import _call, _git, _plan_target, _project

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/flowguard"


def _words(root, capsys, *texts):
    for number, text in enumerate(texts, 1):
        source = root.parent / f"owner-{number}.md"
        source.write_text(text, encoding="utf-8")
        code, output, errors = _call(root, capsys, "req", "add", str(source), "--id", f"R{number}")
        assert code == 0 and not errors, (output, errors)


def _plain(tmp_path, name="project"):
    root = tmp_path / name
    (root / ".flowguard").mkdir(parents=True)
    return root


def _owner_lines(output):
    lines = output.splitlines()
    start = next(index for index, line in enumerate(lines) if line.startswith("OWNER WORDS"))
    rows = []
    for line in lines[start + 1:]:
        if not line.startswith("  "):
            break
        rows.append(line.strip())
    return lines[start], rows


def test_status_lists_the_newest_owner_words_first_without_a_to_do_state(tmp_path, capsys):
    root = _plain(tmp_path)
    _words(root, capsys, "First words.\n", "Second words.\n", "Third words.\nwith a detail\nand another\n",
           "Fourth words.\n", "Fifth words.\n")
    code, output, errors = _call(root, capsys, "status")
    assert code == 0 and not errors, errors
    assert "open since" not in output and "REQUEST " not in output and " done " not in output, output
    header, rows = _owner_lines(output)
    assert "newest first" in header and "commit links unknown (no Git history)" in header, header
    assert [row.split(" ", 1)[0] for row in rows[:3]] == ["R5", "R4", "R3"], rows
    assert rows[0].endswith(": Fifth words.") and rows[2].endswith(": Third words. (+2 lines)"), rows
    assert rows[3] == "older: R2, R1 (python -m flowguard where R2)", rows


def test_req_add_supersedes_names_the_replaced_words(tmp_path, capsys):
    root = _plain(tmp_path)
    _words(root, capsys, "Carts hold ten items.\n")
    source = tmp_path / "new.md"
    source.write_text("Carts hold twelve items.\n", encoding="utf-8")
    code, output, errors = _call(root, capsys, "req", "add", str(source), "--id", "R2", "--supersedes", "R1")
    assert code == 0 and not errors and "supersedes R1" in output, (output, errors)
    assert json.loads((root / ".flowguard/requests/R2.json").read_bytes())["supersedes"] == ["R1"]
    _, rows = _owner_lines(_call(root, capsys, "status")[1])
    assert rows[0].startswith("R2 ") and rows[0].endswith(": Carts hold twelve items."), rows
    assert rows[1].startswith("R1 ") and rows[1].endswith(": superseded by R2"), rows
    code, _, errors = _call(root, capsys, "req", "add", str(source), "--id", "R3", "--supersedes", "R9")
    assert code == 2 and "request_unknown: R9" in errors
    assert not (root / ".flowguard/requests/R3.md").exists()


def test_req_retire_records_once_that_a_text_is_not_the_owners_words(tmp_path, capsys):
    root = _plain(tmp_path)
    _words(root, capsys, "1. Add a cache\n2. Split the module\n", "Make the cart faster.\n")
    original = (root / ".flowguard/requests/R1.md").read_bytes()
    code, output, errors = _call(root, capsys, "req", "retire", "R1", "--not-owner", "--note", "a plan an AI wrote")
    assert code == 0 and not errors and output.startswith("retired R1: not the owner's words"), (output, errors)
    record = json.loads((root / ".flowguard/requests/retired/R1.json").read_bytes())
    sidecar = json.loads((root / ".flowguard/requests/R1.json").read_bytes())
    assert record["id"] == "R1" and record["kind"] == "retired" and record["not_owner"] is True
    assert record["request_sha256"] == sidecar["sha256"] and record["note"] == "a plan an AI wrote"
    assert (root / ".flowguard/requests/R1.md").read_bytes() == original
    code, output, _ = _call(root, capsys, "status")
    _, rows = _owner_lines(output)
    assert [row.split(" ", 1)[0] for row in rows] == ["R2"] and "Add a cache" not in output, output
    assert "RETIRED (not the owner's words): R1" in output
    code, _, errors = _call(root, capsys, "req", "retire", "R1", "--not-owner")
    assert code == 2 and "already retired" in errors
    with pytest.raises(SystemExit) as stopped:
        _call(root, capsys, "req", "retire", "R2")
    assert stopped.value.code == 2 and "--not-owner" in capsys.readouterr().err
    assert not (root / ".flowguard/requests/retired/R2.json").exists()
    code, output, _ = _call(root, capsys, "where", "R1")
    assert "request R1: retired: not the owner's words" in output, output


def test_retired_text_cannot_be_quoted_linked_or_superseded(tmp_path, capsys):
    from flowguard.map.plan import check_plan
    planned = tmp_path / "planned"
    target, view = _plan_target(planned)
    assert _call(planned, capsys, "req", "retire", "RQuote", "--not-owner")[0] == 0
    (planned / ".flowguard/target/PLAN.txt").write_text(
        'changes: renew_limit.renew_within_limit by RQuote "Renewals keep the limit 3."\n', encoding="utf-8")
    _, findings = check_plan(planned, target, view)
    assert [item.code for item in findings] == ["request_retired"], findings
    assert "quote or link the owner's own words" in findings[0].message
    source = tmp_path / "replacement.md"
    source.write_text("The owner's own replacement.\n", encoding="utf-8")
    code, _, errors = _call(planned, capsys, "req", "add", str(source), "--id", "R2", "--supersedes", "RQuote")
    assert code == 2 and "request_retired: RQuote" in errors
    project = _project(tmp_path / "shelf", capsys)
    _words(project, capsys, "planner list\n")
    assert _call(project, capsys, "req", "retire", "R1", "--not-owner")[0] == 0
    code, _, errors = _call(project, capsys, "target", "start", "use it", "--request", "R1")
    assert code == 2 and "request_retired: R1" in errors
    assert not (project / ".flowguard/target").exists()


def test_an_edited_retire_record_is_an_error(tmp_path, capsys):
    from flowguard.map.requests import request_findings, retired_requests
    root = _plain(tmp_path)
    _words(root, capsys, "planner list\n")
    assert _call(root, capsys, "req", "retire", "R1", "--not-owner")[0] == 0
    assert request_findings(root) == [] and set(retired_requests(root)) == {"R1"}
    path = root / ".flowguard/requests/retired/R1.json"
    path.write_bytes(path.read_bytes().replace(b'"not_owner": true', b'"not_owner": false'))
    assert [item.code for item in request_findings(root)] == ["request_retire_edited"]
    assert list(retired_requests(root)) == ["R1"] and "immutable file bytes changed" in retired_requests(root)["R1"]


def test_a_retire_record_in_a_copy_without_git_is_unverifiable_not_edited(tmp_path, capsys):
    import shutil
    from flowguard.map.requests import request_findings, retired_requests
    root = _plain(tmp_path)
    _words(root, capsys, "planner list\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "stored words")
    assert _call(root, capsys, "req", "retire", "R1", "--not-owner")[0] == 0
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "retire")
    copy = tmp_path / "copy"
    shutil.copytree(root, copy, ignore=shutil.ignore_patterns(".git"))
    findings = request_findings(copy)
    assert [(item.level, item.code) for item in findings] == [("info", "immutable_unverified")], findings
    assert list(retired_requests(copy)) == ["R1"] and "cannot be checked here" in retired_requests(copy)["R1"]
    code, _, errors = _call(copy, capsys, "req", "add", str(tmp_path / "owner-1.md"), "--id", "R2", "--supersedes", "R1")
    assert code == 2 and "request_retired: R1" in errors, errors


def test_retired_before_the_release_tag_drops_off_the_screen(tmp_path, capsys):
    root = _plain(tmp_path)
    _words(root, capsys, "planner list one\n", "planner list two\n", "Owner words.\n")
    _git(root, "init", "-q")
    # After git init, stored words are checked against their first commit, so commit them before retiring.
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "stored words")
    assert _call(root, capsys, "req", "retire", "R1", "--not-owner")[0] == 0
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "seed")
    _git(root, "tag", "v0.1.0")
    assert _call(root, capsys, "req", "retire", "R2", "--not-owner")[0] == 0
    output = _call(root, capsys, "status")[1]
    assert "RETIRED (not the owner's words): R2" in output and "R1" not in output, output


def test_a_commit_request_line_is_shown_as_a_citation(tmp_path, capsys):
    root = _plain(tmp_path)
    _words(root, capsys, "Keep receipts.\n", "Print receipts in bold.\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "Print receipts in bold\n\nRequest: R2")
    commit = _git(root, "rev-parse", "--short=7", "HEAD").decode().strip()
    header, rows = _owner_lines(_call(root, capsys, "status")[1])
    assert "commit links unknown" not in header
    assert rows[0].startswith("R2 ") and rows[0].endswith(f"cited by: commit {commit}"), rows
    assert "cited by" not in rows[1], rows


def test_read_shows_no_request_state(tmp_path, capsys):
    root = _project(tmp_path / "project", capsys)
    _words(root, capsys, "Keep the shelf small.\n")
    code, output, _ = _call(root, capsys, "read")
    assert code == 0 and "requests:" not in output and "open since" not in output, output


@pytest.mark.parametrize("pin, expected", [
    ("v0.1.0", "is for v0.1.0; FlowGuard here is"),
    (None, "names no version; FlowGuard here is"),
    ("v99.0.0", "ask the owner to install FlowGuard v99.0.0"),
    ("current", None),
])
def test_status_warns_when_the_installed_skill_text_is_another_version(tmp_path, capsys, monkeypatch, pin, expected):
    from flowguard import __version__
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("CODEX_HOME", raising=False)
    root = _plain(tmp_path)
    assert not [line for line in _call(root, capsys, "status")[1].splitlines() if "installed skill" in line]
    tag = "v" + __version__ if pin == "current" else pin
    skill = home / ".claude/skills/flowguard/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("Install FlowGuard only from git+https://github.com/liuyingxuvka/FlowGuard.git"
                     + (f"@{tag}" if tag else "@<tag>") + ".\n", encoding="utf-8")
    warnings = [line for line in _call(root, capsys, "status")[1].splitlines() if "installed skill" in line]
    if expected is None:
        assert warnings == []
    else:
        assert len(warnings) == 1 and warnings[0].startswith(f"WARNING installed skill text {skill}"), warnings
        assert expected in warnings[0], warnings
    codex = tmp_path / "codex"
    monkeypatch.setenv("CODEX_HOME", str(codex))
    (codex / "skills/flowguard").mkdir(parents=True)
    (codex / "skills/flowguard/SKILL.md").write_text("no pin here\n", encoding="utf-8")
    output = _call(root, capsys, "status")[1]
    assert f"WARNING installed skill text {codex / 'skills/flowguard/SKILL.md'} names no version" in output


def test_the_repository_skill_pins_this_package_version():
    from flowguard import __version__
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert re.findall(r"FlowGuard\.git@(v[0-9.]+)", text) == ["v" + __version__]


def test_skill_and_template_say_what_req_add_stores():
    from flowguard.templates import adoption_template_files
    rules = next(f.content for f in adoption_template_files() if f.path == "docs/flowguard_agents_rules.md")
    for name, text in (("SKILL.md", (SKILL / "SKILL.md").read_text(encoding="utf-8")), ("AGENTS template", rules),
                       ("AGENTS.md", (ROOT / "AGENTS.md").read_text(encoding="utf-8"))):
        assert "never a plan, a list or text an AI wrote" in text, name
        assert "--supersedes" in text, name
    reference = (SKILL / "references/map_format.md").read_text(encoding="utf-8")
    assert "req retire ID --not-owner" in reference


def _marker(root):
    path = root / ".flowguard/cache/status-shown.json"
    return json.loads(path.read_text()) if path.exists() else None


def test_the_first_command_of_a_session_shows_status_once(tmp_path, capsys, monkeypatch):
    root = _plain(tmp_path)
    _words(root, capsys, "Keep receipts.\n")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-a")
    code, output, errors = _call(root, capsys, "where", "R1")
    assert code == 0 and "request R1: owner words" in output and "FLOWGUARD STATUS" not in output
    assert errors.startswith("FLOWGUARD STATUS ") and "R1 " in errors, errors
    assert _marker(root)["session"] == "session-a"
    code, _, errors = _call(root, capsys, "where", "R1")
    assert code == 0 and errors == "", errors
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-b")
    assert "FLOWGUARD STATUS" in _call(root, capsys, "where", "R1")[2]
    assert _marker(root)["session"] == "session-b"
    monkeypatch.delenv("CLAUDECODE")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-c")
    assert _call(root, capsys, "where", "R1")[2] == ""
    assert _marker(root)["session"] == "session-b"


def test_status_itself_and_its_hook_mark_the_session(tmp_path, capsys, monkeypatch):
    root = _plain(tmp_path)
    code, output, _ = _call(root, capsys, "status", "--json")
    assert code == 0 and json.loads(output)["session"] is None and _marker(root) is None
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-a")
    code, output, errors = _call(root, capsys, "status", "--hook")
    assert code == 0 and output.startswith("FLOWGUARD STATUS ") and errors == ""
    assert _marker(root)["session"] == "session-a"
    assert _call(root, capsys, "where", "R1")[2] == ""
    assert json.loads(_call(root, capsys, "status", "--json")[1])["session"] == "session-a"


def test_a_status_failure_is_named_and_the_command_still_runs(tmp_path, capsys, monkeypatch):
    from flowguard.map import status
    root = _plain(tmp_path)
    _words(root, capsys, "Keep receipts.\n")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "session-a")
    def broken(*arguments, **keywords):
        raise RuntimeError("index unreadable")
    monkeypatch.setattr(status, "collect_status", broken)
    code, output, errors = _call(root, capsys, "where", "R1")
    assert code == 0 and "request R1: owner words" in output
    assert errors.startswith("flowguard: status could not be shown first (RuntimeError: index unreadable); run "
                             "python -m flowguard status --root "), errors
    assert _marker(root) is None


def test_an_agent_session_without_an_id_names_the_gap(tmp_path, capsys, monkeypatch):
    root = _plain(tmp_path)
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    code, _, errors = _call(root, capsys, "where", "R1")
    assert errors.startswith("flowguard: CLAUDECODE=1 but CLAUDE_CODE_SESSION_ID is unset; "
                             "status is not shown automatically: python -m flowguard status --root "), errors
    assert "FLOWGUARD STATUS" not in errors and _marker(root) is None


def test_children_flowguard_starts_are_not_the_agent_session():
    from flowguard.map.common import child_pytest_environment
    child = child_pytest_environment({"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": "session-a", "PATH": "/bin"})
    assert child == {"PATH": "/bin"}


def _retired_copy_without_git(tmp_path, capsys):
    import shutil
    root = _plain(tmp_path)
    _words(root, capsys, "1. a planner list\n", "The owner's own words.\n")
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "stored words")
    assert _call(root, capsys, "req", "retire", "R1", "--not-owner")[0] == 0
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "retire")
    copy = tmp_path / "copy"
    shutil.copytree(root, copy, ignore=shutil.ignore_patterns(".git"))
    return root, copy


def test_a_retire_record_applies_in_a_copy_without_git_and_status_names_it_once(tmp_path, capsys):
    _, copy = _retired_copy_without_git(tmp_path, capsys)
    code, output, _ = _call(copy, capsys, "status")
    assert code == 0
    _, rows = _owner_lines(output)
    assert [row.split(" ", 1)[0] for row in rows] == ["R2"] and "a planner list" not in output, output
    named = [line for line in output.splitlines() if "retire record" in line]
    assert len(named) == 1 and "R1" in named[0] and "cannot be checked here" in named[0], output
    from flowguard.map.requests import request_findings
    assert [(item.level, item.code) for item in request_findings(copy)] == [("info", "immutable_unverified")]


def test_an_edited_retire_record_still_hides_the_text_and_status_names_it(tmp_path, capsys):
    root, _ = _retired_copy_without_git(tmp_path, capsys)
    path = root / ".flowguard/requests/retired/R1.json"
    path.write_bytes(path.read_bytes().replace(b'"retired": "', b'"retired": " '))
    code, output, _ = _call(root, capsys, "status")
    assert code == 0
    _, rows = _owner_lines(output)
    assert [row.split(" ", 1)[0] for row in rows] == ["R2"] and "a planner list" not in output, output
    named = [line for line in output.splitlines() if "retire record" in line]
    assert len(named) == 1 and "R1" in named[0] and "edited" in named[0], output
    from flowguard.map.requests import request_findings
    assert [(item.level, item.code) for item in request_findings(root)] == [("error", "request_retire_edited")]


def test_superseded_words_beyond_the_newest_three_are_marked(tmp_path, capsys):
    root = _plain(tmp_path)
    _words(root, capsys, "First words.\n", "Second words.\n", "Third words.\n", "Fourth words.\n")
    source = tmp_path / "fifth.md"
    source.write_text("Fifth words replace the first.\n", encoding="utf-8")
    assert _call(root, capsys, "req", "add", str(source), "--id", "R5", "--supersedes", "R1")[0] == 0
    _, rows = _owner_lines(_call(root, capsys, "status")[1])
    assert rows[3] == "older: R2, R1 (superseded by R5) (python -m flowguard where R2)", rows


def test_citations_beyond_the_shown_ones_say_how_to_see_them(tmp_path, capsys):
    root = _plain(tmp_path)
    _words(root, capsys, "Keep receipts.\n")
    _git(root, "init", "-q")
    for number in range(3):
        (root / f"change{number}.txt").write_text(str(number), encoding="utf-8")
        _git(root, "add", "-A")
        _git(root, "commit", "-qm", f"Change {number}\n\nRequest: R1")
    _, rows = _owner_lines(_call(root, capsys, "status")[1])
    assert "(+" not in rows[0], rows
    assert rows[0].endswith(" and 1 more (python -m flowguard where R1)"), rows


def _agent_run(arguments, cwd, session):
    import os
    import subprocess
    import sys
    environment = {**os.environ, "CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": session,
                   "PYTHONPATH": os.pathsep.join(filter(None, [str(ROOT), os.environ.get("PYTHONPATH")]))}
    return subprocess.run([sys.executable, "-m", *arguments], cwd=cwd, env=environment, capture_output=True, text=True,
                          timeout=120)


def test_status_comes_first_for_flowguard_map_and_from_a_project_subdirectory(tmp_path, capsys):
    root = _plain(tmp_path)
    _words(root, capsys, "Keep receipts.\n")
    result = _agent_run(["flowguard.map", "check", "--root", str(root)], root, "session-map")
    assert result.stderr.startswith(f"FLOWGUARD STATUS {root.resolve()} "), result.stderr
    assert _marker(root)["session"] == "session-map"
    inner = root / "pkg" / "deep"
    inner.mkdir(parents=True)
    result = _agent_run(["flowguard", "where", "R1"], inner, "session-sub")
    assert result.stderr.startswith(f"FLOWGUARD STATUS {root.resolve()} "), result.stderr
    assert _marker(root)["session"] == "session-sub"
    assert not (inner / ".flowguard").exists()


def test_every_entry_finds_the_project_from_a_subdirectory_the_same_way(tmp_path, capsys):
    import os
    import subprocess
    import sys
    root = _plain(tmp_path)
    (root / ".flowguard/map.json").write_text(json.dumps({"schema": "flowguard.map.v1", "components": [], "flows": []}),
                                              encoding="utf-8")
    _words(root, capsys, "Keep receipts.\n")
    inner = root / "pkg" / "deep"
    inner.mkdir(parents=True)
    words = tmp_path / "later.md"
    words.write_text("Keep two receipts.\n", encoding="utf-8")
    environment = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(ROOT), os.environ.get("PYTHONPATH")]))}

    def run(*arguments):
        return subprocess.run([sys.executable, "-m", *arguments], cwd=inner, env=environment, capture_output=True,
                              text=True, timeout=120)

    result = run("flowguard", "req", "add", str(words), "--id", "R2")
    assert result.returncode == 0, result.stderr
    assert (root / ".flowguard/requests/R2.md").is_file() and not (inner / ".flowguard").exists()
    result = run("flowguard", "status")
    assert result.stdout.startswith(f"FLOWGUARD STATUS {root.resolve()} ") and "R2 " in result.stdout, result.stdout
    result = run("flowguard", "where", "R2")
    assert result.returncode == 0 and "request R2: owner words" in result.stdout, (result.stdout, result.stderr)
    for arguments in (("flowguard", "map", "check"), ("flowguard.map", "check"), ("flowguard", "target", "check")):
        result = run(*arguments)
        assert "no map at" not in result.stderr, (arguments, result.stderr)
    assert run("flowguard", "map", "check").returncode == 0
    assert not (inner / ".flowguard").exists()


def test_a_retire_record_that_cannot_be_read_is_not_called_edited(tmp_path, capsys, monkeypatch):
    from flowguard.map import requests
    root, _ = _retired_copy_without_git(tmp_path, capsys)
    def unreadable(root, identifier):
        raise PermissionError(13, "Permission denied", str(root / requests.RETIRED_DIR / (identifier + ".json")))
    monkeypatch.setattr(requests, "_retire_record", unreadable)
    problem = requests.retired_requests(root)["R1"]
    assert problem.startswith("cannot be read: ") and "edited" not in problem, problem
    named = [line for line in _call(root, capsys, "status")[1].splitlines() if "retire record" in line]
    assert len(named) == 1 and "R1 cannot be read: " in named[0], named


def test_an_unreadable_sidecar_of_a_retired_request_keeps_it_retired_and_blames_the_sidecar(tmp_path, capsys):
    """The retire record applies as written; the edited request sidecar is that sidecar's finding, not the record's."""
    from flowguard.map.requests import request_findings, retired_requests
    root, _ = _retired_copy_without_git(tmp_path, capsys)
    sidecar = root / ".flowguard/requests/R1.json"
    sidecar.write_bytes(sidecar.read_bytes().replace(b'"kind": "request"', b'"kind": "bogus"'))
    assert retired_requests(root) == {"R1": None}
    code, output, _ = _call(root, capsys, "status")
    assert code == 0
    _, rows = _owner_lines(output)
    assert [row.split(" ", 1)[0] for row in rows] == ["R2"], output
    assert "retire record" not in output, output
    assert [(item.code, item.component) for item in request_findings(root)] == [("request_meta_edited", "R1")]


def test_owner_text_edited_in_a_checkout_is_not_shown_as_the_owners_words(tmp_path, capsys):
    root, _ = _retired_copy_without_git(tmp_path, capsys)
    body = root / ".flowguard/requests/R2.md"
    body.write_text("Words someone else wrote.\n", encoding="utf-8")
    code, output, _ = _call(root, capsys, "status")
    assert code == 0
    _, rows = _owner_lines(output)
    assert rows[0].startswith("R2 ") and "edited after it was stored" in rows[0], rows
    assert "Words someone else wrote." not in output and "python -m flowguard map check" in rows[0], output


def test_a_deleted_retire_record_is_named_missing_not_edited(tmp_path, capsys):
    root, _ = _retired_copy_without_git(tmp_path, capsys)
    (root / ".flowguard/requests/retired/R1.json").unlink()
    named = [line for line in _call(root, capsys, "status")[1].splitlines() if "retire record" in line]
    assert len(named) == 1 and "R1 is missing" in named[0] and "edited" not in named[0], named

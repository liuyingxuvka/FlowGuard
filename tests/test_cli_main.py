"""Tests grouped by their model or native component."""
from __future__ import annotations
import json
import os
import pytest
from pathlib import Path



from _fg_helpers import (
    target_SHELF_AFTER as SHELF_AFTER,
    target_SHELF_BASE as SHELF_BASE,
    target_SHELF_TARGET as SHELF_TARGET,
    target__assert_current_lending as _assert_current_lending,
    target__check_without_writes as _check_without_writes,
    target__install_shelf_target as _install_shelf_target,
    target__load_map as _load_map,
    target__project_snapshot as _project_snapshot,
    target__promote_with_real_check as _promote_with_real_check,
    target__rename_return_toward_target as _rename_return_toward_target,
    target__run as _run,
    target__run_models_with_results as _run_models_with_results,
    target__target_with as _target_with,
    target__write_map as _write_map,
    target_shelf_project as shelf_project,
    target_shelf_project,
)

@pytest.mark.parametrize("contents", ["{broken json", json.dumps({
    "schema": "wrong.target.schema", "goal": "holds", "components": [], "flows": [], "remove": []})])
@pytest.mark.usefixtures("_no_model_execution")
def test_invalid_target_map_does_not_break_read(tmp_path, capsys, contents):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    original_map = (root / ".flowguard/map.json").read_bytes()
    directory = root / ".flowguard/target"
    directory.mkdir()
    path = directory / "map.json"
    path.write_text(contents, encoding="utf-8")
    code, output, errors = _run(root, capsys, "read")
    assert code == 0 and not errors
    assert next(line for line in output.splitlines() if line.startswith("target:")).startswith(
        "target: .flowguard/target/map.json is invalid; run python -m flowguard target check")
    assert path.read_text(encoding="utf-8") == contents
    assert (root / ".flowguard/map.json").read_bytes() == original_map


@pytest.mark.parametrize("goal", ["", "  "])
@pytest.mark.usefixtures("_no_model_execution")
def test_target_start_rejects_empty_goal_and_missing_map(tmp_path, capsys, goal):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    code, _, errors = _run(root, capsys, "target", "start", goal)
    assert code == 2 and "the goal must be a nonempty sentence" in errors
    assert not (root / ".flowguard/target").exists()
    empty = tmp_path / "empty"
    empty.mkdir()
    code, _, errors = _run(empty, capsys, "target", "start", "holds")
    assert code == 2 and "map" in errors.lower()
    assert not (empty / ".flowguard/target").exists()


@pytest.mark.usefixtures("_no_model_execution")
def test_target_commands_require_a_target_and_offer_help(tmp_path, capsys):
    import flowguard.__main__ as cli
    root = shelf_project(tmp_path)
    capsys.readouterr()
    for arguments in (("add", "loans"), ("drop",), ("drop", "--yes")):
        code, _, errors = _run(root, capsys, "target", *arguments)
        assert code == 2 and "no target" in errors and "target start" in errors
    for arguments in (("target",), ("target", "--help"), ("target", "start", "--help")):
        try:
            code = cli.main([*arguments, "--root", str(root)])
        except SystemExit as exc:
            code = exc.code
        output = capsys.readouterr()
        assert code == 0 and "usage:" in output.out.lower() and not output.err
    assert not (root / ".flowguard/target").exists()


@pytest.mark.usefixtures("_no_model_execution")
def test_target_add_disambiguates_component_and_model_ids(tmp_path, capsys):
    import json
    root = shelf_project(tmp_path)
    capsys.readouterr()
    current = _load_map(root)
    next(component for component in current["components"] if component["id"] == "cli")["id"] = "lending"
    for flow in current["flows"]:
        flow["steps"] = ["lending:" + step.split(":", 1)[1] if step.startswith("cli:") else step
                         for step in flow["steps"]]
    _write_map(root, current)
    assert _run(root, capsys, "target", "start", "disambiguate")[0] == 0
    code, _, errors = _run(root, capsys, "target", "add", "lending")
    assert code == 2 and "is both a component and a model" in errors
    assert "component:lending" in errors and "model:lending" in errors
    for node in ("component:lending", "model:lending"):
        assert _run(root, capsys, "target", "add", node)[0] == 0
    assert (root / ".flowguard/target/models/lending.py").is_file()
    assert [row["id"] for row in json.loads((root / ".flowguard/target/map.json").read_text())["components"]] == ["lending"]


@pytest.mark.usefixtures("_no_model_execution")
def test_target_add_names_helpers_and_current_importers_without_executing_them(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    model = root / ".flowguard/models/lending.py"
    model.write_bytes(model.read_bytes().replace(b"from __future__ import annotations\n",
        b"from __future__ import annotations\nimport _shelf_helper\n", 1))
    (model.parent / "_shelf_helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    (model.parent / "lending_reader.py").write_text(
        'from lending import BorrowBlock\nMODEL_ID = "lending_reader"\n'
        'IMPLEMENTED_BY = {"Borrow": "shelf/loans.py:LoanService.borrow"}\n'
        'def build_explorer():\n    raise AssertionError("must not execute importer")\n', encoding="utf-8")
    assert _run(root, capsys, "target", "start", "change lending")[0] == 0
    code, output, errors = _run(root, capsys, "target", "add", "lending")
    assert code == 0 and not errors
    assert "note: it imports _shelf_helper" in output
    assert "only if the target changes it" in output
    assert "target check also runs these models against the target version: lending_reader" in output
    copied = (root / ".flowguard/target/models/lending.py").read_bytes()
    assert b"import _shelf_helper" in copied
    assert b"import _shelf_helper" not in model.read_bytes()  # tracked edit moved; current is HEAD
    assert not (root / ".flowguard/target/models/_shelf_helper.py").exists()


def test_target_check_todos_then_real_code_and_bound_test(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    current_map = (root / ".flowguard/map.json").read_bytes()
    current_model = (root / ".flowguard/models/lending.py").read_bytes()
    _assert_current_lending(root, capsys)
    for arguments in (
        ("target", "start", "holds"),
        ("target", "add", "loans"),
        ("target", "add", "lending"),
    ):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 0 and not errors, (output, errors)
    directory = root / ".flowguard/target"
    (directory / "map.json").write_text(SHELF_TARGET["map.json"], encoding="utf-8")
    (directory / "models/lending.py").write_text(
        SHELF_TARGET["models/lending.py"], encoding="utf-8"
    )

    code, output, errors = _check_without_writes(root, capsys)
    assert code == 3 and not errors, (output, errors)
    assert not any(line.startswith("ERROR ") for line in output.splitlines()), output
    assert "TO-DO model lending:" in output and "LoanService.hold" in output
    assert "test_hold_gets_returned_copy" in output
    assert "next: write the code and tests" in output
    _assert_current_lending(root, capsys)
    code, output, errors = _run(root, capsys, "read")
    assert code == 0 and not errors
    assert "+1 stage children: lending" in output.split("## cli", 1)[1].split("\n## ", 1)[0]

    for relative in ("shelf/loans.py", "tests/test_loans.py"):
        (root / relative).write_text(SHELF_AFTER[relative], encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 0 and not errors, (output, errors)
    assert "target check: 0 error(s), 0 to-do" in output
    assert "next: python -m flowguard target promote" in output
    assert (root / ".flowguard/map.json").read_bytes() == current_map
    assert (root / ".flowguard/models/lending.py").read_bytes() == current_model
    _assert_current_lending(root, capsys)


def test_target_check_planned_component_is_todo_then_clean(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    _install_shelf_target(root, reports=True)
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 3 and not errors, (output, errors)
    assert not any(line.startswith("ERROR ") for line in output.splitlines()), output
    for finding in ("component_empty", "anchor_broken", "dep_unused"):
        assert any(line.startswith("TO-DO ") and finding in line for line in output.splitlines()), output
    assert any(line.startswith("WARN ") and "test_missing" in line for line in output.splitlines())
    _assert_current_lending(root, capsys)
    for relative in ("shelf/reports.py", "tests/test_reports.py"):
        (root / relative).write_text(SHELF_AFTER[relative], encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 0 and "target check: 0 error(s), 0 to-do" in output and not errors, (output, errors)
    # The real new files are unowned in the CURRENT map; the overlay must not
    # silently promote them into it just because its own check is now clean.
    assert not any(component["id"] == "reports" for component in _load_map(root)["components"])
    code, output, errors = _run(root, capsys, "map", "models", "lending")
    assert code == 0 and any(line.split()[:2] == ["PASS", "lending"] for line in output.splitlines()) and "no_idle_copy_while_held" not in output, (output, errors)


@pytest.mark.parametrize("statement,expected_code", [
    ("import flowguard_missing_external_dependency\n", 1),
    ("import shelf.future_feature\n", 3)])
def test_target_bound_test_imports_keep_environment_errors_distinct(tmp_path, capsys, statement, expected_code):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    _install_shelf_target(root)
    for relative in ("shelf/loans.py", "tests/test_loans.py"):
        (root / relative).write_text(SHELF_AFTER[relative], encoding="utf-8")
    tests = root / "tests/test_loans.py"
    tests.write_text(statement + tests.read_text(), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == expected_code and not errors and "bound tests: ran for lending" in output, (output, errors)
    code, output, errors = _run(root, capsys, "target", "promote")
    assert code == 1 and "ERROR model lending:" in output, (output, errors)
    assert statement.strip()[7:] in output
    assert not any(line.startswith("TO-DO model lending: tested_by") for line in output.splitlines())


def test_unplanned_catalog_breakage_stays_an_error_with_a_target(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    _install_shelf_target(root)
    path = root / "shelf/catalog.py"
    source = path.read_text(encoding="utf-8")
    assert source.count("def take(") == 1
    path.write_text(source.replace("def take(", "def take_renamed("), encoding="utf-8")
    for arguments in (("map", "check"), ("change", "shelf/catalog.py")):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 1 and not errors, (output, errors)
        assert any("ERROR" in line and "anchor_broken" in line and "Catalog.take" in line
                   and "moving to target:" not in line for line in output.splitlines()), output


def test_new_target_file_is_moving_but_strict_remains_an_error(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    _install_shelf_target(root, reports=True)
    (root / "shelf/reports.py").write_text(SHELF_AFTER["shelf/reports.py"], encoding="utf-8")
    code, output, errors = _run(root, capsys, "map", "check")
    assert code == 0 and not errors, (output, errors)
    assert any("INFO" in line and "file_unmapped" in line and "moving to target:" in line
               and "shelf/reports.py" in line for line in output.splitlines()), output
    code, output, errors = _run(root, capsys, "change", "shelf/reports.py")
    assert code == 0 and not errors, (output, errors)
    assert "moving to target:" in output and "UNMAPPED changed files" not in output
    code, output, errors = _run(root, capsys, "map", "check", "--strict")
    assert code == 1 and any("ERROR" in line and "file_unmapped" in line
                            for line in output.splitlines()), (output, errors)


def test_release_warns_first_but_runs_the_same_current_models(tmp_path, capsys):
    import json
    root = shelf_project(tmp_path)
    capsys.readouterr()
    before_code, before, before_errors = _run(root, capsys, "release")
    assert before_code == 0 and not before_errors, (before, before_errors)
    assert not any(line.startswith("warning: target ") for line in before.splitlines())
    _install_shelf_target(root)
    code, output, errors = _run(root, capsys, "release")
    assert code == before_code and not errors, (output, errors)
    goal = json.loads(SHELF_TARGET["map.json"])["goal"]
    assert output.splitlines()[0] == (
        f'warning: target "{goal}" exists: release checks only the current tree; '
        'promote or drop the target before releasing')
    # Compare actual proof results/counts, leaving elapsed times out of the oracle.
    def proof_facts(text):
        return ([line.split()[:2] for line in text.splitlines() if line.split()[:1] in (["PASS"], ["FAIL"], ["ERROR"])],
                [line.strip() for line in text.splitlines() if line.startswith("models:") or "rules:" in line],
                [line for line in text.splitlines() if line.startswith("check --strict:")])
    assert proof_facts(output) == proof_facts(before)
    assert "no_idle_copy_while_held" not in output
    assert "verify: PASS" in output


@pytest.mark.parametrize("node", ["model", "flow", "missing_model"])
def test_target_component_does_not_hide_an_unplanned_model_or_flow(tmp_path, capsys, node):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    if node == "model":
        source = SHELF_BASE[".flowguard/models/lending.py"]
        assert source.count('MODEL_ID = "lending"') == 1
        (root / ".flowguard/models/unplanned_lending.py").write_text(
            source.replace('MODEL_ID = "lending"', 'MODEL_ID = "unplanned_lending"'), encoding="utf-8")
        finding, identity = "model_anchor_broken", ".flowguard/models/unplanned_lending.py"
    elif node == "missing_model":
        data = _load_map(root)
        next(component for component in data["components"] if component["id"] == "loans")["models"] = [
            ".flowguard/models/unknown_contract.py"]
        _write_map(root, data)
        finding, identity = "model_missing", ".flowguard/models/unknown_contract.py"
    else:
        data = _load_map(root)
        data["flows"].append({"id": "unplanned_return", "summary": "Return an existing loan.",
                              "steps": ["loans:LoanService.give_back"]})
        _write_map(root, data)
        finding, identity = "flow_step_broken", "unplanned_return"
    _rename_return_toward_target(root)
    changed = ["shelf/loans.py"] + ([identity] if node == "missing_model" else [])
    for arguments in (("map", "check"), ("change", *changed)):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 1 and not errors, (output, errors)
        assert any("ERROR" in line and finding in line and identity in line
                   and "moving to target:" not in line for line in output.splitlines()), output
        assert any("INFO" in line and "moving to target:" in line and "LoanService.give_back" in line
                   for line in output.splitlines()), output
        if node == "missing_model" and arguments[0] == "change":
            assert any(line.startswith("BLOCKED ") and identity in line for line in output.splitlines()), output


def test_target_keeps_ambiguous_test_command_blocked(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    _install_shelf_target(root)
    data = _load_map(root)
    data["test_commands"] = {"tests/test_loans.py": "python -m pytest -q",
                             "tests/test_*.py": "python -m pytest -v"}
    expected = "ambiguous test commands"
    _write_map(root, data)
    import ast
    source=root/"shelf/loans.py"
    lines=source.read_text().splitlines(True)
    method=next(n for n in ast.walk(ast.parse(''.join(lines))) if isinstance(n,ast.FunctionDef) and n.name=='borrow')
    lines.insert(method.body[0].lineno-1,' '*(method.col_offset+4)+'pass\n')
    source.write_text(''.join(lines))
    code, output, errors = _run(root, capsys, "change", "shelf/loans.py")
    assert code == 1 and not errors, (output, errors)
    assert any(line.startswith("BLOCKED ") and expected in line for line in output.splitlines()), output


def test_target_promote_real_shelf_lifecycle_without_dropping_bindings(tmp_path, capsys, monkeypatch):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    before_missing = _project_snapshot(root)
    code, output, errors = _run(root, capsys, "target", "promote")
    assert code == 2 and "no target; start one" in output + errors, (output, errors)
    assert _project_snapshot(root) == before_missing
    for arguments in (("target", "start", "holds"), ("target", "add", "loans"),
                      ("target", "add", "lending")):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 0 and not errors, (output, errors)
    directory = root / ".flowguard/target"
    (directory / "map.json").write_text(SHELF_TARGET["map.json"], encoding="utf-8")
    (directory / "models/lending.py").write_text(SHELF_TARGET["models/lending.py"], encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 3 and "TO-DO model lending:" in output and not errors, (output, errors)
    before = _project_snapshot(root)
    code, output, errors = _promote_with_real_check(root, capsys, monkeypatch)
    assert code == 1 and "promote refused:" in output + errors, (output, errors)
    assert _project_snapshot(root) == before

    for relative in ("shelf/loans.py", "tests/test_loans.py"):
        (root / relative).write_text(SHELF_AFTER[relative], encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 0 and not errors, (output, errors)
    checked_model = (directory / "models/lending.py").read_bytes()
    code, output, errors = _promote_with_real_check(root, capsys, monkeypatch)
    assert code == 0 and not errors and output.startswith('promoted "'), (output, errors)
    assert "next: python -m flowguard map confirm loans" in output
    assert "next: commit (the code, .flowguard/models/ and .flowguard/map.json together)" in output
    assert not directory.exists()
    assert (root / ".flowguard/models/lending.py").read_bytes() == checked_model
    loans = next(component for component in _load_map(root)["components"] if component["id"] == "loans")
    assert loans["status"] == "draft" and "fingerprint" not in loans
    assert "tests/test_loans.py" in loans["tests"]
    code, output, errors = _run(root, capsys, "map", "confirm", "loans")
    assert code == 0 and not errors, (output, errors)
    code, output, errors = _run(root, capsys, "map", "check")
    assert code == 0 and "0 error(s), 0 warning(s)" in output and not errors, (output, errors)
    code, output, errors, results = _run_models_with_results(root, capsys, "lending", "--tests")
    assert code == 0 and any(line.split()[:2] == ["PASS", "lending"] for line in output.splitlines()), (output, errors)
    assert "no_idle_copy_while_held" in results[0].rules
    code, output, errors = _run(root, capsys, "read")
    assert code == 0 and not errors, (output, errors)
    assert not any(line.startswith("target:") for line in output.splitlines())
    directory.mkdir()
    (directory / "map.json").write_text("{", encoding="utf-8")
    before_invalid = _project_snapshot(root)
    code, output, errors = _promote_with_real_check(root, capsys, monkeypatch)
    assert code == 1 and "promote refused:" in output + errors, (output, errors)
    assert _project_snapshot(root) == before_invalid


def test_target_promote_adds_reports_and_removes_the_requested_flow(tmp_path, capsys, monkeypatch):
    import json
    root = shelf_project(tmp_path)
    capsys.readouterr()
    directory = _install_shelf_target(root, reports=True)
    path = directory / "map.json"
    draft = json.loads(path.read_text(encoding="utf-8"))
    draft["remove"] = ["flow:borrow"]
    path.write_text(json.dumps(draft), encoding="utf-8")
    for relative in ("shelf/reports.py", "tests/test_reports.py"):
        (root / relative).write_text(SHELF_AFTER[relative], encoding="utf-8")
    code, output, errors = _promote_with_real_check(root, capsys, monkeypatch)
    assert code == 0 and not errors, (output, errors)
    assert not directory.exists()
    data = _load_map(root)
    reports = next(component for component in data["components"] if component["id"] == "reports")
    assert reports["status"] == "draft" and "fingerprint" not in reports
    assert not any(flow["id"] == "borrow" for flow in data["flows"])
    assert "next: python -m flowguard map confirm reports" in output
    assert _run(root, capsys, "map", "confirm", "reports")[0] == 0
    code, output, errors = _run(root, capsys, "map", "check")
    assert code == 0 and "0 error(s)" in output and not errors, (output, errors)


def test_target_promote_keeps_replacement_filename_when_old_model_id_is_removed(tmp_path, capsys, monkeypatch):
    import json
    root = shelf_project(tmp_path)
    capsys.readouterr()
    directory = root / ".flowguard/target"
    (directory / "models").mkdir(parents=True)
    (directory / "map.json").write_text(json.dumps({"schema": "flowguard.target.v1", "goal": "rename the model identity",
        "components": [], "flows": [], "remove": ["model:lending"]}), encoding="utf-8")
    source = SHELF_BASE[".flowguard/models/lending.py"]
    assert source.count('MODEL_ID = "lending"') == 1
    replacement = source.replace('MODEL_ID = "lending"', 'MODEL_ID = "lending_v2"').encode("utf-8")
    (directory / "models/lending.py").write_bytes(replacement)
    assert _run(root,capsys,'target','add','desk')[0]==0
    consumer=directory/'models/desk.py'
    consumer.write_text(consumer.read_text().replace('"lending":{"answer":"answer"}','"lending_v2":{"answer":"answer"}'),encoding='utf-8')
    code, output, errors = _promote_with_real_check(root, capsys, monkeypatch)
    assert code == 0 and not errors, (output, errors)
    assert not directory.exists()
    assert (root / ".flowguard/models/lending.py").read_bytes() == replacement
    code, output, errors = _run(root, capsys, "map", "models", "lending_v2", "--tests")
    assert code == 0 and any(line.split()[:2] == ["PASS", "lending_v2"] for line in output.splitlines()), (output, errors)


def test_merge_a_component_keeps_its_promises(tmp_path, capsys):
    import json
    root = shelf_project(tmp_path)
    capsys.readouterr()
    for arguments in (("target", "start", "merge members into loans"), ("target", "add", "loans")):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 0 and not errors, (output, errors)
    path = root / ".flowguard/target/map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["remove"] = ["component:members"]
    path.write_text(json.dumps(data), encoding="utf-8")

    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and not errors, (output, errors)
    owner_errors = [line for line in output.splitlines() if line.startswith("ERROR ") and "owner_dropped:" in line]
    assert len(owner_errors) == 3, output
    assert any("entrypoint 'shelf/members.py:Members.may_borrow'" in line for line in owner_errors), output
    assert any("state 'known members'" in line for line in owner_errors), output
    assert any("responsibility 'enforce the loan limit'" in line for line in owner_errors), output
    all_errors = [line for line in output.splitlines() if line.startswith("ERROR ")]
    code, changed, errors = _run(root, capsys, "change")
    assert code == 0 and not errors, (changed, errors)
    assert f'TARGET "merge members into loans": {len(all_errors)} design error(s)' in changed, changed
    before_refusal = _project_snapshot(root)
    code, refused, errors = _run(root, capsys, "target", "promote")
    assert code == 1 and "promote refused:" in refused + errors, (refused, errors)
    assert all(line in refused for line in all_errors)
    assert _project_snapshot(root) == before_refusal

    loans = data["components"][0]
    loans["files"].append("shelf/members.py")
    loans["entrypoints"].append("shelf/members.py:Members.may_borrow")
    # A word-order change still names the same state; entrypoint anchors remain exact.
    loans["state"].append("members known")
    loans["responsibilities"].append("enforce the loan limit")
    loans["depends_on"].remove("members")
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _run(root, capsys, "target", "add", "flow:borrow")
    assert code == 0 and not errors, (output, errors)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["flows"][0]["steps"] = [step.replace("members:", "loans:", 1) for step in data["flows"][0]["steps"]]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 0 and "0 error(s), 0 to-do" in output and not errors, (output, errors)
    data["components"][0]["state"][-1] = "known members"
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _run(root, capsys, "target", "promote")
    assert code == 0 and not errors, (output, errors)
    current = _load_map(root)
    assert "members" not in {component["id"] for component in current["components"]}
    kept = next(component for component in current["components"] if component["id"] == "loans")
    assert "shelf/members.py" in kept["files"]
    assert "shelf/members.py:Members.may_borrow" in kept["entrypoints"]
    assert "known members" in kept["state"] and "enforce the loan limit" in kept["responsibilities"]
    code, output, errors = _run(root, capsys, "map", "confirm", "loans")
    assert code == 0 and not errors, (output, errors)
    code, output, errors = _run(root, capsys, "map", "check")
    assert code == 0 and "0 error(s)" in output and not errors, (output, errors)


def test_dropping_an_entrypoint_on_purpose_is_written_in_remove(tmp_path, capsys):
    import json
    root = shelf_project(tmp_path)
    capsys.readouterr()
    for arguments in (("target", "start", "retire explicit member promises"),
                      ("target", "add", "loans"), ("target", "add", "cli"),
                      ("target", "add", "flow:borrow")):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 0 and not errors, (output, errors)
    path = root / ".flowguard/target/map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["remove"] = ["component:members", "entrypoint:shelf/members.py:Members.may_borrow", "state:known members",
                      "responsibility:enforce the loan limit"]
    loans = next(component for component in data["components"] if component["id"] == "loans")
    loans["files"].append("shelf/members.py")
    loans["depends_on"].remove("members")
    command = next(component for component in data["components"] if component["id"] == "cli")
    command["side_effects"] = []
    # A counterclaim in the wrong facet cannot take over a real side effect.
    command["state"] = ["prints the result"]
    data["flows"][0]["steps"] = [step.replace("members:", "loans:", 1) for step in data["flows"][0]["steps"]]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and not errors, (output, errors)
    owner_errors = [line for line in output.splitlines() if line.startswith("ERROR ") and "owner_dropped:" in line]
    assert len(owner_errors) == 1 and "side_effect 'prints the result'" in owner_errors[0], output
    assert "component cli" in owner_errors[0]
    command["state"] = []
    data["remove"].append("side_effect:prints the result")
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 0 and "owner_dropped" not in output and not errors, (output, errors)
    assert "(+0 ~3 -1 nodes)" in output, output
    code, current_read, errors = _run(root, capsys, "read")
    assert code == 0 and not errors, (current_read, errors)
    assert 'target: "retire explicit member promises": +0 ~3 -1 nodes;' in current_read, current_read
    code, target_read, errors = _run(root, capsys, "read", "--target")
    assert code == 0 and not errors, (target_read, errors)
    header = next(line for line in target_read.splitlines() if line.startswith("target:"))
    assert "-1 nodes)" in header, header
    removed_nodes = [line for line in target_read.splitlines() if line.startswith("## - ")]
    assert len(removed_nodes) == 1 and removed_nodes[0].startswith("## - members ["), target_read
    code, changed, errors = _run(root, capsys, "change")
    assert code == 0 and 'TARGET "retire explicit member promises": 0 design error(s)' in changed and not errors, (changed, errors)
    data["remove"].append("entrypoint:shelf/nope.py:x")
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and "ERROR target: target_invalid" in output and not errors, (output, errors)
    assert "entrypoint:shelf/nope.py:x" in output


def test_removed_symbol_still_referenced_is_a_todo(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    for arguments in (("target", "start", "drop Catalog.free"), ("target", "add", "lending")):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 0 and not errors, (output, errors)
    path = root / ".flowguard/target/models/lending.py"
    source = path.read_text(encoding="utf-8")
    source = source.replace("from dataclasses import dataclass, replace\n",
                            "from dataclasses import dataclass, replace\nfrom pathlib import Path\n"
                            "from flowguard.map.facts import CodeFacts\n", 1)
    prefix, separator, suffix = source.rpartition("    return last\n")
    assert separator and not suffix
    path.write_text(prefix + '    facts = CodeFacts(Path(__file__).resolve().parents[2])\n'
                    '    facts.unreferenced("shelf/catalog.py:Catalog.free")\n'
                    '    facts.check("the lending replay still conforms", last.ok, last.format_text())\n'
                    '    return facts.report()\n', encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 3 and "TO-DO model lending:" in output and "Catalog.free" in output and not errors, (output, errors)
    assert "still referenced at shelf/loans.py:" in output, output
    catalog = root / "shelf/catalog.py"
    catalog_source = catalog.read_text(encoding="utf-8")
    old_definition = '    def free(self, book):\n        return self.copies.get(book, 0)\n\n'
    assert catalog_source.count(old_definition) == 1
    catalog.write_text(catalog_source.replace(old_definition, ""), encoding="utf-8")
    loans = root / "shelf/loans.py"
    loan_source = loans.read_text(encoding="utf-8")
    assert loan_source.count("self.catalog.free(book)") == 1
    loans.write_text(loan_source.replace("self.catalog.free(book)", "self.catalog.copies.get(book, 0)"), encoding="utf-8")
    tests = {"tests/test_catalog.py": (("c.free(\"x\")", 'c.copies.get("x", 0)'),),
             "tests/test_loans.py": (("s.catalog.free(\"dune\")", 's.catalog.copies.get("dune", 0)'),)}
    for relative, replacements in tests.items():
        test_path = root / relative
        text = test_path.read_text(encoding="utf-8")
        for old, new in replacements:
            assert old in text
            text = text.replace(old, new)
        test_path.write_text(text, encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 0 and "0 error(s), 0 to-do" in output and not errors, (output, errors)


def test_target_keeps_state_unique_and_public_entries_owned(tmp_path, capsys):
    import json
    root = shelf_project(tmp_path)
    capsys.readouterr()
    for arguments in (("target", "start", "plan a lending split"), ("target", "add", "loans")):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 0 and not errors, (output, errors)
    path = root / ".flowguard/target/map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["components"][0]["state"].append("holds per book in order")
    data["components"].append({"id": "holds", "layer": "lending", "summary": "Records member reservations",
                               "responsibilities": ["record a member reservation"], "files": ["shelf/holds.py"],
                               "entrypoints": [], "state": ["holds per book in order"], "side_effects": [],
                               "depends_on": [], "tests": [], "models": []})
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and not errors, (output, errors)
    assert any(line.startswith("ERROR ") and "duplicate_owner:" in line
               and "state 'holds per book in order'" in line for line in output.splitlines()), output

    current = _load_map(root)
    desk = json.loads(json.dumps(next(component for component in current["components"] if component["id"] == "loans")))
    command = json.loads(json.dumps(next(component for component in current["components"] if component["id"] == "cli")))
    for component in (desk, command):
        for field in ("status", "fingerprint", "_hint"):
            component.pop(field, None)
    desk.update(id="lending-desk", summary="Lends free copies", responsibilities=["lend a free copy"],
                entrypoints=["shelf/loans.py:LoanService.borrow"])
    command["depends_on"] = ["lending-desk"]
    returns = {"id": "returns", "layer": "lending", "summary": "Takes back a lent copy",
               "responsibilities": ["take a lent copy back"], "files": ["shelf/returns.py"],
               "entrypoints": [], "state": [], "side_effects": [], "depends_on": [], "tests": [], "models": []}
    data["components"] = [desk, returns, command]
    data["remove"] = ["component:loans"]
    flow = json.loads(json.dumps(current["flows"][0]))
    flow["steps"] = [step.replace("loans:", "lending-desk:", 1) for step in flow["steps"]]
    data["flows"] = [flow]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and not errors, (output, errors)
    dropped = [line for line in output.splitlines() if line.startswith("ERROR ") and "owner_dropped:" in line]
    assert len(dropped) == 1 and "entrypoint 'shelf/loans.py:LoanService.give_back'" in dropped[0], output
    assert "duplicate_owner:" not in output, output


def test_rename_a_field_through_the_target(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    current_model = (root / ".flowguard/models/lending.py").read_bytes()
    for arguments in (("target", "start", "rename the member loan limit"), ("target", "add", "lending")):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 0 and not errors, (output, errors)
    code, output, errors = _check_without_writes(root, capsys)
    # A fresh copy changes nothing yet.
    assert code == 1 and "target_noop" in output and "1 error(s), 0 to-do" in output and not errors, (output, errors)

    model = root / ".flowguard/target/models/lending.py"
    source = model.read_text(encoding="utf-8")
    old_import = "from dataclasses import dataclass, replace\n"
    assert source.count(old_import) == 1
    source = source.replace(old_import, old_import + "from pathlib import Path\nfrom flowguard.map.facts import CodeFacts\n", 1)
    prefix, separator, suffix = source.rpartition("    return last\n")
    assert separator and not suffix
    model.write_text(prefix + '    facts = CodeFacts(Path(__file__).resolve().parents[2])\n'
                     '    facts.check("the lending replay still conforms", last.ok, last.format_text())\n'
                     '    facts.absent("LIMIT", ["shelf/members.py"])\n'
                     '    facts.present("LOAN_LIMIT", ["shelf/members.py"])\n'
                     '    return facts.report()\n', encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 3 and not errors, (output, errors)
    assert "TO-DO model lending:" in output and "LIMIT" in output, output
    assert not any(line.startswith("ERROR ") for line in output.splitlines()), output
    assert (root / ".flowguard/models/lending.py").read_bytes() == current_model

    members = root / "shelf/members.py"
    source = members.read_text(encoding="utf-8")
    assert source.count("LIMIT") == 2 and "LOAN_LIMIT" not in source
    members.write_text(source.replace("LIMIT", "LOAN_LIMIT"), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 0 and "0 error(s), 0 to-do" in output and not errors, (output, errors)
    assert (root / ".flowguard/models/lending.py").read_bytes() == current_model


def test_target_child_can_plan_code_owned_by_its_component(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    directory = _install_shelf_target(root, reports=True)
    source = '''from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
MODEL_ID = "report_child"
PARENT = "reports"
IMPLEMENTED_BY = {"Overdue": "shelf/reports.py:overdue"}
TESTED_BY = {}
class Overdue:
    name = "Overdue"
    def __init__(self, bad=False): self.bad = bad
    def apply(self, late, state):
        result = (("alice", "book"),) if late or self.bad else ()
        return [FunctionResult(result, (late, result))]
def explorer(bad=False):
    return Explorer(Workflow((Overdue(bad),)), initial_states=((False, ()),), external_inputs=(False, True),
                    max_sequence_length=1, progress_steps=0,
                    invariants=(Invariant("only_overdue", "only late members appear",
                                          lambda s, t: s[1] == ((("alice", "book"),) if s[0] else ())),))
def build_explorer(): return explorer()
def broken_variants(): return {"ignores_lateness": explorer(True)}
def conformance():
    from types import SimpleNamespace
    from shelf.reports import overdue
    service = SimpleNamespace(loans=[("alice", "book")])
    return CodeFactsReport(tuple(Fact("actual overdue result", tuple(overdue(service, {"alice"} if late else set()))
                                     == ((("alice", "book"),) if late else ())) for late in (False, True)))
'''
    child = directory / "models/report_child.py"
    child.write_text(source, encoding="utf-8")
    assert not (root / "shelf/reports.py").exists()
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 3 and not errors, (output, errors)
    assert not any(line.startswith("ERROR ") for line in output.splitlines()), output
    assert any(line.startswith("TO-DO ") and "model_anchor_broken" in line and "shelf/reports.py" in line
               for line in output.splitlines()), output
    _assert_current_lending(root, capsys)

    child.write_text(source.replace("shelf/reports.py:overdue", "shelf/unowned_report.py:overdue"), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 3 and not errors, (output, errors)
    assert not any(line.startswith("ERROR ") and "anchor_outside_home" in line for line in output.splitlines()), output
    assert any(line.startswith("TO-DO ") and "shelf/unowned_report.py" in line
               for line in output.splitlines()), output

    # This final guard observes the current tree after removing the overlay.
    code, output, errors = _run(root, capsys, "target", "drop", "--yes")
    assert code == 0 and not errors and not directory.exists(), (output, errors)
    current_model = root / ".flowguard/models/lending.py"
    current_source = current_model.read_text(encoding="utf-8")
    anchor = "shelf/loans.py:LoanService.borrow"
    assert current_source.count(anchor) == 1
    current_model.write_text(current_source.replace(anchor, "shelf/loans.py:LoanService.missing_borrow"), encoding="utf-8")
    code, output, errors = _run(root, capsys, "map", "check")
    assert code == 1 and not errors, (output, errors)
    assert any(line.startswith("ERROR ") and "model_anchor_broken" in line and "missing_borrow" in line
               for line in output.splitlines()), output


def test_target_refuses_to_remove_a_component_parent_with_children(tmp_path, capsys):
    import json
    root = shelf_project(tmp_path)
    capsys.readouterr()
    current = _load_map(root)
    for component in current['components']:
        if component['id'] in {'catalog', 'loans'}:
            component['parent'] = 'records'
            component['layer'] = 'records'
    current['components'].append(dict(
        id='records', layer='records', summary='Record subsystem', responsibilities=['group records'],
        files=[], tests=[], models=[], depends_on=[], status='draft'))
    _write_map(root, current)
    assert _run(root, capsys, 'map', 'check')[0] == 0
    assert _run(root, capsys, 'map', 'confirm', 'all')[0] == 0
    before = (root / '.flowguard/map.json').read_bytes()
    assert _run(root, capsys, 'target', 'start', 'remove the records parent')[0] == 0
    path = root / '.flowguard/target/map.json'
    draft = json.loads(path.read_text(encoding='utf-8'))
    draft['remove'] = ['component:records']
    path.write_text(json.dumps(draft), encoding='utf-8')
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and not errors, (output, errors)
    assert any(line.startswith('ERROR') and 'target_invalid' in line and 'parent' in line and 'records' in line
               for line in output.splitlines()), output
    assert (root / '.flowguard/map.json').read_bytes() == before
    assert {component['id'] for component in _load_map(root)['components'] if component.get('parent') == 'records'} == {'catalog', 'loans'}


def test_promote_lists_what_to_re_read(tmp_path, capsys):
    import json
    import re

    root = shelf_project(tmp_path)
    capsys.readouterr()
    path = _target_with(root, capsys, "lending under a shelf policy", "catalog", "lending")
    target = json.loads(path.read_text(encoding="utf-8"))
    target["components"][0]["summary"] = "Counts the free copies of each book."
    path.write_text(json.dumps(target), encoding="utf-8")
    models = root / ".flowguard/target/models"
    source = (models / "lending.py").read_text(encoding="utf-8")
    # A component grouping changes placement without inventing a second domain model.
    parent = dict(id="shelf_policy", layer="lending", summary="Group shelf policy code", responsibilities=["group the lending components"],
                  files=[], tests=[], models=[], depends_on=[], state=[], side_effects=[])
    target["components"].append(parent)
    current_loans = next(c for c in _load_map(root)["components"] if c["id"] == "loans")
    target["components"].append({**{k:v for k,v in current_loans.items() if k not in {"status","fingerprint","_hint"}}, "parent": "shelf_policy"})
    path.write_text(json.dumps(target), encoding="utf-8")
    source = source.replace('PARENT = "desk"', 'PARENT = "shelf_policy"')
    source = source.replace(',\n             "limit_respected": ["tests/test_loans.py:test_limit"]}', '}')
    (models / "lending.py").write_text(source, encoding="utf-8")
    code, output, errors = _run(root, capsys, "target", "promote")
    assert code == 0, (output, errors)
    lines = output.splitlines()
    assert "re-read: model lending: its parent changed from desk to shelf_policy; check its purpose" in lines, output
    assert "re-read: flow borrow: it crosses changed component loans; check its steps and model" in lines, output
    assert "re-read: test tests/test_loans.py:test_limit: no longer bound by any TESTED_BY; bind it or delete it" in lines
    assert lines.index("re-read: test tests/test_loans.py:test_limit: no longer bound by any TESTED_BY; bind it or delete it") \
        < next(index for index, line in enumerate(lines) if line.startswith("next: "))


def test_shelf_example_matches_the_fixture_and_runs_the_target_workflow(tmp_path, capsys):
    """examples/shelf holds the shelf fixture as files; copied out it runs the whole target workflow."""
    import subprocess
    from pathlib import Path
    import shutil

    example = Path(__file__).resolve().parents[1] / "examples/shelf"
    expected = {**SHELF_BASE,
                **{"target/" + name: SHELF_TARGET[name] for name in ("map.json", "models/lending.py")},
                **{"after/" + name: SHELF_AFTER[name] for name in ("shelf/loans.py", "tests/test_loans.py")}}
    found = {path.relative_to(example).as_posix(): path.read_bytes().decode("utf-8").replace("\r\n", "\n")
             for path in example.rglob("*") if path.is_file() and path.name != "README.md" and "__pycache__" not in path.parts and not path.relative_to(example).as_posix().startswith(".flowguard/cache/")}
    assert found == {name: text.replace("\r\n", "\n") for name, text in expected.items()}
    root = tmp_path / "shelf"          # the project is the example without its target/ and after/ folders
    for part in (".flowguard", "shelf", "tests"):
        shutil.copytree(example / part, root / part)
    git = ["git", "-c", "core.autocrlf=false", "-c", "user.name=FlowGuard tests",
           "-c", "user.email=flowguard-tests@example.invalid"]
    for arguments in (("init", "-q"), ("add", "."), ("commit", "-qm", "shelf baseline")):
        subprocess.run([*git, *arguments], cwd=root, check=True, capture_output=True)
    assert _run(root, capsys, "map", "confirm", "all")[0] == 0
    shutil.copytree(example / "target", root / ".flowguard/target")
    code, output, errors = _run(root, capsys, "target", "check")
    assert code == 3 and "TO-DO" in output and "ERROR" not in output, (output, errors)
    shutil.copytree(example / "after", root, dirs_exist_ok=True)
    code, output, errors = _run(root, capsys, "target", "check")
    assert code == 0, (output, errors)
    code, output, errors = _run(root, capsys, "target", "promote")
    assert code == 0 and not (root / ".flowguard/target").exists(), (output, errors)


def test_jobs_default_is_min_four_cpus(tmp_path, monkeypatch, capsys):
    import os
    from flowguard.__main__ import _verb_parser
    from flowguard.map import proof, target
    from flowguard.map.cli import build_parser
    expected = min(4, os.cpu_count() or 1)
    assert proof.DEFAULT_JOBS == expected
    for parser, argv in ((_verb_parser('release'), []),
            (build_parser(), ['models']), (build_parser(), ['verify']),
            (target.build_parser(), ['check']), (target.build_parser(), ['promote'])):
        assert parser.parse_args(argv).jobs == expected
    root = target_shelf_project(tmp_path)
    assert target.start_target(root, 'parallel model checks') == 0
    assert target.add_to_target(root, 'lending') == 0
    recorded = []
    original = proof.run_models
    def run_models(*args, **kwargs):
        recorded.append(kwargs.get('jobs'))
        return []
    monkeypatch.setattr(proof, 'run_models', run_models)
    target.main(['check', '--root', str(root)])
    assert recorded and recorded[-1] == expected
    recorded.clear()
    target.check_target(root)
    assert recorded and recorded[-1] == 1
    monkeypatch.setattr(proof, 'run_models', original)
    def no_pool(*args, **kwargs):
        raise AssertionError('serial model execution must stay in the calling thread')
    monkeypatch.setattr(proof, 'ThreadPoolExecutor', no_pool)
    results = proof.run_models(root, [], jobs=1)
    assert results and all(result.status == 'pass' for result in results)
    capsys.readouterr()

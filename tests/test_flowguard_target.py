"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


from _fg_helpers import (
    target_SHELF_AFTER as SHELF_AFTER,
    target_SHELF_BASE as SHELF_BASE,
    target_SHELF_TARGET as SHELF_TARGET,
    target__assert_current_lending as _assert_current_lending,
    target__check_without_writes as _check_without_writes,
    target__fg403_clean_target as _fg403_clean_target,
    target__fg403_helpers as _fg403_helpers,
    target__install_shelf_target as _install_shelf_target,
    target__load_map as _load_map,
    target__namespace_project as _namespace_project,
    target__project_snapshot as _project_snapshot,
    target__promote_with_real_check as _promote_with_real_check,
    target__run as _run,
    target__run_models_with_results as _run_models_with_results,
    target__static_target_read as _static_target_read,
    target__target_life_cycle_fixture_helpers as _target_life_cycle_fixture_helpers,
    target__target_with as _target_with,
    target_shelf_project as shelf_project,
    target__run,
    target_shelf_project,
)

@pytest.mark.usefixtures("_no_model_execution")
def test_target_overlay_is_independent_and_rejects_invalid_fields(tmp_path, capsys):
    import json
    import copy
    from flowguard.map.targetfile import (
        load_target,
        merge_target_map,
        target_node_changes,
        validate_target,
    )

    root = shelf_project(tmp_path)
    capsys.readouterr()
    current = _load_map(root)
    before = copy.deepcopy(current)
    loans = copy.deepcopy(next(c for c in current["components"] if c["id"] == "loans"))
    for field in ("status", "fingerprint", "_hint"):
        loans.pop(field, None)
    loans["summary"] = "Loan service with future holds"
    draft = {
        "schema": "flowguard.target.v1",
        "goal": "holds",
        "components": [loans],
        "flows": [],
        "remove": ["flow:borrow"],
        "layers": ["records", "lending", "interface"],
        "accepted_debts": [],
    }
    directory = root / ".flowguard/target"
    directory.mkdir()
    path = directory / "map.json"
    path.write_text(json.dumps(draft))
    target = load_target(root)
    assert target.models == {}  # Git need not retain an empty models directory.
    assert validate_target(root, current, target) == []
    merged = merge_target_map(current, target)
    replacement = next(c for c in merged["components"] if c["id"] == "loans")
    assert replacement["summary"] == "Loan service with future holds"
    assert replacement["status"] == "draft" and "fingerprint" not in replacement
    assert (
        merged["flows"] == []
        and merged["layers"] == draft["layers"]
        and merged["accepted_debts"] == []
    )
    assert target_node_changes(root, current, target) == {
        "+": [],
        "~": ["component:loans"],
        "-": ["flow:borrow"],
    }
    replacement["responsibilities"].append("only in the returned overlay")
    assert current == before and target.data == draft
    invalid = [
        {**draft, "extra": True},
        {**draft, "components": [{**loans, "status": "confirmed"}]},
        {**draft, "components": [loans, loans]},
        {**draft, "remove": ["component:missing"]},
        {**draft, "remove": ["component:loans"]},
        {**draft, "flows": [{"id": "future", "steps": [123]}]},
        {**draft, "flows": [{"id": "future", "steps": [], "model": 123}]},
        *[
            {**draft, "flows": [{"id": "future", "steps": [], "model": value}]}
            for value in ("other/foo.py", "foo.py", ".flowguard/target/models/lending.py")
        ],
    ]
    for payload in invalid:
        path.write_text(json.dumps(payload))
        assert "target_invalid" in {
            issue.code for issue in validate_target(root, current, load_target(root))
        }
    path.write_text(json.dumps({**draft, "components": [{**loans, "summary": ""}]}))
    assert "target_component_incomplete" in {
        issue.code for issue in validate_target(root, current, load_target(root))
    }
    path.write_text(json.dumps(draft))
    (directory / "models").mkdir()
    model = (root / ".flowguard/models/lending.py").read_text()
    (directory / "models/lending2.py").write_text(model)
    assert {"target_model_id_clash"} <= {
        issue.code for issue in validate_target(root, current, load_target(root))
    }
    assert current == before


@pytest.mark.parametrize(
    ("mutation", "finding"),
    [
        ("passing_bad", "known-bad variant 'return_ignores_holds' passed"),
        ("unknown_remove", "target_invalid"),
        ("id_clash", "target_model_id_clash"),
        ("duplicate_responsibility", "duplicate_owner"),
    ],
)
def test_target_check_rejects_real_design_errors(tmp_path, capsys, mutation, finding):
    import json

    root = shelf_project(tmp_path)
    capsys.readouterr()
    directory = _install_shelf_target(root)
    map_path, model_path = directory / "map.json", directory / "models/lending.py"
    original_map, original_model = map_path.read_bytes(), model_path.read_bytes()
    extra = directory / "models/lending2.py"
    try:
        target = json.loads(original_map)
        if mutation == "passing_bad":
            source = original_model.decode("utf-8")
            old = '"return_ignores_holds": _explorer(BorrowBlock(), GiveBackOld())'
            assert source.count(old) == 1
            model_path.write_text(
                source.replace(old, '"return_ignores_holds": _explorer(BorrowBlock())'),
                encoding="utf-8",
            )
        elif mutation == "unknown_remove":
            target["remove"] = ["component:nope"]
        elif mutation == "id_clash":
            extra.write_bytes(original_model)
        else:
            target["components"][0]["responsibilities"].append("count free copies")
        map_path.write_text(json.dumps(target), encoding="utf-8")
        code, output, errors = _check_without_writes(root, capsys)
        assert code == 1 and not errors, (output, errors)
        assert any(
            line.startswith("ERROR ") and finding in line for line in output.splitlines()
        ), output
        assert "next: fix the target design (ERROR lines)" in output
    finally:
        map_path.write_bytes(original_map)
        model_path.write_bytes(original_model)
        extra.unlink(missing_ok=True)
    assert map_path.read_bytes() == original_map and model_path.read_bytes() == original_model
    _assert_current_lending(root, capsys)


def test_target_check_distinguishes_absence_from_malformed_existing_target(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 2 and "no target" in errors and "target start" in errors, (output, errors)
    directory = root / ".flowguard/target"
    (directory / "models").mkdir(parents=True)
    (directory / "map.json").write_text("{", encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and "ERROR target: target_invalid" in output, (output, errors)
    assert "Traceback" not in output + errors


def test_target_view_restores_imports_and_preserves_canonical_root_and_child_port(tmp_path, capsys):
    import sys
    from flowguard.map.proof import run_model_in_process
    from flowguard.map.targetfile import build_target_view, load_target

    root = _namespace_project(tmp_path)
    capsys.readouterr()
    code, output, errors, results = _run_models_with_results(root, capsys, "ns_parent")
    assert code == 0 and results[0].rules == ["one_step_1"], (output, errors)
    view = build_target_view(root, _load_map(root), load_target(root))
    path_before = list(sys.path)
    names = (
        "ns_parent",
        "ns_child",
        "_view_setting",
        "namespace_subject",
        "_flowguard_model_ns_parent",
        "_flowguard_model_ns_child",
    )
    modules_before = {name: sys.modules.get(name) for name in names}
    for name in ("ns_parent", "ns_child"):
        result = run_model_in_process(root, root / f".flowguard/models/{name}.py", view=view)
        assert result.status == "pass", result
        assert result.rules == ["one_step_2"], result
        assert not any("child_start_gap" in warning for warning in result.warnings), result
        assert sys.path == path_before
        assert {key: sys.modules.get(key) for key in names} == modules_before
    # The same-process view has gone away; ordinary commands must still load the
    # current helper and current child, not the target's imported modules.
    code, output, errors, results = _run_models_with_results(root, capsys, "ns_parent")
    assert code == 0 and results[0].rules == ["one_step_1"], (output, errors)
    assert (root / ".flowguard/models/_view_setting.py").read_text() == "VALUE = 1\n"


def test_target_removed_model_cannot_fall_back_to_current_disk(tmp_path, capsys):
    import json

    root = _namespace_project(tmp_path)
    capsys.readouterr()
    directory = root / ".flowguard/target"
    # Keep the importing current parent and the real old child on disk, but
    # explicitly remove that child from the requested namespace.
    (directory / "models/ns_child.py").unlink()
    (directory / "models/_view_setting.py").unlink()
    path = directory / "map.json"
    target = json.loads(path.read_text(encoding="utf-8"))
    target["remove"] = ["model:ns_child"]
    path.write_text(json.dumps(target), encoding="utf-8")
    old_child = (root / ".flowguard/models/ns_child.py").read_bytes()
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and not errors, (output, errors)
    assert any(
        line.startswith("ERROR ") and "ns_child" in line for line in output.splitlines()
    ), output
    assert (root / ".flowguard/models/ns_child.py").read_bytes() == old_child
    code, output, errors, results = _run_models_with_results(root, capsys, "ns_parent")
    assert code == 0 and results[0].rules == ["one_step_1"], (output, errors)


def test_impact_skips_target_changes_before_test_content_lookup(tmp_path, capsys, monkeypatch):
    from pathlib import Path
    from flowguard.map import impact
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import ignore_patterns

    root = shelf_project(tmp_path)
    capsys.readouterr()
    _install_shelf_target(root)
    data = _load_map(root)
    inventory = build_inventory(root, ignore_patterns(data))
    read_source = impact.read_source
    read_tests = []

    def observe_read(path):
        if Path(path).resolve().is_relative_to(root / "tests"):
            read_tests.append(str(path))
        return read_source(path)

    with monkeypatch.context() as scoped:
        scoped.setattr(impact, "read_source", observe_read)
        result = impact.compute_impact(
            root,
            data,
            inventory,
            [".flowguard/target/models/lending.py", ".flowguard/target/map.json"],
            base="HEAD",
        )
    assert (
        not result.changed and not result.tests and not result.models and not result.unmapped
    ), result
    assert not result.blocked and not read_tests, (result, read_tests)


def test_read_target_shows_holds_facets_from_target_bytes_and_keeps_current_read(
    tmp_path, capsys, monkeypatch
):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    directory = _install_shelf_target(root)
    model = directory / "models/lending.py"
    source = model.read_text(encoding="utf-8")
    first_line = source.splitlines()[0]
    model.write_text(
        source.replace(first_line, '"""Target-only reservation policy.', 1)
        + '\nraise AssertionError("a read imported the target model")\n',
        encoding="utf-8",
    )
    current_bytes = (root / ".flowguard/models/lending.py").read_bytes()
    code, output, errors = _static_target_read(root, capsys, monkeypatch, "read", "--target")
    assert code == 0 and not errors and "truncated" not in output, (output, errors)
    for text in (
        "## ~ loans",
        "~ model lending",
        "rules + no_idle_copy_while_held",
        "known-bad + return_ignores_holds",
        "code + Hold -> shelf/loans.py:LoanService.hold",
        "tests + no_idle_copy_while_held -> tests/test_loans.py:test_hold_gets_returned_copy",
        "state + holds per book in order",
        "unchanged: 3 component(s)",
    ):
        assert text in output, (text, output)
    assert "Target-only reservation policy." in output
    assert "## catalog" not in output and "## members" not in output

    code, detail, errors = _static_target_read(
        root, capsys, monkeypatch, "read", "--target", "--component", "loans"
    )
    assert code == 0 and not errors, (detail, errors)
    detail = "\n".join(line for line in detail.splitlines() if not line.startswith("goal rules:"))
    component, foreign_line = detail.split("model lending:", 1)
    assert "(home cli)" in foreign_line and "purpose:" not in foreign_line
    code, home_detail, errors = _static_target_read(
        root, capsys, monkeypatch, "read", "--target", "--component", "cli"
    )
    assert code == 0 and not errors, (home_detail, errors)
    home_detail = "\n".join(
        line for line in home_detail.splitlines() if not line.startswith("goal rules:")
    )
    model_text = home_detail.split("model lending:", 1)[1]
    labels = ("purpose:", "rules:", "known-bad:", "code:", "tests:")
    for section in (component, model_text):
        positions = [section.index(label) for label in labels]
        assert positions == sorted(positions), section
    # The component purpose is unchanged, while the model purpose really differs.
    for section, changed_purpose in ((component, False), (model_text, True)):
        purpose = section.split("purpose:", 1)[1].split("rules:", 1)[0]
        assert ("was:" in purpose) == changed_purpose, purpose
    assert "was:" in component.split("rules:", 1)[1].split("known-bad:", 1)[0]
    assert "was:" in model_text.split("known-bad:", 1)[1].split("code:", 1)[0]
    assert "was:" in model_text.split("tests:", 1)[1]
    code, current, errors = _static_target_read(
        root, capsys, monkeypatch, "read", "--component", "loans"
    )
    assert code == 0 and not errors, (current, errors)
    assert "no_idle_copy_while_held" not in current and "return_ignores_holds" not in current
    assert "Target-only reservation policy." not in current
    assert (root / ".flowguard/models/lending.py").read_bytes() == current_bytes


def test_read_target_added_removed_flows_and_mermaid_use_real_node_identity(
    tmp_path, capsys, monkeypatch
):
    import json
    import re

    root = shelf_project(tmp_path)
    capsys.readouterr()
    directory = _install_shelf_target(root)
    path = directory / "map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["components"].extend(json.loads(SHELF_TARGET["map_reports.json"])["components"])
    data["remove"] = ["component:cli"]
    data["flows"] = [
        {
            "id": "borrow",
            "summary": "Borrow with future holds.",
            "steps": ["loans:LoanService.hold"],
        },
        {"id": "overdue", "summary": "List overdue loans.", "steps": ["reports:overdue"]},
    ]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _static_target_read(root, capsys, monkeypatch, "read", "--target")
    assert code == 0 and not errors, (output, errors)
    for text in (
        "## + reports",
        "## - cli",
        "(removed by the target)",
        "> ~ flow borrow:",
        "> + flow overdue:",
    ):
        assert text in output, (text, output)
    removed = output.split("## - cli", 1)[1].split("\n## ", 1)[0]
    assert "purpose:" not in removed and "changes:" not in removed
    code, diagram, errors = _static_target_read(
        root, capsys, monkeypatch, "read", "--mermaid", "--target"
    )
    assert code == 0 and not errors and diagram.startswith("flowchart TD\n"), (diagram, errors)
    for style in ("added", "changed", "removed"):
        assert f"classDef {style} " in diagram
    assert "stroke-dasharray" in next(
        line for line in diagram.splitlines() if "classDef removed " in line
    )

    # Resolve IDs from actual definitions, rather than assume the renderer's sanitizer.
    def component_id(label):
        matches = re.findall(r'^\s*(\w+)\["' + re.escape(label) + r'<br/>[^"\n]*"\]', diagram, re.M)
        assert len(matches) == 1, (label, diagram)
        return matches[0]

    loans, reports, removed_cli = (component_id(label) for label in ("loans", "reports", "cli"))
    models = re.findall(r'^\s*(\w+)\(\["model lending<br/>[^"\n]*"\]\)', diagram, re.M)
    assert len(models) == 1, diagram
    lending = models[0]
    for node, style in (
        (loans, "changed"),
        (lending, "changed"),
        (reports, "added"),
        (removed_cli, "removed"),
    ):
        assert any(
            line.strip().rstrip(";") == f"class {node} {style}" for line in diagram.splitlines()
        ), diagram
    desk = re.findall(r'^\s*(\w+)\(\["model desk<br/>[^"\n]*"\]\)', diagram, re.M)
    assert len(desk) == 1
    assert f"{desk[0]} ==> {lending}" in diagram
    assert f"root_system --> {reports}" in diagram
    code, focused, errors = _static_target_read(
        root, capsys, monkeypatch, "read", "--target", "--mermaid", "--component", "loans"
    )
    assert (
        code == 0 and "loans<br/>" in focused and "model lending" not in focused and not errors
    ), (focused, errors)
    assert "reports<br/>" not in focused and "cli<br/>" not in focused


def test_read_target_comments_do_not_invent_facet_changes(tmp_path, capsys, monkeypatch):
    import json

    root = shelf_project(tmp_path)
    capsys.readouterr()
    directory = root / ".flowguard/target"
    (directory / "models").mkdir(parents=True)
    (directory / "map.json").write_text(
        json.dumps(
            {
                "schema": "flowguard.target.v1",
                "goal": "explain lending",
                "components": [],
                "flows": [],
                "remove": [],
            }
        ),
        encoding="utf-8",
    )
    (directory / "models/lending.py").write_text(
        SHELF_BASE[".flowguard/models/lending.py"]
        + "\n# Explanation only, no declared fact changed.\n",
        encoding="utf-8",
    )
    code, output, errors = _static_target_read(root, capsys, monkeypatch, "read", "--target")
    assert code == 0 and "model lending" in output and not errors, (output, errors)
    assert "goal rules: none (no promise changes" in output
    output = "\n".join(line for line in output.splitlines() if not line.startswith("goal rules:"))
    assert "changes:" not in output and "was:" not in output
    (directory / "models/lending.py").unlink()
    (directory / "map.json").write_text(
        json.dumps(
            {
                "schema": "flowguard.target.v1",
                "goal": "retire lending",
                "components": [],
                "flows": [],
                "remove": ["component:loans", "model:lending"],
            }
        ),
        encoding="utf-8",
    )
    code, removed, errors = _static_target_read(root, capsys, monkeypatch, "read", "--target")
    assert code == 0 and not errors, (removed, errors)
    assert "## - loans" in removed and "\n  - model lending:" in removed, removed
    assert removed.count("(removed by the target)") == 2, removed
    removed = "\n".join(line for line in removed.splitlines() if not line.startswith("goal rules:"))
    assert not any(
        label in removed for label in ("purpose:", "rules:", "known-bad:", "code:", "tests:")
    ), removed


@pytest.mark.parametrize("state", ["absent", "invalid"])
def test_read_target_absent_or_invalid_is_not_a_current_view(tmp_path, capsys, monkeypatch, state):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    if state == "invalid":
        directory = root / ".flowguard/target"
        directory.mkdir()
        (directory / "map.json").write_text("{", encoding="utf-8")
    code, output, errors = _static_target_read(root, capsys, monkeypatch, "read", "--target")
    assert code == 1, (output, errors)
    text = output + errors
    if state == "absent":
        assert 'no target; start one with python -m flowguard target start "<goal>"' in text
    else:
        assert "target: .flowguard/target/map.json is invalid" in text
    assert "## loans" not in output


def test_read_target_conflicts_only_with_find(tmp_path, capsys, monkeypatch):
    import pytest

    root = shelf_project(tmp_path)
    capsys.readouterr()
    _install_shelf_target(root)
    with pytest.raises(SystemExit) as error:
        _static_target_read(root, capsys, monkeypatch, "read", "--target", "--find", "loans")
    assert error.value.code == 2
    capsys.readouterr()

    code, output, errors = _static_target_read(root, capsys, monkeypatch, "read", "--target")
    assert code == 0 and not errors and "## ~ loans" in output, (output, errors)


def test_target_promote_refuses_a_model_that_edits_its_checked_source(
    tmp_path, capsys, monkeypatch
):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    directory = _install_shelf_target(root)
    for relative in ("shelf/loans.py", "tests/test_loans.py"):
        (root / relative).write_text(SHELF_AFTER[relative], encoding="utf-8")
    model = directory / "models/lending.py"
    model.write_text(
        model.read_text(encoding="utf-8") + """
_original_conformance = conformance

def conformance():
    from pathlib import Path
    report = _original_conformance()
    target = Path(__file__).resolve().parents[2] / ".flowguard/target/models/lending.py"
    with target.open("a", encoding="utf-8", newline="\\n") as stream:
        stream.write("\\n# edited during the real conformance check\\n")
    return report
""",
        encoding="utf-8",
    )
    before_files, before_dirs = _project_snapshot(root)
    code, output, errors = _promote_with_real_check(root, capsys, monkeypatch)
    assert code == 1 and "promote refused:" in output + errors, (output, errors)
    assert "changed" in (output + errors).lower()
    after_files, after_dirs = _project_snapshot(root)
    relative = ".flowguard/target/models/lending.py"
    assert (
        after_files[relative][0]
        == before_files[relative][0] + b"\n# edited during the real conformance check\n"
    )
    # The real model's explicit edit survives; the promoter writes nothing else.
    assert {p: v for p, v in after_files.items() if p != relative} == {
        p: v for p, v in before_files.items() if p != relative
    }
    assert after_dirs == before_dirs and directory.is_dir()


def test_target_promote_reports_real_write_failure_without_backup_or_automatic_git(
    tmp_path, capsys, monkeypatch
):
    from pathlib import Path

    root = shelf_project(tmp_path)
    capsys.readouterr()
    directory = _install_shelf_target(root)
    for relative in ("shelf/loans.py", "tests/test_loans.py"):
        (root / relative).write_text(SHELF_AFTER[relative], encoding="utf-8")
    before_files, before_dirs = _project_snapshot(root)
    original_write = Path.write_bytes
    destination = root / ".flowguard/models/lending.py.tmp"
    attempted = []

    def fail_destination(path, content):
        if path == destination:
            attempted.append(path)
            raise OSError("injected target destination write failure")
        return original_write(path, content)

    with monkeypatch.context() as scoped:
        scoped.setattr(Path, "write_bytes", fail_destination)
        code, output, errors = _promote_with_real_check(root, capsys, monkeypatch)
    assert attempted == [destination]
    assert code == 2 and "injected target destination write failure" in output + errors, (
        output,
        errors,
    )
    assert "restore with: git checkout -- .flowguard && git clean -fd .flowguard" in output + errors
    assert directory.is_dir()
    after_files, after_dirs = _project_snapshot(root)
    backup = directory / ".replaced/models/lending.py"
    assert (
        backup.is_file() and backup.read_bytes() == before_files[".flowguard/models/lending.py"][0]
    )
    assert (directory / "models/lending.py").is_file()
    assert "promote stopped:" in output + errors
    # git restore/clean is guidance only: no index, ref, log or object changes.
    assert {p: v for p, v in after_files.items() if p.startswith(".git/")} == {
        p: v for p, v in before_files.items() if p.startswith(".git/")
    }




def test_target_real_proof_dispositions_and_hard_boundaries(tmp_path):
    import json
    import json
    from flowguard.map import target as native
    from flowguard.map.mapfile import load_map
    from flowguard.map.targetfile import build_target_view, load_target

    helpers = _target_life_cycle_fixture_helpers()
    make, stage, snapshot = helpers["make_project"], helpers["stage_target"], helpers["snapshot"]
    prove = helpers["probe_regular_model"]

    # Three related provenance cases share a small fixture, not a result.
    # Every changed artifact is reproved through real run_model_in_process AND a fresh
    # full check_target. No fabricated ModelResult or mocked model runner.
    root = make(tmp_path / "provenance")
    stage(root)
    code_path = root / "shelf/loans.py"
    model_path = root / ".flowguard/target/models/shelf_rule.py"
    original_code, original_model = code_path.read_bytes(), model_path.read_bytes()
    logical_model = root / ".flowguard/models/shelf_rule.py"

    code_path.write_text(
        original_code.decode().replace("value + capacity()", "value + capacity() + 1"),
        encoding="utf-8",
    )
    view = build_target_view(root, load_map(root), load_target(root))
    result = prove(root, logical_model, view=view)
    assert result.status == "fail" and result.code_gaps, result
    assert set(result.code_gaps) <= set(result.problems)
    report = native.check_target(root)
    for message in result.code_gaps:
        assert any(
            f.node == "model shelf_rule" and f.message == message for f in report.todos
        ), report
        assert not any(f.message == message for f in report.errors + report.warnings), report

    code_path.write_bytes(original_code)
    source = original_model.decode()
    assert source.count('return {"advance_twice": make(2)}') == 1
    model_path.write_text(
        source.replace('return {"advance_twice": make(2)}', 'return {"advance_twice": make(1)}'),
        encoding="utf-8",
    )
    view = build_target_view(root, load_map(root), load_target(root))
    result = prove(root, logical_model, view=view)
    assert result.status == "fail" and not result.code_gaps, result
    design_failures = [p for p in result.problems if "known-bad variant" in p and "passed" in p]
    assert design_failures, result
    report = native.check_target(root)
    for message in design_failures:
        assert any(
            f.node == "model shelf_rule" and f.message == message for f in report.errors
        ), report
        assert not any(f.message == message for f in report.todos + report.warnings), report

    partial = original_model.decode().replace("invariants=(RULE,)", "invariants=(RULE, SECOND)")
    partial += (
        '\nTESTED_BY = {"one_loan_step": ["tests/test_shelf.py:test_advance"]}\n'
        'SECOND = Invariant("at_most_one", "no double advance", lambda s,t: s <= 1)\n'
    )
    model_path.write_text(partial, encoding="utf-8")
    partial_model = model_path.read_bytes()
    view = build_target_view(root, load_map(root), load_target(root))
    result = prove(root, logical_model, view=view)
    assert result.status == "pass" and not result.code_gaps and not result.problems, result
    assert any(w.startswith("invariant_untested:") for w in result.warnings), result
    report = native.check_target(root)
    assert not report.errors and not report.todos, report
    assert any(
        f.node == "model shelf_rule" and f.code == "invariant_untested" for f in report.warnings
    ), report
    assert not any(f.code == "invariant_untested" for f in report.errors + report.todos), report
    assert native.main(["check", "--root", str(root)]) == 0
    assert code_path.read_bytes() == original_code and model_path.read_bytes() == partial_model

    # Two actual hard boundaries must remain ERROR, independently of TODO
    # allowances for missing future code. Each case starts from new real files.
    # Full check_target is invoked with its normal model selection; no models
    # flag, runner patch or fabricated Finding/ModelResult supplies a verdict.
    for code in ("owner_dropped", "entrypoint_owner"):
        hard_root = make(tmp_path / ("hard-" + code))
        stage(hard_root, with_model=False)
        target_path = hard_root / ".flowguard/target/map.json"
        draft = json.loads(target_path.read_text(encoding="utf-8"))
        if code == "owner_dropped":
            draft["remove"] = ["component:catalog"]
            draft["components"][0]["depends_on"] = []
            target_path.write_text(json.dumps(draft), encoding="utf-8")
        elif code == "entrypoint_owner":
            draft["components"][0]["entrypoints"].append("shelf/catalog.py:capacity")
            target_path.write_text(json.dumps(draft), encoding="utf-8")
        before = snapshot(hard_root)
        report = native.check_target(hard_root)
        assert any(f.code == code for f in report.errors), (code, report)
        assert not any(f.code == code for f in report.todos + report.warnings), (code, report)
        assert snapshot(hard_root) == before


def test_read_target_changes_skip_computed_coverage(tmp_path, capsys, monkeypatch):
    """A target that adds one entrypoint reports that entrypoint, not recomputed coverage text."""
    import json

    root = shelf_project(tmp_path)
    capsys.readouterr()
    target = json.loads(SHELF_TARGET["map.json"])
    loans = target["components"][0]
    loans["responsibilities"] = loans["responsibilities"][:2]
    loans["state"] = ["current loans"]
    target["goal"] = "one more loans entrypoint"
    (root / ".flowguard/target").mkdir()
    (root / ".flowguard/target/map.json").write_text(
        json.dumps(target, indent=2) + "\n", encoding="utf-8"
    )
    code, output, errors = _static_target_read(root, capsys, monkeypatch, "read", "--target")
    assert code == 0 and not errors, (output, errors)
    changes = [line for line in output.splitlines() if line.strip().startswith("changes:")]
    assert changes and all("coverage" not in line for line in changes), output
    assert any("code + shelf/loans.py:LoanService.hold" in line for line in changes), output
    assert "\n\n\n" not in output


def test_behaviour_target_without_a_rule_is_untied(tmp_path, capsys):
    import json

    root = shelf_project(tmp_path)
    capsys.readouterr()
    path = _target_with(root, capsys, "loans can renew", "loans")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["components"][0]["entrypoints"].append("shelf/loans.py:LoanService.renew")
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert (
        code == 1
        and "ERROR target: target_goal_untied: the target changes a promise (entrypoints: "
        "shelf/loans.py:LoanService.renew)" in output
    ), output
    assert "goal rules: none\n" in output and "target_noop" not in output
    code, output, errors = _run(root, capsys, "target", "add", "lending")
    assert code == 0, (output, errors)
    model = root / ".flowguard/target/models/lending.py"
    source = model.read_text(encoding="utf-8")
    model.write_text(
        source.replace(
            '              Invariant("limit_respected", "a member holds at most LIMIT loans", _limit))',
            '              Invariant("limit_respected", "a member holds at most LIMIT loans", _limit),\n'
            '              Invariant("renewal_keeps_limit", "a renewal never exceeds LIMIT", _limit))',
        ),
        encoding="utf-8",
    )
    from flowguard.map.target import check_target, render_target_report

    output = render_target_report(check_target(root, models=False))  # goal rules are static
    assert (
        "target_goal_untied" not in output
        and "goal rules: model lending: +renewal_keeps_limit" in output
    ), output
    code, shown, errors = _run(root, capsys, "read", "--target")
    assert "goal rules: model lending: +renewal_keeps_limit" in shown, shown


def test_structure_only_target_prints_structure_goal(tmp_path, capsys):
    import json

    root = shelf_project(tmp_path)
    capsys.readouterr()
    path = _target_with(root, capsys, "reword and move", "loans", "catalog")
    data = json.loads(path.read_text(encoding="utf-8"))
    loans, catalog = data["components"]
    loans["summary"] = "Lends books and takes them back."
    code, output, errors = _check_without_writes(root, capsys)
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert "target_goal_untied" not in output and "target_noop" not in output, output
    assert "goal rules: none (no promise changes" in output
    # moving an entrypoint between components keeps the project-wide set
    catalog["entrypoints"].append(loans["entrypoints"].pop())
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert "target_goal_untied" not in output, output
    # retiring an entrypoint explicitly is governed by owner_dropped, not by goal rules
    catalog["entrypoints"].pop()
    data["remove"] = ["entrypoint:shelf/loans.py:LoanService.give_back"]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert (
        "target_goal_untied" not in output and "goal rules: none (no promise changes" in output
    ), output


def test_removed_component_file_hint_says_delete(tmp_path, capsys):
    import json

    root = shelf_project(tmp_path)
    capsys.readouterr()
    path = _target_with(root, capsys, "retire members", "loans")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["remove"] = ["component:members"]
    data["components"][0]["depends_on"].remove("members")
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    unmapped = [
        line
        for line in output.splitlines()
        if line.startswith("TO-DO ") and "file_unmapped" in line and "shelf/members.py" in line
    ]
    assert unmapped and unmapped[0].endswith(
        "(delete the file, or give it an owner in the target)"
    ), output


def test_rule_reading_a_changed_table_is_changed():
    result = _fg403_helpers()["native_case"]("table")
    assert "~answer" in str(result["goal"]) and "EXPECTED GAP one:" in result["text"]


def test_kit_model_binding_edit_prints_no_rule_change():
    result = _fg403_helpers()["native_case"]("kit_binding")
    assert "no rule change: one" in result["text"] and not result["errors"]


def test_kit_feature_table_change_changes_the_rules(tmp_path):
    from flowguard.map import target as native
    from flowguard.map.facets import target_goal_rules
    from flowguard.map.targetfile import load_target

    helpers = _fg403_helpers()
    source = helpers["KIT_SOURCE"]
    helpers["make_project"](tmp_path, source)
    native.start_target(tmp_path, "change a kit feature")
    native.add_to_target(tmp_path, "one")
    (tmp_path / ".flowguard/target/models/one.py").write_text(
        source.replace("lambda value: 1", "lambda value: 2")
    )
    goal = target_goal_rules(tmp_path, load_target(tmp_path))
    assert len(goal) == 1 and "~" in goal[0], goal


@pytest.mark.parametrize("case", ["remove_clean", "remove_gap"])
def test_removed_rule_only_prints_no_rule_change(case):
    result = _fg403_helpers()["native_case"](case)
    assert "no rule change: one" in result["text"]
    assert ("code gap(s) are TO-DO" in result["text"]) == (case == "remove_gap")


def test_name_added_to_two_models_moves_into_one():
    result = _fg403_helpers()["native_case"]("move_twice")
    assert "moved rules only: moved" in result["text"] and "model second: +positive" in str(
        result["goal"]
    )


def test_writes_only_target_prints_no_rule_change(tmp_path):
    from flowguard.map import target as native

    helpers = _fg403_helpers()
    helpers["make_project"](tmp_path, helpers["regular_source"]())
    native.start_target(tmp_path, "declare the write footprint")
    native.add_to_target(tmp_path, "one")
    p = tmp_path / ".flowguard/target/models/one.py"
    p.write_text(p.read_text().replace('name = "Value"', 'name = "Value"\n    writes = ("value",)'))
    text = native.render_target_report(native.check_target(tmp_path))
    assert "no rule change: one" in text and "~answer" not in text


def test_promote_oserror_keeps_replaced_files(tmp_path, monkeypatch, capsys):
    from pathlib import Path

    native = _fg403_clean_target(tmp_path)
    helpers = _fg403_helpers()
    second = tmp_path / ".flowguard/models/moved.py"
    second.write_text(helpers["regular_source"]("moved"))
    staged = tmp_path / ".flowguard/target/models/moved.py"
    staged.write_text(helpers["regular_source"]("moved", positive=True))
    before = (tmp_path / ".flowguard/models/one.py").read_bytes()
    second_before = second.read_bytes()
    write_bytes = Path.write_bytes

    def interrupted(path, content):
        if path == second.with_name("moved.py.tmp"):
            raise OSError("injected second model replacement")
        return write_bytes(path, content)

    monkeypatch.setattr(Path, "write_bytes", interrupted)
    assert native.promote_target(tmp_path) == 2
    assert (tmp_path / ".flowguard/target/.replaced/models/one.py").read_bytes() == before
    assert (tmp_path / ".flowguard/target/.replaced/models/moved.py").read_bytes() == second_before
    assert (tmp_path / ".flowguard/target/models/one.py").is_file()
    text = capsys.readouterr().err
    assert "promote stopped:" in text and "copy them back into .flowguard/ to restore" in text
    assert "git checkout" not in text


def test_shelf_without_git_runs_the_whole_route(tmp_path):
    from flowguard.map import target as native

    helpers = _target_life_cycle_fixture_helpers()
    root = helpers["make_project"](tmp_path / "shelf")
    old = (root / ".flowguard/models/shelf_rule.py").read_bytes()
    assert not (root / ".git").exists()
    helpers["stage_target"](root)
    helpers["edit_missing_method"](root)
    assert not native.check_target(root).errors
    assert (root / ".flowguard/models/shelf_rule.py").read_bytes() == old
    helpers["write_method"](root)
    assert native.promote_target(root) == 0
    assert (root / ".flowguard/models/shelf_rule.py").read_bytes() != old
    assert not (root / ".flowguard/target").exists()


def test_in_place_edit_without_target_is_named(tmp_path):
    from flowguard.map.check import model_edit_findings
    from flowguard.map.common import content_digest

    helpers = _fg403_helpers()
    helpers["make_project"](tmp_path, helpers["regular_source"]())
    p = tmp_path / ".flowguard/models/one.py"
    data = _load_map(tmp_path)
    data["model_digests"] = {".flowguard/models/one.py": content_digest(p)}
    p.write_text(p.read_text() + "\n# unplanned edit\n")
    assert len(model_edit_findings(tmp_path, data, "warn")) == 1
    assert model_edit_findings(tmp_path, data, "error")[0].level == "error"


def test_promote_runs_what_function_selection_reaches(tmp_path):
    """A real direct-calling test outside TESTED_BY must prevent promotion on failure."""
    from flowguard.map import target as native

    helpers = _target_life_cycle_fixture_helpers()
    root = helpers["make_project"](tmp_path / "selection")
    helpers["stage_target"](root)
    helpers["edit_missing_method"](root)
    helpers["write_method"](root)
    path = root / "tests/test_extra.py"
    path.write_text(
        'from shelf.loans import advance\ndef test_extra():\n    advance(0)\n    assert False, "direct caller failed"\n'
    )
    # No git uses the conservative file fallback; this test actually calls an anchor.
    assert native.promote_target(root) == 1
    assert (root / ".flowguard/target").exists()


def test_shelf_port_change_escalates_to_desk(tmp_path, capsys):
    root = target_shelf_project(tmp_path)
    capsys.readouterr()
    assert target__run(root, capsys, "target", "start", "extend lending answer")[0] == 0
    assert target__run(root, capsys, "target", "add", "lending")[0] == 0
    path = root / ".flowguard/target/models/lending.py"
    source = path.read_text()
    old = 'OUTPUTS = {"answer":("lent","refused")}'
    assert old in source
    path.write_text(source.replace(old, 'OUTPUTS = {"answer":("lent","refused","waitlisted")}'))
    code, text, error = target__run(root, capsys, "target", "check")
    assert code == 1 and not error
    assert "port changed: lending out +waitlisted -> verify desk (parent)" in text
    assert "port_changed_parent_missing" in text
    assert target__run(root, capsys, "target", "add", "desk")[0] == 0
    code, text, error = target__run(root, capsys, "target", "check")
    assert code == 1 and not error
    assert "handoff_output_unhandled" in text and "waitlisted" in text

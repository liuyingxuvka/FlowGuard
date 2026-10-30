"""Tests grouped by their model or native component."""
from __future__ import annotations
import json
import os
import pytest
from pathlib import Path




from _fg_helpers import (
    target_OLD_CHILD_MODEL as OLD_CHILD_MODEL,
    target__check_without_writes as _check_without_writes,
    target__fg403_clean_target as _fg403_clean_target,
    target__load_map as _load_map,
    target__rename_return_toward_target as _rename_return_toward_target,
    target__run as _run,
    target__target_life_cycle_fixture_helpers as _target_life_cycle_fixture_helpers,
    target__target_with as _target_with,
    target__write_map as _write_map,
    target_shelf_project as shelf_project,
)

@pytest.mark.usefixtures("_no_model_execution")
def test_target_start_add_drop_and_read_line(tmp_path, capsys):
    import json
    root = shelf_project(tmp_path)
    capsys.readouterr()
    current = _load_map(root)
    loans = next(component for component in current["components"] if component["id"] == "loans")
    loans["_hint"] = "current-only drafting hint"
    _write_map(root, current)
    original_map = (root / ".flowguard/map.json").read_bytes()
    code, check_before, errors = _run(root, capsys, "map", "check")
    assert code == 0 and "0 error(s)" in check_before and not errors

    code, output, errors = _run(root, capsys, "target", "start", "holds")
    assert code == 0 and not errors
    assert 'target started: "holds"' in output
    assert "next: python -m flowguard target add" in output
    directory = root / ".flowguard/target"
    target_path = directory / "map.json"
    assert target_path.is_file() and (directory / "models").is_dir()
    assert json.loads(target_path.read_text(encoding="utf-8")) == {
        "schema": "flowguard.target.v1", "goal": "holds", "components": [], "flows": [], "remove": []}

    code, _, errors = _run(root, capsys, "target", "start", "second goal")
    assert code == 2 and 'a target already exists: "holds"' in errors
    assert "target promote" in errors and "target drop --yes" in errors
    for node, message in (("loans", "added component loans"), ("lending", "added model lending"),
                          ("flow:borrow", "added flow borrow")):
        code, output, errors = _run(root, capsys, "target", "add", node)
        assert code == 0 and message in output and not errors
    target = json.loads(target_path.read_text(encoding="utf-8"))
    assert target["components"] == [{key: value for key, value in loans.items()
                                      if key not in {"status", "fingerprint", "_hint"}}]
    assert target["flows"] == current["flows"]
    assert (directory / "models/lending.py").read_bytes() == (root / ".flowguard/models/lending.py").read_bytes()
    before_errors = target_path.read_bytes()
    code, _, errors = _run(root, capsys, "target", "add", "loans")
    assert code == 2 and "component loans is already in the target" in errors
    code, _, errors = _run(root, capsys, "target", "add", "nope")
    assert code == 2 and "unknown node 'nope'" in errors
    assert "components:" in errors and "loans" in errors and "models:" in errors and "lending" in errors
    assert target_path.read_bytes() == before_errors

    code, output, errors = _run(root, capsys, "read")
    assert code == 0 and not errors
    assert next(line for line in output.splitlines() if line.startswith("target:")).startswith('target: "holds": +0 ~3 -0 nodes')
    code, check_after, errors = _run(root, capsys, "map", "check")
    assert code == 0 and check_after == check_before and not errors
    assert (root / ".flowguard/map.json").read_bytes() == original_map

    target_files = {p.relative_to(directory).as_posix(): p.read_bytes()
                    for p in directory.rglob("*") if p.is_file()}
    code, output, errors = _run(root, capsys, "target", "drop")
    assert code == 1 and not errors and 'would delete .flowguard/target/ ("holds", 3 file(s))' in output
    assert "re-run with --yes" in output
    assert {p.relative_to(directory).as_posix(): p.read_bytes()
            for p in directory.rglob("*") if p.is_file()} == target_files
    code, output, errors = _run(root, capsys, "target", "drop", "--yes")
    assert code == 0 and 'dropped target "holds"' in output and not errors
    assert not directory.exists()
    code, output, errors = _run(root, capsys, "read")
    assert code == 0 and not errors and not any(line.startswith("target:") for line in output.splitlines())
    assert (root / ".flowguard/map.json").read_bytes() == original_map


def test_change_marks_only_planned_breakage_and_keeps_tests(tmp_path, capsys, monkeypatch):
    import json
    import pytest
    from flowguard.map import cli as map_cli
    from flowguard.map import proof

    root = shelf_project(tmp_path)
    capsys.readouterr()
    _rename_return_toward_target(root)
    # Retire the old public name explicitly while keeping the renamed entrypoint.
    target_path = root / ".flowguard/target/map.json"
    target_data = json.loads(target_path.read_text(encoding="utf-8"))
    target_data.setdefault("remove", []).append("entrypoint:shelf/loans.py:LoanService.give_back")
    target_path.write_text(json.dumps(target_data), encoding="utf-8")
    code, output, errors = _run(root, capsys, "map", "check")
    assert code == 0 and not errors, (output, errors)
    assert any("INFO" in line and "moving to target:" in line and "LoanService.give_back" in line
               for line in output.splitlines()), output
    code, strict, errors = _run(root, capsys, "map", "check", "--strict")
    assert code == 1 and "ERROR" in strict and "LoanService.give_back" in strict, (strict, errors)

    original_check = map_cli.check_target
    modes = []

    def static_check(*args, **kwargs):
        modes.append(kwargs.get("models", True))
        return original_check(*args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("change must not execute models or TESTED_BY")

    # This guard covers this actual change only; all FG209 native tests remain real.
    with monkeypatch.context() as scoped:
        scoped.setattr(map_cli, "check_target", static_check)
        for name in ("run_models", "run_model", "run_model_in_process"):
            scoped.setattr(proof, name, forbidden)
        code, output, errors = _run(root, capsys, "change", "shelf/loans.py")
    assert code == 0 and not errors, (output, errors)
    assert modes == [False]
    assert "moving to target: lending" in output
    assert any(line.startswith("run:") and "tests/test_loans.py" in line for line in output.splitlines()), output
    for line in output.splitlines():
        if line.startswith("run: python -m flowguard map models "):
            assert "lending" not in line.split()[6:], line
    assert any(line.startswith('TARGET "') and "0 design error(s)" in line for line in output.splitlines()), output


def test_target_small_promotion_preserves_map_and_model_bytes(tmp_path):
    from flowguard.map import target as native
    from flowguard.map.mapfile import load_map
    from flowguard.map.targetfile import build_target_view, load_target

    helpers = _target_life_cycle_fixture_helpers()
    make, stage, snapshot = helpers["make_project"], helpers["stage_target"], helpers["snapshot"]

    root = make(tmp_path / "promotion")
    stage(root)
    helpers["edit_missing_method"](root)
    report = native.check_target(root)
    assert not report.errors and any(f.code == "anchor_broken" for f in report.todos), report
    before = snapshot(root)
    assert native.promote_target(root) == 1
    assert snapshot(root) == before

    helpers["write_method"](root)
    report = native.check_target(root)
    assert not report.errors and not report.todos, report
    current, draft = load_map(root), load_target(root)
    expected = build_target_view(root, current, draft).data
    expected_models = {name: (root / rel).read_bytes() for name, rel in draft.models.items()}
    assert expected_models and expected_models["shelf_rule.py"] != (root / ".flowguard/models/shelf_rule.py").read_bytes()
    assert native.promote_target(root) == 0
    assert load_map(root) == expected
    assert all((root / ".flowguard/models" / name).read_bytes() == content
               for name, content in expected_models.items())
    assert not (root / ".flowguard/target").exists()
    assert not any(flow["id"] == "borrow" for flow in load_map(root)["flows"])
    loans = next(c for c in load_map(root)["components"] if c["id"] == "loans")
    assert loans["status"] == "draft" and "fingerprint" not in loans


def test_reworded_duty_is_not_owner_dropped(tmp_path, capsys):
    from flowguard.map import target as native

    helpers = _target_life_cycle_fixture_helpers("target_findings")
    root = helpers["make_project"](tmp_path)
    current = _load_map(root)
    current["components"][0]["responsibilities"] = ["place an order once"]
    _write_map(root, current)
    code, output, errors = _run(root, capsys, "map", "confirm", "all")
    assert code == 0 and not errors, (output, errors)
    path = _target_with(root, capsys, "reword the order duty", "component:loans")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["components"][0]["responsibilities"] = ["place each order exactly once"]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _run(root, capsys, "target", "check")
    assert code == 0 and not errors, (output, errors)
    assert "owner_dropped" not in output
    assert any(line.startswith("WARN ") and "responsibility_reworded:" in line
               for line in output.splitlines()), output
    assert ("responsibility 'place an order once' of component loans is reworded as "
            "'place each order exactly once' (advice, not a gate)") in output

    data["components"][0]["responsibilities"] = ["render the shop page"]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _run(root, capsys, "target", "check")
    assert code == 1 and not errors, (output, errors)
    assert any(line.startswith("ERROR ") and "owner_dropped: responsibility 'place an order once'" in line
               for line in output.splitlines()), output
    data["components"][0]["responsibilities"] = ["place each order exactly once"]
    path.write_text(json.dumps(data), encoding="utf-8")
    assert native.promote_target(root) == 0
    assert not (root / ".flowguard/target").exists()


def test_existing_similar_duty_does_not_hide_a_dropped_responsibility(tmp_path):
    from flowguard.map import target as native

    helpers = _target_life_cycle_fixture_helpers("target_findings")
    root = helpers["make_project"](tmp_path)
    current = _load_map(root)
    current["components"][0]["responsibilities"] = [
        "place an order once", "place each order exactly once",
    ]
    _write_map(root, current)
    helpers["stage_target"](root, with_model=False)
    path = root / ".flowguard/target/map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["components"][0]["responsibilities"] = ["place each order exactly once"]
    path.write_text(json.dumps(data), encoding="utf-8")
    report = native.check_target(root)
    assert any(f.code == "owner_dropped" and "responsibility 'place an order once'" in f.message
               for f in report.errors), report
    assert not any(f.code == "responsibility_reworded"
                   for f in report.errors + report.todos + report.warnings), report


def test_dropping_a_responsibility_is_owner_dropped(tmp_path, capsys):
    """A responsibility needs a new owner or an explicit responsibility:<text> retirement."""
    import json
    root = shelf_project(tmp_path)
    capsys.readouterr()
    for arguments in (("target", "start", "loans lends only"), ("target", "add", "loans"), ("target", "add", "catalog")):
        code, output, errors = _run(root, capsys, *arguments)
        assert code == 0 and not errors, (output, errors)
    path = root / ".flowguard/target/map.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    loans = next(component for component in data["components"] if component["id"] == "loans")
    loans["responsibilities"] = ["lend a free copy"]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    dropped = [line for line in output.splitlines() if line.startswith("ERROR ") and "owner_dropped: responsibility" in line]
    assert code == 1 and len(dropped) == 1 and "'take a lent copy back'" in dropped[0], output
    assert '"responsibility:take a lent copy back" in remove' in dropped[0]
    data["remove"] = ["responsibility:take a lent copy back"]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert "owner_dropped" not in output and "target_invalid" not in output, output
    data["remove"] = []
    catalog = next(component for component in data["components"] if component["id"] == "catalog")
    catalog["responsibilities"].append("take a lent copy back")
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert "owner_dropped" not in output, output
    data["remove"] = ["responsibility:no such duty"]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and "target_invalid" in output and "remove names no current node" in output, output


def test_unchanged_target_is_target_noop(tmp_path, capsys):
    root = shelf_project(tmp_path)
    capsys.readouterr()
    _target_with(root, capsys, "copy loans", "loans")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and "ERROR target: target_noop: the target changes nothing yet" in output, output
    before = (root / ".flowguard/map.json").read_bytes()
    code, refused, errors = _run(root, capsys, "target", "promote")
    assert code == 1 and "promote refused:" in refused + errors
    assert (root / ".flowguard/map.json").read_bytes() == before
    code, output, errors = _run(root, capsys, "target", "add", "lending")
    assert code == 0, (output, errors)
    model = root / ".flowguard/target/models/lending.py"
    model.write_text(model.read_text(encoding="utf-8") + "\n# only a comment\n", encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    assert code == 1 and "target_noop" in output, output


def test_copied_but_unchanged_entry_stays_an_error(tmp_path, capsys):
    import json
    root = shelf_project(tmp_path)
    capsys.readouterr()
    path = _target_with(root, capsys, "describe loans better", "loans")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["components"][0]["summary"] = "Lends books to members and takes them back."
    path.write_text(json.dumps(data), encoding="utf-8")
    code_path = root / "shelf/loans.py"
    source = code_path.read_text(encoding="utf-8")
    assert source.count("def give_back(") == 1
    code_path.write_text(source.replace("def give_back(", "def hand_back("), encoding="utf-8")
    code, output, errors = _run(root, capsys, "change")
    broken = [line for line in output.splitlines() if line.split()[1:2] == ["anchor_broken"] and "give_back" in line]
    assert code == 1 and broken and all(line.startswith("ERROR") and "moving to target" not in line for line in broken), output
    data["components"][0]["entrypoints"] = [entry.replace("give_back", "hand_back") for entry in data["components"][0]["entrypoints"]]
    path.write_text(json.dumps(data), encoding="utf-8")
    code, output, errors = _run(root, capsys, "change")
    broken = [line for line in output.splitlines() if line.split()[1:2] == ["anchor_broken"] and "give_back" in line]
    assert broken and all("moving to target: " in line for line in broken), output


def test_old_findings_of_unchanged_models_do_not_block(tmp_path, capsys):
    import json
    import flowguard.__main__ as cli
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import ignore_patterns
    from flowguard.map.target import _unchanged_models
    from flowguard.map.targetfile import build_target_view, load_target
    from flowguard.map.tree import build_tree

    root = shelf_project(tmp_path)
    (root / ".flowguard/models/loan_count.py").write_text(OLD_CHILD_MODEL.replace('MODEL_ID = "loan_count"', 'MODEL_ID = "loan_count"\nimport _lending_bridge').replace('PARENT = "lending"', 'PARENT = "loans"'), encoding="utf-8")
    # This is a two-hop import dependency, not an exclusive parent/child decomposition.
    (root / ".flowguard/models/_lending_bridge.py").write_text("import lending\n", encoding="utf-8")
    assert cli.main(["map", "confirm", "all", "--root", str(root)]) == 0
    path = _target_with(root, capsys, "describe the catalog; one more lending known-bad", "catalog", "lending")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["components"][0]["summary"] = "Counts the free copies of each book."
    path.write_text(json.dumps(data), encoding="utf-8")
    model = root / ".flowguard/target/models/lending.py"
    old = 'return {"lend_always": _explorer(LendAlways()), "no_limit": _explorer(NoLimit())}'
    model.write_text(model.read_text(encoding="utf-8").replace(
        old, old[:-1] + ', "no_limit_again": _explorer(NoLimit())}'), encoding="utf-8")
    # One real check: the old uncovered invariant of the unchanged child is a WARN and promotion stays open.
    code, output, errors = _check_without_writes(root, capsys)
    old_lines = [line for line in output.splitlines() if line.startswith("WARN  model loan_count: old_finding: ")]
    assert code == 0 and len(old_lines) == 1 and "uncovered_invariant: invariant 'never_negative'" in old_lines[0], output
    assert "(already in the current tree; the target does not change this model or its code;" in old_lines[0]
    assert any("(1 old)" in line for line in output.splitlines()) and "next: python -m flowguard target promote" in output

    def classify():
        current = json.loads((root / ".flowguard/map.json").read_text(encoding="utf-8"))
        target = load_target(root)
        view = build_target_view(root, current, target)
        inv = build_inventory(root, ignore_patterns(view.data), write_cache=False)
        tree = build_tree(root, view.data, inv, view=view)
        return _unchanged_models(root, current, target, inv, tree, ["lending", "loan_count"])

    assert classify() == ({"loan_count"}, {"loan_count"})
    # Its anchored code changes: still unchanged by the target, but no longer old (it stays ERROR / TO-DO,
    # with the "model unchanged by the target" note that check_target adds for such models).
    loans = root / "shelf/loans.py"
    loans.write_text(loans.read_text(encoding="utf-8") + "\nLOANS_EDITED = True\n", encoding="utf-8")
    assert classify() == ({"loan_count"}, set())


def test_target_check_warns_about_debts_it_makes_stale(tmp_path, capsys):
    import json
    root = shelf_project(tmp_path)
    data = _load_map(root)
    data["accepted_debts"] = [{"expires": "9999-12-31", "code": "untested_component", "component": "members",
                               "reason": "members are tested through the loans tests"}]
    _write_map(root, data)
    capsys.readouterr()
    path = _target_with(root, capsys, "merge members into loans", "loans", "cli", "flow:borrow")
    target = json.loads(path.read_text(encoding="utf-8"))
    target["remove"] = ["component:members", "entrypoint:shelf/members.py:Members.may_borrow", "state:known members",
                        "responsibility:enforce the loan limit"]
    loans = next(component for component in target["components"] if component["id"] == "loans")
    loans["files"].append("shelf/members.py")
    loans["depends_on"].remove("members")
    target["flows"][0]["steps"] = [step.replace("members:", "loans:", 1) for step in target["flows"][0]["steps"]]
    path.write_text(json.dumps(target), encoding="utf-8")
    code, output, errors = _check_without_writes(root, capsys)
    stale = [line for line in output.splitlines() if line.startswith("WARN ") and "debt_stale" in line]
    assert code == 0 and len(stale) == 1, output
    assert "members are tested through the loans tests" in stale[0]
    assert stale[0].endswith("(remove the debt in the target's accepted_debts)")
    code, output, errors = _run(root, capsys, "target", "promote")
    assert code == 0 and "promoted" in output, (output, errors)


def test_target_check_reports_unwritten_code_as_todo(tmp_path, capsys):
    """An entrypoint the target plans but the code does not have yet is a TO-DO, never an ERROR."""
    import json
    from flowguard.map.target import check_target

    root = shelf_project(tmp_path)
    capsys.readouterr()
    path = _target_with(root, capsys, "loans can renew", "loans")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["components"][0]["entrypoints"].append("shelf/loans.py:LoanService.renew")
    path.write_text(json.dumps(data), encoding="utf-8")
    report = check_target(root, models=False)
    assert any(f.code == "anchor_broken" and "renew" in f.message for f in report.todos), report
    assert not any(f.code == "anchor_broken" for f in report.errors), report


@pytest.mark.parametrize("relative", ["models/shelf_rule.py", "base.json"])
def test_promote_refuses_inputs_changed_after_its_check(tmp_path, capsys, monkeypatch, relative):
    """promote_target checks once; when a checked input changes afterwards it refuses and writes nothing."""
    from pathlib import Path
    from flowguard.map import target as native

    helpers = _target_life_cycle_fixture_helpers()
    root = helpers["make_project"](tmp_path / "promotion")
    helpers["stage_target"](root)
    helpers["edit_missing_method"](root)
    helpers["write_method"](root)
    original = native.check_target

    def check_then_edit(checked_root, **options):
        report = original(checked_root, **options)
        path = Path(checked_root) / ".flowguard/target" / relative
        suffix = "\n# edited after the check\n" if path.suffix == ".py" else "\n "
        path.write_text(path.read_text(encoding="utf-8") + suffix, encoding="utf-8")
        return report

    monkeypatch.setattr(native, "check_target", check_then_edit)
    current = (root / ".flowguard/map.json").read_bytes()
    capsys.readouterr()
    assert native.promote_target(root) == 1
    assert "promote refused: checked inputs changed" in capsys.readouterr().out
    assert (root / ".flowguard/target").is_dir() and (root / ".flowguard/map.json").read_bytes() == current


def test_refused_promote_prints_the_report(tmp_path, monkeypatch, capsys):
    import json
    from flowguard.map import target
    root = shelf_project(tmp_path)
    assert target.start_target(root, "invalid goal case") == 0
    path = root / ".flowguard/target/map.json"
    data = json.loads(path.read_text())
    data["goal"] = ""
    path.write_text(json.dumps(data))
    paths = [root / ".flowguard/map.json", *(root / ".flowguard/models").glob("*.py"), path]
    before = {p: p.read_bytes() for p in paths}
    original, calls = target.check_target, []
    def counted(*args, **kwargs):
        calls.append(True)
        return original(*args, **kwargs)
    monkeypatch.setattr(target, "check_target", counted)
    capsys.readouterr()
    assert target.promote_target(root) == 1
    output = capsys.readouterr().out
    assert "ERROR" in output and "promote refused: 1 error(s), 0 to-do" in output
    assert len(calls) == 1
    assert all(p.read_bytes() == content for p, content in before.items())


def test_target_check_runs_no_pytest_and_promote_runs_one_check(tmp_path, monkeypatch):
    from flowguard.map import proof
    native = _fg403_clean_target(tmp_path)
    original = proof.run_bound_tests
    calls = []
    def counted(*args, **kwargs):
        calls.append(args[1])
        return original(*args, **kwargs)
    monkeypatch.setattr(proof, "run_bound_tests", counted)
    report = native.check_target(tmp_path)
    assert not report.errors and not report.todos and calls == []
    assert "bound tests: not run here; target promote runs them once" in native.render_target_report(report)
    assert native.promote_target(tmp_path) == 0 and len(calls) == 1


def test_promote_next_line_names_target_deletion(tmp_path, capsys):
    import shlex
    import subprocess
    from flowguard.map import target as native

    helpers = _target_life_cycle_fixture_helpers("target_findings")
    root = helpers["make_project"](tmp_path / "项目 space")
    current = _load_map(root)
    current["components"][1]["files"].append("shelf/new*.py")
    _write_map(root, current)
    for name in ("obsolete.txt", "already staged.txt", "notes [x].md"):
        (root / name).write_text("old text\n", encoding="utf-8")
    def git(*args):
        return subprocess.run(["git", "-C", str(root), *args], check=True,
                              capture_output=True, text=True).stdout
    git("init", "-q")
    git("add", ".")
    git("-c", "user.name=probe", "-c", "user.email=probe@example.invalid", "commit", "-qm", "seed")
    helpers["stage_target"](root)
    target_model = root / ".flowguard/target/models/shelf_rule.py"
    target_model.write_text(target_model.read_text() +
                           '\nTESTED_BY = {"one_loan_step": ["tests/test_added.py:test_step"]}\n')
    git("add", ".flowguard/target")
    git("-c", "user.name=probe", "-c", "user.email=probe@example.invalid", "commit", "-qm", "target")
    (root / "shelf/catalog.py").write_text("def capacity():\n    return 1\n\n# current change\n")
    (root / "shelf/new helper.py").write_text("def extra():\n    return 'new helper'\n")
    (root / "tests/test_added.py").write_text("from shelf.loans import advance\ndef test_step():\n    assert advance(0) == 1\n")
    (root / "notes [x].md").write_text("changed text\n", encoding="utf-8")
    (root / "notes x.md").write_text("unrelated note\n", encoding="utf-8")
    (root / "scratch.txt").write_text("unrelated\n", encoding="utf-8")
    (root / "obsolete.txt").unlink()
    git("rm", "-q", "already staged.txt")
    index = root / ".git/index"
    before = index.read_bytes()
    capsys.readouterr()
    assert native.promote_target(root) == 0
    output = capsys.readouterr().out
    assert index.read_bytes() == before, "promote must leave staging to the user"
    last = output.splitlines()[-1]
    prefix = ("next: commit the code, .flowguard/models/, .flowguard/map.json, .flowguard/requests/ "
              "and the deletion of .flowguard/target/ together: ")
    assert last.startswith(prefix), output
    command = last[len(prefix):]
    argv = shlex.split(command)
    assert argv[:3] == ["git", "-C", str(root.resolve())]
    assert "add" in argv and "-A" in argv and "--" in argv and ".flowguard" in argv
    assert "already staged.txt" not in argv
    assert "<code paths>" not in command and " -F " not in command
    # Execute the printed POSIX text on POSIX; Windows checks the same argv.
    result = subprocess.run(command if os.name != "nt" else argv, shell=os.name != "nt",
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    cached = set(git("diff", "--cached", "--name-only", "-z").split("\0"))
    assert {".flowguard/map.json", ".flowguard/models/shelf_rule.py", "shelf/catalog.py",
            "shelf/new helper.py", "tests/test_added.py", "notes [x].md", "obsolete.txt", "already staged.txt"} <= cached
    assert "scratch.txt" not in cached and "notes x.md" not in cached
    assert not git("ls-files", "--", ".flowguard/target")
    assert not any(path.startswith(".flowguard/cache/") for path in cached)


def test_promote_without_git_keeps_usable_next_step(tmp_path, capsys, monkeypatch):
    import shlex
    from flowguard.__main__ import main

    root = tmp_path / "gitless project"
    root.mkdir()
    native = _fg403_clean_target(root)
    capsys.readouterr()
    assert native.promote_target(root) == 0
    output = capsys.readouterr().out
    assert "no Git worktree" in output and "deletion of .flowguard/target/" in output
    argv = shlex.split(output.splitlines()[-1].removeprefix("next: "))
    assert argv[:4] == ["python", "-m", "flowguard", "map"]
    assert argv[4:] == ["check", "--strict", "--root", str(root.resolve())]
    assert "git -C" not in output and " -F " not in output
    assert main(["map", "confirm", "all", "--root", str(root)]) == 0
    monkeypatch.chdir(tmp_path)
    assert main(argv[3:]) == 0


def test_promote_names_stale_component_to_confirm(tmp_path, capsys):
    from flowguard.map.cli import cmd_confirm
    from types import SimpleNamespace
    native = _fg403_clean_target(tmp_path)
    cmd_confirm(tmp_path, SimpleNamespace(ids=["app"]))
    path = tmp_path / "native.py"
    path.write_text(path.read_text() + "\n# source changed after confirmation\n")
    capsys.readouterr()
    assert native.promote_target(tmp_path) == 0
    assert "next: python -m flowguard map confirm app" in capsys.readouterr().out


def test_port_change_without_parent_is_an_error(tmp_path):
    from pathlib import Path
    import runpy
    from flowguard.map.target import check_target
    fixture = runpy.run_path(str(Path(__file__).parents[1]/".flowguard/models/_target_fixture.py"))
    fixture["make_port_project"](tmp_path)
    call = fixture["call_target"]
    assert call(tmp_path,"start","extend lending outputs") == 0
    assert call(tmp_path,"add","lending") == 0
    path = tmp_path/".flowguard/target/models/lending.py"
    path.write_text(path.read_text().replace('("lent","refused")}', '("lent","refused","waitlisted")}'))
    report = check_target(tmp_path,models=False)
    findings = [f for f in report.errors if f.code == "port_changed_parent_missing"]
    assert len(findings) == 1
    assert findings[0].message == "the target changes the port of lending (out +waitlisted) but not its parent desk; python -m flowguard target add desk, then make desk receive 'waitlisted' (a CHECK step that takes it; with a full-form HANDOFF entry, also map it there)"
    assert not (tmp_path/".flowguard/target/models/desk.py").exists()
    assert call(tmp_path,"add","desk") == 0
    assert not any(f.code == "port_changed_parent_missing" for f in check_target(tmp_path,models=False).errors)


def test_changed_port_fails_short_form_consumer(tmp_path, capsys):
    import runpy
    from pathlib import Path
    from flowguard.map import cli, target
    directory = Path(__file__).resolve().parents[1] / '.flowguard'
    fixture = directory / 'target/models/_target_fixture.py'
    if not fixture.exists():
        fixture = directory / 'models/_target_fixture.py'
    runpy.run_path(str(fixture))['make_port_project'](tmp_path, 'short_consumer')
    assert cli.main(['confirm', 'all', '--root', str(tmp_path)]) == 0
    assert target.main(['start', 'extend producer outputs', '--root', str(tmp_path)]) == 0
    assert target.main(['add', 'lending', '--root', str(tmp_path)]) == 0
    path = tmp_path / '.flowguard/target/models/lending.py'
    source = path.read_text()
    assert source.count('("lent","refused")}') == 1
    path.write_text(source.replace('("lent","refused")}', '("lent","refused","waitlisted")}'))
    capsys.readouterr()
    assert target.main(['check', '--root', str(tmp_path)]) == 1
    output = capsys.readouterr().out
    assert "ERROR model consumer: port_changed_consumer_unhandled: lending emits answer='waitlisted'; consumer never receives it and is not in the target; python -m flowguard target add consumer, then make consumer receive 'waitlisted'" in output
    assert 'old_finding' not in output
    current = tmp_path / '.flowguard/map.json'
    before = current.read_bytes()
    assert target.main(['promote', '--root', str(tmp_path)]) == 1
    assert 'promote refused:' in capsys.readouterr().out
    assert current.read_bytes() == before


def test_target_check_runs_own_bound_tests_after_code(tmp_path, monkeypatch):
    from flowguard.map import proof, target as native
    helpers = __import__("runpy").run_path(str(Path(__file__).parents[1] / ".flowguard/models/_gap_cases.py"))
    helpers["make_project"](tmp_path, helpers["regular_source"]())
    native.start_target(tmp_path, "raise the answer and check its own tests")
    native.add_to_target(tmp_path, "one")
    model = tmp_path / ".flowguard/target/models/one.py"
    source = helpers["regular_source"](expected=2, positive=True)
    source = source.replace("TESTED_BY = {}", 'TESTED_BY = {"positive": ["tests/test_native.py:test_value"]}')
    model.write_text(source)
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_native.py").write_text("from native import value\ndef test_value(): assert value() == 2\n")
    calls = []
    actual = proof.run_bound_tests

    def counted(*args, **kwargs):
        calls.append(True)
        return actual(*args, **kwargs)

    monkeypatch.setattr(proof, "run_bound_tests", counted)
    report = native.check_target(tmp_path)
    assert not report.errors and report.todos and calls == []
    path = tmp_path / "native.py"
    path.write_text(path.read_text().replace("def value(): return 1", "def value(): return 2"))
    report = native.check_target(tmp_path)
    assert not report.errors and not report.todos
    assert len(calls) == 1
    output = native.render_target_report(report)
    assert "GAP CLOSED one:" in output and "native.py" in output
    assert "bound tests: ran for one" in output
    base = tmp_path / ".flowguard/target/base.json"
    # A damaged design identity is not an execution result. With no staged
    # helpers, fresh proof still succeeds; promotion now watches its bytes for races.
    base.write_text("not JSON: this is no stored execution verdict")
    assert native.promote_target(tmp_path) == 0
    assert len(calls) == 2
    assert not (tmp_path / ".flowguard/target/base.json").exists()

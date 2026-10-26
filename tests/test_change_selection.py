"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_impact_shared_test_binding_and_unknown_helper(impact_project):
    from _fg_helpers import map_impact_of as impact_of
    root, data = impact_project
    data["components"][2]["tests"].append("tests/test_orders.py")
    imp = impact_of(root, data, ["tests/test_orders.py"])
    assert imp.direct == [] and imp.dependents == []
    assert imp.tests == ["tests/test_orders.py"]
    assert imp.model_ids == []
    unknown = impact_of(root, data, [".flowguard/models/owners/unbound/helper.py"])
    assert unknown.blocked and not unknown.models and not unknown.model_ids


@pytest.mark.parametrize("edit", ["comment", "docstring", "code", "untouched"])
@pytest.mark.parametrize("line_endings", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_comment_only_edit_keeps_review_but_selects_no_checks(impact_project, edit, line_endings):
    from _fg_helpers import map_impact_of as impact_of
    from flowguard.map.impact import render_impact
    root, data = impact_project
    path = root / "shop/storage.py"
    text = path.read_text(encoding="utf-8")
    edited = {"comment": text.replace("DB = {}\n", "DB = {}  # in-memory store\n\n"),
              "docstring": '"""Order storage."""\n' + text,
              "code": text.replace("return x", "return x or None"),
              "untouched": text}[edit]
    path.write_bytes(edited.replace("\n", line_endings).encode("utf-8"))
    imp = impact_of(root, data, ["shop/storage.py"], base="HEAD", broad=True)
    assert imp.direct == ["storage"]
    if edit == "comment":
        assert imp.comment_only == ["shop/storage.py"] and "comment-only edits" in render_impact(imp)
        assert imp.dependents == [] and imp.tests == [] and imp.models == []
    else:
        assert imp.comment_only == [] and imp.dependents == ["api", "orders"]
        assert "tests/test_storage.py" in imp.tests and "orders_check" in imp.model_ids


@pytest.mark.parametrize('changed,expected,tests', [
    ('child.py', {'child', 'parent'}, ['tests/test_child.py']),
    ('_shared.py', {'child', 'parent'}, []),
    ('_leaf.py', {'child', 'parent'}, []),
    ('grand.py', {'grand', 'parent'}, ['tests/test_grand.py']),
    ('parent.py', {'parent'}, ['tests/test_parent.py']),
    ('_unused.py', set(), []),
])
def test_change_selects_importers_and_ancestors_of_a_changed_model(impact_project, changed, expected, tests):
    from _fg_helpers import map_write as write, map_impact_of as impact_of
    root, data = impact_project
    for mid in ('parent', 'child', 'grand'):
        content = (f'MODEL_ID = {mid!r}\nIMPLEMENTED_BY = {{"Probe": "tests/test_{mid}.py:test_safe"}}\ndef conformance(): pass\n'
                   f'TESTED_BY = {{"safe": ["tests/test_{mid}.py:test_safe"]}}\ndef build_explorer(): pass\n')
        content += {'parent': 'import child\nimport _shared\n', 'child': 'from _shared import VALUE\n',
                    'grand': 'PARENT = "parent"\n'}[mid]
        write(root, f'.flowguard/models/{mid}.py', content)
        write(root, f'tests/test_{mid}.py', 'def test_safe(): assert True\n')
    write(root, '.flowguard/models/_shared.py', 'PARENT = None\nfrom _leaf import VALUE\n')
    write(root, '.flowguard/models/_leaf.py', 'VALUE = 1\n')
    write(root, '.flowguard/models/_unused.py', 'VALUE = 2\n')
    path = '.flowguard/models/' + changed
    impact = impact_of(root, data, [path], broad=True)
    assert set(impact.model_ids) == expected
    assert impact.tests == tests  # added importers/ancestors do not add their TESTED_BY tests
    assert not impact.direct and not impact.dependents and not impact.blocked
    assert impact.no_checks == ([path] if changed == '_unused.py' else [])


    # Reverse model imports remain selected even without the broad ancestry loop.
    direct = impact_of(root, data, [path])
    if changed in {"child.py", "_shared.py", "_leaf.py"}:
        assert {"child", "parent"} <= set(direct.model_ids)


def test_change_selects_models_whose_anchors_the_edit_calls(tmp_path, capsys):
    """Editing a file that calls another component's anchored code selects that model and its tests."""
    import flowguard.__main__ as flowguard_cli
    from _fg_helpers import target_shelf_project as shelf_project

    root = shelf_project(tmp_path)
    capsys.readouterr()
    path = root / "shelf/cli.py"
    original = path.read_text(encoding="utf-8")
    path.write_text(original + "X = 1\n", encoding="utf-8")
    flowguard_cli.main(["change", "--root", str(root)])
    output = capsys.readouterr().out
    assert "relies on: lending via loans:LoanService.borrow" in output, output
    assert "models to run: -" in output, output
    path.write_text(original + "# a comment only\n", encoding="utf-8")
    flowguard_cli.main(["change", "--root", str(root)])
    assert "models to run: -" in capsys.readouterr().out


def test_change_selects_the_model_of_a_flow_whose_step_changed(impact_project):
    """A flow's model protects every step: editing a step's file selects it, a comment does not."""
    from _fg_helpers import map_write as write, map_save as save, map_impact_of as impact_of, map_git as git
    root, data = impact_project
    write(root, "shop/jobs.py", "def run():\n    return 'done'\n")
    write(root, ".flowguard/models/journey.py", 'MODEL_ID = "journey"\nCOMPONENTS = ["storage"]\n'
          'IMPLEMENTED_BY = {"save": "shop/storage.py:save"}\ndef build_explorer(): pass\ndef conformance(): pass\n')
    data["components"].append({"id": "jobs", "summary": "jobs", "responsibilities": ["run jobs"], "files": ["shop/jobs.py"],
                               "entrypoints": ["shop/jobs.py:run"], "depends_on": [], "tests": [], "models": [],
                               "status": "draft", "layer": data["components"][0].get("layer", "")})
    data.setdefault("flows", []).append({"id": "chain", "summary": "store then run the job",
                                         "steps": ["storage:save", "jobs:run reads out.json"],
                                         "model": ".flowguard/models/journey.py"})
    save(root, data)
    git(root, "add", "-A")
    git(root, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "flow chain")
    from flowguard.map.impact import render_impact
    path = root / "shop/jobs.py"
    path.write_text("def run():\n    return 'finished'\n", encoding="utf-8")
    impact = impact_of(root, data, ["shop/jobs.py"], base="HEAD")
    assert "journey" in impact.model_ids, impact
    assert "flow chain: step 2 changed; model journey" in render_impact(impact)
    path.write_text("def run():\n    return 'done'\n# a comment\n", encoding="utf-8")
    assert "journey" not in impact_of(root, data, ["shop/jobs.py"], base="HEAD").model_ids


def test_change_lists_unexplained_functions_of_changed_files(tmp_path, capsys):
    """A real edit lists the edited file's unexplained entrypoints; the exit code does not change."""
    import flowguard.__main__ as flowguard_cli
    from _fg_helpers import target_shelf_project as shelf_project

    root = shelf_project(tmp_path)
    capsys.readouterr()
    path = root / "shelf/members.py"
    original = path.read_text(encoding="utf-8")
    path.write_text(original + "\nLIMIT_NOTE = 'members may borrow up to the limit'\n", encoding="utf-8")
    code = flowguard_cli.main(["change", "--root", str(root)])
    output = capsys.readouterr().out
    assert "UNEXPLAINED members: shelf/members.py:Members.may_borrow (entrypoint)" in output, output
    path.write_text(original + "# a comment only\n", encoding="utf-8")
    comment_code = flowguard_cli.main(["change", "--root", str(root)])
    assert "UNEXPLAINED" not in capsys.readouterr().out
    assert code == comment_code

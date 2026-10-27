"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_owned_edit_does_not_select_composing_parent(tmp_path):
    from _fg_helpers import map_function_fixture as function_fixture
    helper=function_fixture()
    for case in ('body','helper'):
        root=tmp_path/case;root.mkdir()
        impact=helper['native_case'](root,case)
        assert impact.model_ids==['child']
        assert 'parent' not in impact.model_ids


def test_module_binding_change_selects_importer_functions(tmp_path):
    from _fg_helpers import map_function_fixture as function_fixture
    from flowguard.map.impact import render_impact
    impact=function_fixture()['native_case'](tmp_path,'binding')
    assert 'importer' in impact.model_ids
    assert 'api.py:call' in impact.changed_functions
    assert 'UNCERTAIN: core.py' not in render_impact(impact)


def test_removed_function_is_uncertain(tmp_path):
    from _fg_helpers import map_function_fixture as function_fixture
    from flowguard.map.impact import render_impact
    impact=function_fixture()['native_case'](tmp_path,'removed')
    assert impact.model_ids and impact.uncertain_files['core.py']
    assert 'UNCERTAIN: core.py:' in render_impact(impact)


def test_no_git_uses_stale_components(tmp_path):
    from _fg_helpers import map_function_fixture as function_fixture
    from flowguard.map.impact import render_impact
    impact=function_fixture()['native_case'](tmp_path,'no_git')
    assert impact.tests==['tests/test_core.py']
    assert impact.changed==['core.py']
    assert 'NO GIT: changed files = the files of 1 component(s)' in render_impact(impact)
    assert 'a test file edited alone is not seen: run it by path' in render_impact(impact)


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

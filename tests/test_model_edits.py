"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path

from _fg_helpers import target__target_life_cycle_fixture_helpers as model_fixture


def test_in_place_edit_of_staged_model_refused(tmp_path, capsys):
    import shlex
    from flowguard.__main__ import main
    from flowguard.map import target as native
    from flowguard.map.mapfile import load_map, model_digests

    root = model_fixture("target_findings")["make_project"](tmp_path / "guard project")
    current = load_map(root)
    current["model_digests"] = model_digests(root)
    (root / ".flowguard/map.json").write_text(json.dumps(current))
    assert native.start_target(root, "retain a model edit") == 0
    assert native.add_to_target(root, "shelf_rule") == 0
    copied = root / ".flowguard/target/models/shelf_rule.py"
    copied.write_text(copied.read_text() + "\nTARGET_REVISION = 2\n")
    healthy = native.check_target(root)
    assert not healthy.errors and not healthy.todos, healthy
    path = root / ".flowguard/models/shelf_rule.py"
    path.write_text(path.read_text() + "\nCURRENT_INTENT = 'retain this edit'\n")
    watched = [path, copied, root / ".flowguard/map.json", root / ".flowguard/target/map.json"]
    before = {file: file.read_bytes() for file in watched}
    capsys.readouterr()
    for strict in (False, True):
        args = ["map", "check", "--root", str(root)] + (["--strict"] if strict else [])
        assert main(args) == 1
        output = capsys.readouterr().out
        assert "ERROR" in output and "model_edited_outside_target" in output
        assert str(path.resolve()) in output and str(copied.resolve()) in output
        assert "git -C " + shlex.quote(str(root.resolve())) in output
    report = native.check_target(root)
    assert any(f.code == "model_edited_outside_target" for f in report.errors), report
    assert native.promote_target(root) == 1
    assert "model_edited_outside_target" in capsys.readouterr().out
    assert all(file.read_bytes() == content for file, content in before.items())
    assert "CURRENT_INTENT" in path.read_text() and "CURRENT_INTENT" not in copied.read_text()


def test_map_check_names_model_edited_outside_target(tmp_path):
    from flowguard.map.inventory import build_inventory
    from flowguard.map.check import run_check
    from flowguard.map.common import content_digest
    from flowguard.map.inventory import build_inventory
    directory = tmp_path / ".flowguard/models"
    directory.mkdir(parents=True)
    path = directory / "one.py"
    path.write_text('MODEL_ID = "one"\n')
    data = {"schema": "flowguard.map.v1", "components": [], "model_digests": {".flowguard/models/one.py": content_digest(path)}}
    inv = build_inventory(tmp_path, [])
    def guards(strict=False):
        return [f for f in run_check(tmp_path, data, inv, strict=strict) if f.code == "model_edited_outside_target"]
    assert guards() == []
    from flowguard.map.mapfile import fingerprint
    (tmp_path / "app.py").write_text("def run(): return 1\n")
    pointer = fingerprint(tmp_path, ["app.py"])
    path.write_text(path.read_text() + "# modified\n")
    assert fingerprint(tmp_path, ["app.py"]) == pointer  # the model digest, not the code pointer, changes

    assert len(guards()) == 1 and guards()[0].level == "warn"
    assert len(guards(True)) == 1 and guards(True)[0].level == "error"
    del data["model_digests"]
    assert guards() == []

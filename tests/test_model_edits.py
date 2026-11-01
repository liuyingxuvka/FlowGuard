"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path

from _fg_helpers import target__target_life_cycle_fixture_helpers as model_fixture


@pytest.mark.parametrize("git_backed", [False, True])
def test_in_place_edit_of_staged_model_refused(tmp_path, capsys, git_backed):
    import shlex
    import subprocess
    from flowguard.__main__ import main
    from flowguard.map import target as native
    from flowguard.map.mapfile import load_map, model_digests

    root = model_fixture("target_findings")["make_project"](tmp_path / "guard project")
    current = load_map(root)
    current["model_digests"] = model_digests(root)
    (root / ".flowguard/map.json").write_text(json.dumps(current))
    if git_backed:
        for arguments in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "base"]):
            subprocess.run(["git", "-c", "user.name=probe", "-c", "user.email=probe@example.invalid",
                            "-C", str(root), *arguments], check=True, capture_output=True)
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
        if git_backed:
            assert "git -C " + shlex.quote(str(root.resolve())) in output
        else:  # a folder without Git gets no Git command to restore the file
            assert "git " not in output and "from the copy, archive or backup" in output, output
    report = native.check_target(root)
    assert any(f.code == "model_edited_outside_target" for f in report.errors), report
    assert native.promote_target(root) == 1
    assert "model_edited_outside_target" in capsys.readouterr().out
    assert all(file.read_bytes() == content for file, content in before.items())
    assert "CURRENT_INTENT" in path.read_text() and "CURRENT_INTENT" not in copied.read_text()


def test_in_place_edit_of_staged_helper_refused(tmp_path, capsys):
    from flowguard.__main__ import main
    from flowguard.map import target as native
    from flowguard.map.mapfile import load_map, model_digests

    root = model_fixture("target_findings")["make_project"](tmp_path / "helper project")
    helper = root / ".flowguard/models/_local_helper.py"
    helper.write_text('VALUE = "original"\n')
    data = load_map(root)
    data["model_digests"] = model_digests(root)
    assert helper.relative_to(root).as_posix() not in data["model_digests"]
    (root / ".flowguard/map.json").write_text(json.dumps(data))
    assert native.start_target(root, "retain helper intent") == 0
    assert native.add_to_target(root, "shelf_rule") == 0
    copied = root / ".flowguard/target/models/_local_helper.py"
    copied.write_bytes(helper.read_bytes())
    model = root / ".flowguard/target/models/shelf_rule.py"
    model.write_text(model.read_text() + "\nTARGET_REVISION = 2\n")
    healthy = native.check_target(root)
    assert not healthy.errors and not healthy.todos, healthy
    helper.write_text('VALUE = "current intent"\n')
    watched = [helper, copied, model, root / ".flowguard/map.json", root / ".flowguard/target/map.json"]
    before = {path: path.read_bytes() for path in watched}
    capsys.readouterr()
    for strict in (False, True):
        args = ["map", "check", "--root", str(root)] + (["--strict"] if strict else [])
        assert main(args) == 1
        output = capsys.readouterr().out
        assert "ERROR" in output and "model_edited_outside_target" in output
        assert str(helper.resolve()) in output and str(copied.resolve()) in output
    assert native.promote_target(root) == 1
    assert "model_edited_outside_target" in capsys.readouterr().out
    assert all(path.read_bytes() == content for path, content in before.items())


def test_staged_helper_presence_and_legacy_identity(tmp_path):
    from flowguard.map.check import model_edit_findings
    from flowguard.map.mapfile import MapError, load_map
    from flowguard.map.target import start_target

    root = model_fixture("target_findings")["make_project"](tmp_path)
    data = load_map(root)  # Helper protection does not require public model digests.
    helper = root / ".flowguard/models/_existing.py"
    helper.write_bytes(b'VALUE = "original"\r\n')
    assert not model_edit_findings(root, data)
    assert start_target(root, "change helper safely") == 0
    copied = root / ".flowguard/target/models/_existing.py"
    copied.write_bytes(helper.read_bytes())
    added = root / ".flowguard/models/_new.py"
    target_added = root / ".flowguard/target/models/_new.py"
    target_added.write_text("NEW = True\n")
    helper.write_bytes(b'VALUE = "original"\n')
    assert not model_edit_findings(root, data)  # Source newline equivalence and target-only creation.
    added.write_bytes(target_added.read_bytes())
    assert all(f.level == "error" for f in model_edit_findings(root, data))
    assert model_edit_findings(root, data)
    added.unlink()
    helper.unlink()
    assert model_edit_findings(root, data)  # Deleting a captured helper is an edit too.
    helper.write_bytes(copied.read_bytes())
    target_added.unlink()
    base = root / ".flowguard/target/base.json"
    identity = json.loads(base.read_text())
    # A base without a helper baseline (an older or damaged target) is refused, never guessed from the copy.
    for broken in ({key: value for key, value in identity.items() if key != "helpers"},
                   {**identity, "schema": "unrecognized.target-base"}):
        base.write_text(json.dumps(broken))
        with pytest.raises(MapError, match="restart the target"):
            model_edit_findings(root, data)


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

    assert len(guards()) == 1 and guards()[0].level == "info"
    assert len(guards(True)) == 1 and guards(True)[0].level == "info"
    del data["model_digests"]
    assert guards() == []

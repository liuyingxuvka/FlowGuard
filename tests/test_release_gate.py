"""Focused release checks for the target promotion/commit seam."""
import json

from _fg_helpers import (
    map_git as git,
    flowguard_map_contracts421_project as basic_project,
)


def test_release_refuses_deleted_unstaged_target(tmp_path, capsys):
    from flowguard.__main__ import main

    basic_project(tmp_path)
    assert main(["map", "confirm", "all", "--root", str(tmp_path)]) == 0
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "user.name=probe", "-c", "user.email=probe@example.invalid", "commit", "-qm", "seed")
    assert main(["target", "start", "describe app", "--root", str(tmp_path)]) == 0
    assert main(["target", "add", "component:app", "--root", str(tmp_path)]) == 0
    path = tmp_path / ".flowguard/target/map.json"
    data = json.loads(path.read_text())
    data["components"][0]["summary"] = "Serve the application answer"
    path.write_text(json.dumps(data))
    git(tmp_path, "add", ".flowguard/target")
    git(tmp_path, "-c", "user.name=probe", "-c", "user.email=probe@example.invalid", "commit", "-qm", "target")
    assert main(["target", "promote", "--root", str(tmp_path)]) == 0
    assert main(["map", "confirm", "all", "--root", str(tmp_path)]) == 0
    capsys.readouterr()
    assert main(["release", "--shards", "1", "--root", str(tmp_path)]) == 1
    output = capsys.readouterr().out
    assert "target_deleted_not_staged: .flowguard/target/ files are deleted on disk but still committed" in output
    assert "suite: not run" in output and "verify: FAIL" in output
    git(tmp_path, "add", "-A", ".flowguard")
    assert main(["release", "--root", str(tmp_path)]) == 0



def test_open_target_is_release_warning(tmp_path, capsys):
    from flowguard.__main__ import main

    basic_project(tmp_path)
    assert main(["map", "confirm", "all", "--root", str(tmp_path)]) == 0
    assert main(["target", "start", "open app", "--root", str(tmp_path)]) == 0
    assert main(["target", "add", "component:app", "--root", str(tmp_path)]) == 0
    path = tmp_path / ".flowguard/target/map.json"
    data = json.loads(path.read_text())
    data["components"][0]["summary"] = "A planned app description"
    path.write_text(json.dumps(data))
    capsys.readouterr()
    assert main(["release", "--root", str(tmp_path)]) == 0
    assert capsys.readouterr().out.splitlines()[0] == ('warning: target "open app" exists: release checks only the current tree; '
                                                    'promote or drop the target before releasing')

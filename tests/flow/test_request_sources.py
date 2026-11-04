"""Flow checks and static status agree on registered owner requests."""
from __future__ import annotations

import pytest

from flowguard.__main__ import main
from flowguard.flow.project import request_line, unstored_sources
from flowguard.map.requests import store_request

from checkrun import run_check


MODEL = '''
from flowguard.flow import Model
m = Model("lamp")
m.field("on", [False, True], False)

@m.action(source="R11")
def flip(s):
    s["on"] = not s["on"]
MODEL = m
'''


@pytest.mark.parametrize("has_git", [False, True])
def test_handwritten_request_is_unstored_in_check_and_status(project, capsys, has_git):
    if has_git:
        project.git("init", "-q")
    body = project.file(".flowguard/requests/R11.md", "Hand-written words without registration.\n")
    project.flow("lamp", MODEL)
    before = body.read_bytes()

    checked = run_check(project.root)
    assert checked.code == 0, checked.out + checked.err
    assert "source 'R11' is not a stored request" in checked.out
    assert "R11 is not stored" in checked.out and "req add" in checked.out
    assert main(["status", "--root", str(project.root)]) == 0
    status = capsys.readouterr().out
    assert "R11 is not stored" in status and "req add" in status
    for text in (checked.out, status):
        assert "does not exist" not in text
        assert "git checkout" not in text
        assert "Hand-written words" not in text
    assert body.read_bytes() == before
    assert not body.with_suffix(".json").exists()
    assert request_line(project.root, "R11") is None


def test_registered_request_is_used_without_a_source_warning(project, capsys):
    store_request(project.root, b"The lamp may flip.\n", identifier="R11")
    assert request_line(project.root, "R11") == "The lamp may flip."
    assert unstored_sources(project.root, [("lamp", {"R11": ["action flip"]})]) == []
    assert main(["status", "--root", str(project.root)]) == 0
    text = capsys.readouterr().out
    assert "The lamp may flip." in text and "req add" not in text


@pytest.mark.parametrize("damage", ["body", "missing_sidecar"])
def test_damage_to_a_registered_request_retains_restore_guidance(project, capsys, damage):
    project.git("init", "-q")
    store_request(project.root, b"Original registered words.\n", identifier="R11")
    project.commit()
    body = project.root / ".flowguard/requests/R11.md"
    if damage == "body":
        body.write_text("Changed words.\n", encoding="utf-8")
    else:
        body.with_suffix(".json").unlink()
    assert main(["status", "--root", str(project.root)]) == 0
    text = capsys.readouterr().out
    assert "restore its original bytes" in text and "checkout" in text
    assert "R11 is not stored" not in text and "req add" not in text
    assert "Changed words." not in text and "Original registered words." not in text

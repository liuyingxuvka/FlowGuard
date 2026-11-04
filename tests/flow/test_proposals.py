"""An explicit setting proposal is usable for design, visible until code sync, and not releasable."""
from __future__ import annotations

import json
import subprocess
import sys

from checkrun import env, run_check


def proposal_project(project, *, source='source="R12"'):
    project.request("R12", "Try limit 3, then update the code before release.\n")
    project.file("config.py", "class Config:\n    limit = 4\n")
    project.file("app.py", "from config import Config\n\nclass App:\n    def limit(self):\n        return Config.limit\n")
    project.flow("m", f'''
        from flowguard.flow import Model
        m = Model("proposal", covers=["app.py:App"], config="config:Config")
        m.setting("limit", 3, propose=True{", " + source if source else ""})
        m.field("on", [False, True], False)
        @m.action()
        def toggle(s):
            s["on"] = not s["on"]
        MODEL = m
        ''')
    return project


def command(project, *args):
    return subprocess.run([sys.executable, "-m", "flowguard", *args], cwd=project.root,
                          capture_output=True, text=True, env=env(), timeout=120)


def test_a_proposed_setting_is_advisory_but_stays_visible_and_blocks_release(project):
    proposal_project(project)
    check = run_check(project.root, "--json")
    assert check.code == 0, check.out + check.err
    [proposal] = check.data["setting_proposals"]
    assert proposal == {"model": "m", "name": "limit", "value": 3, "code_value": 4,
                        "source": "R12", "where": "config.py: Config.limit"}
    assert check.data["conflicts"] == [] and check.data["errors"] == []
    text = run_check(project.root)
    assert text.code == 0 and "proposed setting m: limit=3; code 4" in text.out
    stored = json.loads((project.root / ".flowguard/conflicts.json").read_text())
    assert stored["models"]["m"]["setting_proposals"] == [{k: v for k, v in proposal.items() if k != "model"}]
    status = command(project, "status")
    assert status.returncode == 0, status.stdout + status.stderr
    assert "proposed setting m: limit=3; code 4" in status.stdout
    release = command(project, "release")
    assert release.returncode == 1, release.stdout + release.stderr
    assert "proposed setting m: limit=3; code 4" in release.stdout + release.stderr


def test_code_sync_removes_the_proposal_and_allows_release(project):
    proposal_project(project)
    before = run_check(project.root, "--json")
    assert before.code == 0 and before.data["setting_proposals"]
    project.file("config.py", "class Config:\n    limit = 3\n")
    after = run_check(project.root, "--json")
    assert after.code == 0, after.out + after.err
    assert after.data["setting_proposals"] == []
    stored = json.loads((project.root / ".flowguard/conflicts.json").read_text())
    assert stored["models"]["m"]["setting_proposals"] == []
    status = command(project, "status")
    assert status.returncode == 0, status.stdout + status.stderr
    assert "proposed setting" not in status.stdout
    release = command(project, "release")
    assert release.returncode == 0, release.stdout + release.stderr
    assert "proposed setting" not in release.stdout + release.stderr


def test_an_explicit_proposal_without_a_source_is_a_model_error(project):
    proposal_project(project, source="")
    check = run_check(project.root, "--json")
    assert check.code == 2, check.out + check.err
    assert "a proposal needs an explicit value and source= request" in check.out

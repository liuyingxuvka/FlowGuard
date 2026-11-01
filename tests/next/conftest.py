"""Fixtures of the next-engine tests: temp projects and a hash-seed runner."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

HERE = Path(__file__).parent
DATA = HERE / "data"
REPO = HERE.parent.parent


class Project:
    """A temp FlowGuard project: .flowguard/flow, requests, any code files, optional git."""

    def __init__(self, root: Path):
        self.root = root
        (root / ".flowguard" / "flow").mkdir(parents=True)
        (root / ".flowguard" / "requests").mkdir(parents=True)

    def file(self, rel, text):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip("\n"), encoding="utf-8")
        return path

    def flow(self, name, text):
        return self.file(f".flowguard/flow/{name}.py", text)

    def flow_from(self, src: Path, name=None):
        dest = self.root / ".flowguard" / "flow" / f"{name or src.stem}.py"
        shutil.copy(src, dest)
        return dest

    def request(self, rid, text):
        return self.file(f".flowguard/requests/{rid}.md", text)

    def kit(self):
        """The small kit's settings and covered class, and its stored requests."""
        shutil.copytree(DATA / "kit" / "counter", self.root / "counter")
        for p in (DATA / "kit" / "requests").glob("*.md"):
            shutil.copy(p, self.root / ".flowguard" / "requests" / p.name)
        return self

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True,
                       env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})

    def commit(self, message="snapshot"):
        if not (self.root / ".git").exists():
            self.git("init", "-q")
        self.git("add", "-A")
        self.git("commit", "-qm", message)


@pytest.fixture
def project(tmp_path):
    return Project(tmp_path / "proj")


@pytest.fixture(autouse=True)
def _no_mv(monkeypatch):
    monkeypatch.delenv("MV", raising=False)          # e7_mach_sonnet1_R9 reads it


_SEED_SCRIPT = """
import json, sys
from pathlib import Path
from flowguard._next.model import load_model
from flowguard._next.checks import check_model
from flowguard._next.explore import Bounds
root, path = Path(sys.argv[1]), Path(sys.argv[2])
report = check_model(load_model(path, root), Bounds(int(sys.argv[3])))
print(json.dumps([[f.cls, f.kind, f.subject, f.id, list(f.sources)] for f in report.findings]))
"""


def findings_under_seeds(root: Path, path: Path, seeds=(0, 1, 2), max_states=200_000):
    """The findings of one model checked in fresh processes under several hash seeds."""
    out = []
    for seed in seeds:
        env = {**os.environ, "PYTHONHASHSEED": str(seed), "PYTHONPATH": str(REPO)}
        env.pop("MV", None)
        res = subprocess.run([sys.executable, "-c", _SEED_SCRIPT, str(root), str(path), str(max_states)],
                             capture_output=True, text=True, env=env, timeout=300)
        assert res.returncode == 0, res.stderr
        out.append(json.loads(res.stdout))
    return out

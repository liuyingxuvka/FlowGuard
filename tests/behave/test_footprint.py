"""Execution facts invalidate on actual file, directory and engine content."""

import json
import sys

import pytest

from flowguard.behave import engine
from flowguard.behave.engine import audit, content_identity
from flowguard.behave.skeleton import derive
from .test_explore import program

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot behavior needs Python 3.12")


def test_facts_reuse_then_actual_read_file_change_invalidates(program):
    path = program / "program.py"
    path.write_text(path.read_text().replace('        self._value = 0', '        self._value = 0\n        self._payload = Path(__file__).with_name("data.txt").read_text()'))
    data = program / "data.txt"
    data.write_text("first")
    first = audit(program, worlds=["small"], seeds=[0], steps=1)
    second = audit(program, worlds=["small"], seeds=[0], steps=1)
    assert first["facts_reused"] == 0 and second["facts_reused"] == 1
    data.write_text("changed without a code edit")
    changed = audit(program, worlds=["small"], seeds=[0], steps=1)
    assert changed["facts_reused"] == 0
    caches = list(engine.cache_root(program).glob("*.json"))
    assert caches
    for cache in caches:
        value = json.loads(cache.read_text())
        assert "verdict" not in value and "verdict" not in value["facts"]


def test_actually_listed_directory_change_invalidates(program):
    assets = program / "assets"
    assets.mkdir()
    path = program / "program.py"
    path.write_text(path.read_text().replace('        self._value = 0', '        self._value = 0\n        self._listed = os.listdir(Path(__file__).with_name("assets"))'))
    first = audit(program, worlds=["small"], seeds=[0], steps=1)
    assert audit(program, worlds=["small"], seeds=[0], steps=1)["facts_reused"] == 1
    (assets / "new.txt").write_text("new")
    changed = audit(program, worlds=["small"], seeds=[0], steps=1)
    assert first["facts_reused"] == 0 and changed["facts_reused"] == 0


def test_engine_source_identity_changes_without_version_bump(program, tmp_path, monkeypatch):
    package = tmp_path / "engine-copy/flowguard/behave"
    package.mkdir(parents=True)
    path = package / "engine.py"
    path.write_text('__version__ = "0.71.0"\nVALUE = 1\n')
    monkeypatch.setattr(engine, "__file__", str(path))
    spec = derive(program)
    before = content_identity(spec)
    path.write_text('__version__ = "0.71.0"\nVALUE = 2\n')
    assert content_identity(spec) != before

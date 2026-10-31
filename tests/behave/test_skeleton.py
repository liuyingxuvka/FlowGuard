"""Finite source and correction controls for the generated skeleton."""

from pathlib import Path
import sys

import pytest

from flowguard.behave.skeleton import SkeletonError, derive, read_corrections, write_pins

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot behavior needs Python 3.12")

SOURCE = '''from dataclasses import dataclass, asdict
import json
from pathlib import Path

@dataclass(frozen=True)
class Options:
    limit: int = 3

class Refusal(Exception): pass

class Vault:
    __slots__ = ("__secret",)
    def __init__(self): self.__secret = 1
    def bump(self): self.__secret += 1

class Bag(list): pass

class Engine:
    def __init__(self, options=None):
        self._options = options if options is not None else Options()
        self._items = {}
        self._hidden = {"count": 0}
        self._alias = self._hidden
        self._cycle = []
        self._cycle.append(self._cycle)
        self._vault = Vault()
    def add_entry(self, entry_id, name): self._items[entry_id] = name
    def entries(self): return list(self._items)
    def bump(self, entry_id):
        self._hidden["count"] += 1
        self._vault.bump()
        return self._hidden["count"]
    def status(self, entry_id):
        if entry_id not in self._items: return "missing"
        if self._hidden["count"]: return "active"
        return "ready"
    def why_not_bump(self, entry_id):
        return None if entry_id in self._items else "missing"
    def refuse(self): raise Refusal("unchanged")
    def refuse_changed(self):
        self._hidden["count"] += 1
        raise Refusal("changed")
    def refuse_permissions(self):
        Path("locked").chmod(0o400)
        raise Refusal("permissions changed")
    def use_subtype(self): self._sub = Bag([1, 2])
    def read_file(self, path): return Path(path).read_bytes()
    def save(self, path):
        data = {"options": asdict(self._options), "items": list(self._items.items()),
                "hidden": self._hidden, "secret": self._vault._Vault__secret}
        Path(path).write_text(json.dumps(data))
    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text())
        result = cls(Options(**data["options"]))
        result._items = dict(data["items"])
        result._hidden = data["hidden"]
        result._alias = result._hidden
        result._vault._Vault__secret = data["secret"]
        return result
'''


@pytest.fixture
def example(tmp_path):
    (tmp_path / "example.py").write_text(SOURCE, encoding="utf-8")
    return tmp_path


def test_skeleton_matches_reference_actions(example):
    spec = derive(example)
    assert spec["system"] == "example:Engine"
    assert spec["settings"] == "example:Options"
    assert spec["settings_parameter"] == "options"
    assert spec["shipped"] == {"limit": 3}
    assert spec["actions"] == ["bump", "refuse_changed", "use_subtype"]
    assert spec["entities"]["entry"]["list"] == "entries"
    assert spec["file_inputs"] == ["read_file"]
    assert spec["status_values"] == {"status": ["active", "missing", "ready"]}
    assert spec["predictor_pairs"] == [["why_not_bump", "bump"]]


def test_corrections_cannot_remove_goals(example):
    before = derive(example)
    write_pins(example, before)
    after = derive(example)
    assert after["actions"] == before["actions"]
    assert after["status_values"] == before["status_values"]


def test_config_in_skeleton_is_error(example):
    directory = example / ".flowguard"
    directory.mkdir()
    (directory / "skeleton.py").write_text('limit = 1\n')
    with pytest.raises(SkeletonError, match="config_in_skeleton"):
        derive(example)


def test_skeleton_removes_goal_is_error(example):
    directory = example / ".flowguard"
    directory.mkdir()
    (directory / "skeleton.py").write_text('exclude("bump", why="hide it")\n')
    with pytest.raises(SkeletonError, match="skeleton_removes_goal"):
        derive(example)


def test_source_pins_are_idempotent_and_preserve_user_bytes(example):
    directory = example / ".flowguard"
    directory.mkdir()
    original = b'# user comment without newline'
    path = directory / 'skeleton.py'
    path.write_bytes(original)
    spec = derive(example)
    write_pins(example, spec)
    once = path.read_bytes()
    write_pins(example, derive(example))
    assert path.read_bytes() == once
    assert once.startswith(original + b'\n')
    assert {row['args'][0] for row in read_corrections(example)} == {'system', 'settings'}


def test_missing_and_ambiguous_roots_do_not_create_pins(tmp_path):
    with pytest.raises(SkeletonError, match="world kind needed"):
        derive(tmp_path)
    (tmp_path / 'example.py').write_text('class A:\n def go(self): pass\nclass B:\n def go(self): pass\n')
    with pytest.raises(SkeletonError, match="system_ambiguous"):
        derive(tmp_path)
    assert not (tmp_path / '.flowguard').exists()

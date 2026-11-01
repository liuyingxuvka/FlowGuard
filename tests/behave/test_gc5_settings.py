"""Setting effects use real saved bytes and complete shipped test traces."""

import base64
import json
import sys

import pytest

from flowguard.behave.engine import audit
from flowguard.behave.project import replay
from flowguard.behave.skeleton import derive
from flowguard.behave.why import why

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot behavior needs Python 3.12")

PROGRAM = '''import json
from pathlib import Path
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class Settings:
    factor: int = 2
    capacity: int = 2
    unused: int = 1
    def to_data(self): return asdict(self)

class Refusal(Exception): pass

class Program:
    def __init__(self, settings=None):
        self._settings = settings if settings is not None else Settings()
        self._units = {}
        self._charges = []
    def add_unit(self, unit_id, name): self._units[unit_id] = {"premium": False, "active": 0}
    def units(self): return list(self._units)
    def price(self, unit_id): return 10 * self._settings.factor
    def allowance(self, unit_id): return self._settings.capacity
    def charge(self, unit_id): self._charges.append(10)
    def upgrade(self, unit_id): self._units[unit_id]["premium"] = True
    def reserve(self, unit_id):
        limit = 3 + (self._settings.capacity if self._units[unit_id]["premium"] else 0)
        if self._units[unit_id]["active"] >= limit: raise Refusal("full")
        self._units[unit_id]["active"] += 1
    def _data(self):
        return {"settings": self._settings.to_data(), "units": self._units, "charges": self._charges}
    def save(self, path):
        Path(path).write_text(json.dumps(self._data()))
    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text())
        result = cls(Settings(**data["settings"]))
        result._units = data["units"]
        result._charges = data["charges"]
        return result
'''

USAGE = '''from program import Program

def test_long_threshold_path():
    program = Program()
    program.add_unit("U1", "one")
    program.upgrade("U1")
    for _ in range(4): program.reserve("U1")
    assert program.allowance("U1") == 2
'''


def run(root):
    return audit(root, worlds=["small"], seeds=[1], steps=1, node_cap=16, alphabet_cap=64, use_cache=False)


def test_real_settings_mirror_is_not_a_domain_effect_and_why_rechecks(tmp_path):
    path = tmp_path / "program.py"
    path.write_text(PROGRAM)
    result = run(tmp_path)
    assert not result["errors"]
    item, = [row for row in result["items"] if row["semantic"].get("setting") == "factor"]
    assert item["label"] == "ADVICE ONLY" and item["id"].startswith("A-")
    assert item["effects"]["query_changes"] == ["price"]
    assert item["proof"]["matched"]
    assert any(row["setting"] == "unused" and row["label"] == "NO OBSERVED EFFECT" for row in result["settings"]["information"])
    path.write_text(PROGRAM.replace('self._charges.append(10)', 'self._charges.append(self.price(unit_id))'))
    fixed = why(tmp_path, item["id"])
    assert not fixed["matched"] and fixed["state"] == "no-longer-reproduces"


def test_actual_full_shipped_test_prefix_removes_fresh_only_advice(tmp_path):
    (tmp_path / "program.py").write_text(PROGRAM)
    fresh = run(tmp_path)
    assert any(row["semantic"].get("setting") == "capacity" for row in fresh["items"])
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_usage.py").write_text(USAGE)
    union = run(tmp_path)
    assert not union["errors"]
    assert union["test_scope"]["tests"] == 1
    assert not any(row["semantic"].get("setting") == "capacity" for row in union["items"])
    assert any(row["setting"] == "capacity" and row["label"] == "EFFECT OBSERVED" for row in union["settings"]["information"])
    assert union["settings"]["traces"] > fresh["settings"]["traces"]


def test_loaded_configuration_override_and_unbound_serializer_are_not_unused(tmp_path):
    path = tmp_path / "program.py"
    path.write_text(PROGRAM)
    spec = derive(tmp_path)
    payload = json.dumps({"settings": {"factor": 7, "capacity": 2, "unused": 1},
                          "units": {"U1": {"premium": False, "active": 0}}, "charges": []}).encode()
    trace = {"start": {"files": {"saved.json": base64.b64encode(payload).decode("ascii")}},
             "prefix": [{"name": "load", "args": [{"$file": "saved.json"}], "replace": True}],
             "outcomes": ["success"], "origin": "saved-file"}
    loaded = replay(spec, [], operation="settings", options={"traces": [trace], "setting": "factor", "alphabet_cap": 64})
    assert not loaded["candidates"] and not loaded["information"]
    assert any("overwrote" in row["reason"] for row in loaded["unknown"])
    path.write_text(PROGRAM.replace('self._settings.to_data()', '{"factor": self._settings.factor}'))
    unbound = replay(derive(tmp_path), [], operation="settings", options={"traces": [], "setting": "factor"})
    assert not unbound["candidates"] and not unbound["information"] and unbound["unknown"]
    coerced = PROGRAM.replace('def to_data(self): return asdict(self)',
              'def to_data(self):\n        result = asdict(self)\n        result["unused"] = bool(result["unused"])\n        return result')
    path.write_text(coerced)
    wrong_type = replay(derive(tmp_path), [], operation="settings", options={
        "traces": [{"start": {"world": "small"}, "prefix": [], "outcomes": []}], "setting": "factor"})
    assert not wrong_type["candidates"]
    assert any("subtree does not match" in row["reason"] for row in wrong_type["unknown"])


def test_declared_invalid_configuration_does_not_abort_other_setting_profiles(tmp_path):
    from flowguard.behave.project import UnsupportedWorld

    source = PROGRAM.replace('    def to_data(self): return asdict(self)',
        '    def __post_init__(self):\n        if self.factor < 1: raise Refusal("factor must be at least one")\n    def to_data(self): return asdict(self)')
    source = source.replace('        self._units = {}',
        '        if self._settings.factor == 999: raise RuntimeError("unexpected constructor")\n        self._units = {}')
    source += '\n    def decline(self): raise Refusal("declared action")\n    def explode(self):\n        self._charges.append(0)\n        raise RuntimeError("unexpected action")\n'
    (tmp_path / "program.py").write_text(source)
    spec = derive(tmp_path)
    traces = [{"start": {"world": "small"}, "prefix": [], "outcomes": []}]
    facts = replay(spec, [], operation="settings", options={"traces": traces, "alphabet_cap": 32})
    invalid, = [row for row in facts["profiles"] if row["setting"] == "factor" and row["value"] == 0]
    assert invalid["state"] == "not-buildable"
    assert any(row["setting"] == "factor" and row["value"] == 1 and row["replays"] > 0 for row in facts["profiles"])
    assert any(row["setting"] == "capacity" and row["replays"] > 0 for row in facts["profiles"])
    assert any(row["setting"] == "unused" for row in facts["information"])
    assert any("Refusal" in row["reason"] and "factor must be at least one" in row["reason"] for row in facts["unknown"])
    actual = replay(spec, [{"name": "decline"}, {"name": "explode"}])
    assert [row["outcome"] for row in actual["steps"]] == ["refusal", "crash"]
    assert actual["steps"][1]["exception"]["type"] == "builtins:RuntimeError"
    with pytest.raises(UnsupportedWorld, match="RuntimeError: unexpected constructor"):
        replay(spec, [], {"settings": {"factor": 999}})

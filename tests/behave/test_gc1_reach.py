"""Shipped reach failures require complete native search and a fresh proof."""

import sys

import pytest

from flowguard.behave.engine import audit

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot behavior needs Python 3.12")

PROGRAM = '''from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    enabled: bool = False

class Refusal(Exception): pass

class Program:
    def __init__(self, settings=None):
        self._settings = settings if settings is not None else Settings()
        self._ids = []
        self._state = {}
        self._clock = False
    def add_unit(self, unit_id, name):
        self._ids.append(unit_id)
        self._state[unit_id] = 0
    def units(self): return list(self._ids)
    def advance(self, unit_id):
        if not self._settings.enabled: raise Refusal("disabled")
        self._state[unit_id] = 1
    def close(self, unit_id):
        if self._state[unit_id] != 1: raise Refusal("not ready")
        self._state[unit_id] = 2
    def tick(self, unit_id): self._clock = not self._clock
    def status(self, unit_id):
        if self._state[unit_id] == 0: return "new"
        if self._state[unit_id] == 1: return "ready"
        return "done"
'''


def is_advance(row):
    semantic = row.get("semantic", row.get("goal", {}))
    return semantic.get("kind") == "action" and semantic.get("name") == "advance"


def test_boolean_default_has_a_proved_missing_action_and_enabled_control(tmp_path):
    path = tmp_path / "program.py"
    path.write_text(PROGRAM)
    result = audit(tmp_path, worlds=["small"], seeds=[0], steps=8,
                   node_cap=16, alphabet_cap=32, use_cache=False)
    assert not result["errors"]
    item, = [row for row in result["items"] if is_advance(row)]
    assert item["semantic"]["check"] == "GC1"
    assert item["label"] == "OFF BY DEFAULT"
    assert item["explanations"] == [{"setting": "enabled", "value": True}]
    assert item["search"]["complete"]
    assert item["proof"]["matched"] and item["proof"]["state"] == "reproduced"
    proof = item["proof"]["proof"]
    assert not proof["found"] and proof["extent"]["complete"]
    assert proof["execution"]["child_pid"] != result["runs"][0]["facts"]["execution"]["child_pid"]

    path.write_text(PROGRAM.replace("enabled: bool = False", "enabled: bool = True"))
    corrected = audit(tmp_path, worlds=["small"], seeds=[0], steps=8,
                      node_cap=16, alphabet_cap=32, use_cache=False)
    assert not corrected["errors"]
    assert not any(is_advance(row) for row in corrected["items"])
    assert not any(is_advance(row) for row in corrected["runs"][0]["facts"]["reach"]["unknown"])


def test_capped_missing_action_remains_unknown_instead_of_never_reached(tmp_path):
    (tmp_path / "program.py").write_text(PROGRAM)
    result = audit(tmp_path, worlds=["small"], seeds=[0], steps=1,
                   node_cap=1, alphabet_cap=32, use_cache=False)
    assert not result["errors"]
    unknown = [row for row in result["runs"][0]["facts"]["reach"]["unknown"] if is_advance(row)]
    assert unknown and all(row["extent"]["capped"] and not row["extent"]["complete"] for row in unknown)
    assert not any(is_advance(row) for row in result["items"])

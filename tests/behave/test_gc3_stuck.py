"""Concrete status traps and cross-entity exits use the real child and search."""

import sys

import pytest

from flowguard.behave.engine import audit
from flowguard.behave.project import replay
from flowguard.behave.skeleton import derive
from flowguard.behave.why import why

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot behavior needs Python 3.12")

PROGRAM = '''class Refusal(Exception): pass

class Program:
    def __init__(self): self._units = {}
    def add_unit(self, unit_id, name, place=None):
        if place is None: place = "local" if not self._units else "remote"
        self._units[unit_id] = {"state": "busy", "place": place}
    def units(self): return list(self._units)
    def begin(self, unit_id):
        if self.status(unit_id) != "idle": raise Refusal("not idle")
        self._units[unit_id]["state"] = "busy"
    def finish(self, unit_id):
        if self.status(unit_id) != "busy": raise Refusal("not busy")
        if self.place(unit_id) != "local": raise Refusal("remote")
        self._units[unit_id]["state"] = "idle"
    def move(self, unit_id, place):
        if self.status(unit_id) != "idle": raise Refusal("not idle")
        if place not in ("local", "remote"): raise Refusal("unknown place")
        self._units[unit_id]["place"] = place
    def close(self, unit_id):
        if self.status(unit_id) != "idle": raise Refusal("not idle")
        self._units[unit_id]["state"] = "done"
    def place(self, unit_id): return self._units[unit_id]["place"]
    def status(self, unit_id):
        if self._units[unit_id]["state"] == "idle": return "idle"
        if self._units[unit_id]["state"] == "busy": return "busy"
        return "done"
'''

USAGE = '''from program import Program

def test_usage():
    program = Program()
    program.add_unit("U1", "one", place="local")
    program.add_unit("U2", "two", place="remote")
    program.finish("U1")
    program.begin("U1")
    assert program.status("U2") == "busy"
'''


def test_generated_world_trap_is_freshly_proved_and_source_fix_removes_it(tmp_path):
    path = tmp_path / "program.py"
    path.write_text(PROGRAM)
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_usage.py").write_text(USAGE)
    options = dict(worlds=["default"], seeds=[0], steps=4, node_cap=64,
                   alphabet_cap=64, use_cache=False)
    result = audit(tmp_path, **options)
    assert not result["errors"]
    traps = [row for row in result["items"] if row["semantic"].get("check") == "GC3"]
    assert traps
    item = next(row for row in traps if row["semantic"]["value"] == "busy"
                and row["semantic"]["context"].get("place") == "remote")
    assert item["label"] == "STUCK" and item["search"]["complete"]
    assert item["start"] == {"world": "default", "seed": 0}
    assert not any(row.get("name") == "add_unit" for row in item["prefix"])
    assert item["proof"]["matched"] and item["proof"]["state"] == "reproduced"
    proof = item["proof"]["proof"]
    assert not proof["found"] and proof["extent"]["complete"]
    assert proof["execution"]["child_pid"] != result["runs"][0]["facts"]["execution"]["child_pid"]

    path.write_text(PROGRAM.replace('        if self.place(unit_id) != "local": raise Refusal("remote")\n', ""))
    corrected = audit(tmp_path, **options)
    assert not corrected["errors"]
    assert not any(row["semantic"].get("check") == "GC3" for row in corrected["items"])
    recheck = why(tmp_path, item["id"])
    assert not recheck["matched"] and recheck["state"] == "no-longer-reproduces"
    assert recheck["proof"]["found"]


RELATED_PROGRAM = '''class Refusal(Exception): pass

class Program:
    def __init__(self):
        self._agents = {}
        self._units = {}
    def add_agent(self, agent_id, name): self._agents[agent_id] = False
    def agents(self): return list(self._agents)
    def add_unit(self, unit_id, name, agent_id):
        self._units[unit_id] = {"state": "idle", "agent": agent_id}
    def units(self): return list(self._units)
    def holder(self, unit_id): return self._units[unit_id]["agent"]
    def begin(self, unit_id):
        if self.status(unit_id) != "idle": raise Refusal("not idle")
        self._units[unit_id]["state"] = "busy"
    def settle(self, agent_id): self._agents[agent_id] = True
    def finish(self, unit_id):
        if self.status(unit_id) != "busy": raise Refusal("not busy")
        if not self._agents[self.holder(unit_id)]: raise Refusal("agent not settled")
        self._units[unit_id]["state"] = "idle"
    def close(self, unit_id):
        if self.status(unit_id) != "idle": raise Refusal("not idle")
        self._units[unit_id]["state"] = "done"
    def status(self, unit_id):
        if self._units[unit_id]["state"] == "idle": return "idle"
        if self._units[unit_id]["state"] == "busy": return "busy"
        return "done"
'''


def test_related_unit_search_keeps_the_queried_holder_and_two_step_exit(tmp_path):
    (tmp_path / "program.py").write_text(RELATED_PROGRAM)
    prefix = [{"name": "begin", "args": ["U1"]}]
    result = replay(derive(tmp_path), [], {"world": "small"}, operation="search", options={
        "goal": {"kind": "query", "query": "status", "args": ["U1"], "value": "busy", "comparison": "ne"},
        "prefix": prefix, "depth": 2, "node_cap": 16, "alphabet_cap": 32,
        "related": {"query": "status", "identifier": "U1"},
    })
    assert result["found"]
    assert [row["name"] for row in result["prefix"]] == ["begin", "settle", "finish"]
    assert result["prefix"][1]["args"] == ["A1"]
    assert result["prefix"][2]["args"] == ["U1"]

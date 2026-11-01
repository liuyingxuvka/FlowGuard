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


SLICE_CAP_PROGRAM = '''class Refusal(Exception): pass

class Program:
    def __init__(self):
        self._agents = {}
        self._units = {}
        self._noises = {}
    def add_agent(self, agent_id, name): self._agents[agent_id] = False
    def agents(self): return list(self._agents)
    def add_noise(self, noise_id, name): self._noises[noise_id] = False
    def noises(self): return list(self._noises)
    def aa_noise(self, noise_id): self._noises[noise_id] = not self._noises[noise_id]
    def add_unit(self, unit_id, name, agent_id):
        self._units[unit_id] = {"state": "idle", "agent": agent_id, "ready": False}
    def units(self): return list(self._units)
    def holder(self, unit_id): return self._units[unit_id]["agent"]
    def begin(self, unit_id): self._units[unit_id]["state"] = "busy"
    def close(self, unit_id):
        if self.status(unit_id) != "idle": raise Refusal("not idle")
        self._units[unit_id]["state"] = "done"
    def finish_ready(self):
        for unit_id in self._units:
            if self._units[unit_id]["ready"] and self._units[unit_id]["state"] == "busy":
                self._units[unit_id]["state"] = "idle"
    def zz_assist(self, unit_id, agent_id):
        if agent_id == self.holder(unit_id): raise Refusal("another agent is required")
        self._units[unit_id]["ready"] = True
    def status(self, unit_id):
        if self._units[unit_id]["state"] == "idle": return "idle"
        if self._units[unit_id]["state"] == "busy": return "busy"
        return "done"
'''


def test_related_alphabet_cap_counts_only_the_full_or_slice(tmp_path):
    (tmp_path / "program.py").write_text(SLICE_CAP_PROGRAM)
    result = replay(derive(tmp_path), [], {"world": "default"}, operation="search", options={
        "goal": {"kind": "query", "query": "status", "args": ["U1"], "value": "busy", "comparison": "ne"},
        "prefix": [{"name": "begin", "args": ["U1"]}], "depth": 2,
        "node_cap": 16, "alphabet_cap": 8,
        "related": {"query": "status", "identifier": "U1"},
    })
    assert result["found"], result
    assert not result["extent"]["domain_truncated"]
    assert result["prefix"][1:] == [
        {"name": "zz_assist", "args": ["U1", "A2"]},
        {"name": "finish_ready", "args": []},
    ]


NUMERIC_TRAP_PROGRAM = '''class Refusal(Exception): pass

class Program:
    def __init__(self): self._units = {}
    def add_unit(self, unit_id, name): self._units[unit_id] = {"state": "busy", "budget": 1}
    def units(self): return list(self._units)
    def advance(self, unit_id):
        if self._units[unit_id]["state"] == "busy":
            if self._units[unit_id]["budget"] < 1: raise Refusal("budget exhausted")
            self._units[unit_id]["budget"] -= 1
            self._units[unit_id]["state"] = "idle"
        elif self._units[unit_id]["state"] == "idle": self._units[unit_id]["state"] = "busy"
    def budget(self, unit_id): return self._units[unit_id]["budget"]
    def status(self, unit_id):
        if self._units[unit_id]["state"] == "idle": return "idle"
        if self._units[unit_id]["state"] == "busy": return "busy"
        return "done"
'''


def test_stuck_keeps_distinct_numeric_origins_with_the_same_labels(tmp_path):
    (tmp_path / "program.py").write_text(NUMERIC_TRAP_PROGRAM)
    result = replay(derive(tmp_path), [], {"world": "small"}, operation="diff", options={
        "seed": 0, "steps": 3, "node_cap": 4, "alphabet_cap": 4,
    })
    before = {row["query"]: row["value"] for row in result["events"][0]["before_observations"]["values"]}
    after = {row["query"]: row["value"] for row in result["events"][1]["after_observations"]["values"]}
    assert before["status"] == after["status"] == "busy"
    assert before["budget"] == 1 and after["budget"] == 0
    trap_prefix = [{"name": "advance", "args": ["U1"]}] * 2
    assert any(row["prefix"] == trap_prefix and row["search"]["complete"]
               for row in result["stuck"]["candidates"]), result["stuck"]


def test_stuck_search_reuses_its_first_bfs_layer(tmp_path, monkeypatch):
    from flowguard.behave import project
    (tmp_path / "program.py").write_text(RELATED_PROGRAM)
    original = project.run_isolated_process
    control = '''from flowguard.behave import checks, explore as walk, project as native
run_session = native._run_session
def controlled(request, arena, observed):
    if not request.get("options", {}).get("control_stuck"):
        return run_session(request, arena, observed)
    session = native._Session(request["spec"], request.get("start", {}), arena, observed)
    session.reset()
    records = []
    for recipe in ({"name": "begin", "args": ["U1"]}, {"name": "settle", "args": ["A1"]}, {"name": "finish", "args": ["U1"]}):
        session.step(recipe)
        records.append({"prefix": list(session.prefix), "start": dict(session.start),
                        "observations": walk.observations(session, all_queries=True)})
    searches, search = [], checks.focused_search
    def counted(*args, **kwargs):
        searches.append(kwargs["depth"])
        return search(*args, **kwargs)
    checks.focused_search = counted
    result = checks.stuck(session, {"states": records[:1], "extent": {"node_cap": 16, "alphabet_cap": 32}},
                          states=records, depth=2)
    return {**result, "control_depths": searches, "execution": session.receipt()}
native._run_session = controlled
'''
    def observed(command, **kwargs):
        command = list(command)
        command[2] = control + command[2]
        return original(command, **kwargs)
    monkeypatch.setattr(project, "run_isolated_process", observed)
    result = replay(derive(tmp_path), [], {"world": "small"}, options={"control_stuck": True})
    assert result["control_depths"] == [2]
    assert result["candidates"] == [] and result["unknown"] == []

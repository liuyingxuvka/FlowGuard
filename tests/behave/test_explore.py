"""Concrete finite search and the single-child execution boundary."""

import json
import sys

import pytest

from flowguard.behave import project
from flowguard.behave.project import UnsupportedWorld, replay
from flowguard.behave.skeleton import derive

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot behavior needs Python 3.12")

PROGRAM = '''from dataclasses import dataclass
from pathlib import Path
import os

@dataclass(frozen=True)
class Settings:
    ceiling: int = 3

class Refusal(Exception): pass

class Program:
    def __init__(self, settings=None):
        self._settings = settings if settings is not None else Settings()
        self._ids = []
        self._value = 0
    def add_unit(self, unit_id, name): self._ids.append(unit_id)
    def units(self): return list(self._ids)
    def advance(self, unit_id):
        if self._value >= self._settings.ceiling: raise Refusal("ceiling")
        self._value += 1
        return self._value
    def value(self, unit_id): return self._value
    def status(self, unit_id):
        if self._value == 0: return "new"
        if self._value == 1: return "ready"
        return "done"
'''


@pytest.fixture
def program(tmp_path):
    (tmp_path / "program.py").write_text(PROGRAM)
    return tmp_path


def goal(value):
    return {"kind": "query", "receiver": "system", "query": "value", "args": ["U1"], "value": value}


def test_walk_stays_in_one_child_and_returns_compact_events(program, monkeypatch):
    original = project.run_isolated_process
    invocations = []
    def count(*args, **kwargs):
        invocations.append(1)
        return original(*args, **kwargs)
    monkeypatch.setattr(project, "run_isolated_process", count)
    spec = derive(program)
    facts = replay(spec, [], {"world": "small"}, operation="explore", options={"seed": 4, "steps": 2, "node_cap": 10})
    assert len(invocations) == 1
    assert facts["execution"]["executed_calls"] > 2
    assert len(facts["events"]) == 2
    assert all("before" not in row and "after" not in row and "before_key" in row for row in facts["events"])
    assert not facts["extent"]["complete"]
    assert facts["witnesses"]


def test_focused_search_distinguishes_complete_capped_and_reached(program):
    spec = derive(program)
    start = {"world": "small"}
    complete = replay(spec, [], start, operation="search", options={"goal": goal(99), "depth": 4, "node_cap": 8})
    capped = replay(spec, [], start, operation="search", options={"goal": goal(99), "depth": 4, "node_cap": 2})
    reached = replay(spec, [], start, operation="search", options={"goal": goal(2), "depth": 3, "node_cap": 8})
    assert not complete["found"] and complete["extent"]["complete"]
    assert not capped["found"] and capped["extent"]["capped"] and not capped["extent"]["complete"]
    assert reached["found"] and len(reached["prefix"]) == 2
    assert complete["execution"]["child_pid"] != capped["execution"]["child_pid"]


def test_known_witness_precedes_second_seed_and_directed_search(program):
    spec = derive(program)
    prefix = [{"name": "advance", "args": ["U1"]}]
    known = replay(spec, [], {"world": "small"}, operation="directed", options={"goal": goal(1), "known": [{"prefix": prefix}], "node_cap": 1})
    assert known["found"] and known["origin"] == "known-public-witness"
    directed = replay(spec, [], {"world": "small"}, operation="directed", options={"goal": goal(2), "secondary_steps": 1, "depth": 3, "node_cap": 8})
    assert directed["found"] and len(directed["prefix"]) == 2


def test_actual_class_data_mutation_is_unsupported_but_unused_global_is_not(program):
    path = program / "program.py"
    source = path.read_text().replace("import os", "import os\nimport random\nimport helper")
    source = source.replace("        self._value += 1", "        if self._value < 0: random.random()\n        self._value += 1")
    source = source.replace("        self._value += 1", "        self._value += helper.pure()")
    source = source.replace("    def units(self):", '    def external(self):\n        Totals.count += 1\n        raise Refusal("outside instance graph")\n    def random_value(self): return random.random()\n    def mutate_function(self): helper.mutating()\n    def units(self):')
    path.write_text(source + "\nclass Totals:\n    count = 0\n")
    (program / "helper.py").write_text("def pure(): return 1\ndef mutating(): mutating.count += 1\nmutating.count = 0\n")
    (program / "unused.py").write_text("count = 0\ndef never_called():\n global count\n count += 1\n")
    spec = derive(program)
    assert spec["unsupported"]  # A source-only declaration used to refuse this entire project.
    ordinary = replay(spec, [{"name": "advance", "args": ["U1"]}], {"world": "small"})
    assert ordinary["steps"][0]["outcome"] == "success"
    with pytest.raises(UnsupportedWorld, match="class/global/closure"):
        replay(spec, [{"name": "external"}], {"world": "small"})
    with pytest.raises(UnsupportedWorld, match="called nondeterministic"):
        replay(spec, [{"name": "random_value"}], {"world": "small"})
    with pytest.raises(UnsupportedWorld, match="class/global/closure"):
        replay(spec, [{"name": "mutate_function"}], {"world": "small"})


def test_branch_checkpoints_keep_aliases_cycles_and_file_bytes_and_mode(program):
    path = program / "program.py"
    source = path.read_text().replace("        self._value = 0", "        self._value = 0\n        self._data = {'value': 0}\n        self._alias = self._data\n        self._cycle = []\n        self._cycle.append(self._cycle)")
    source = source.replace("        self._value += 1", '''        if self._alias is not self._data or self._cycle[0] is not self._cycle:
            raise Refusal("broken graph")
        path = Path("state.bin")
        if path.exists():
            if path.read_text() != str(self._data["value"]) or path.stat().st_mode & 0o777 != 0o400:
                raise Refusal("broken files")
            path.chmod(0o600)
        self._value += 1
        self._data["value"] = self._value
        path.write_text(str(self._value))
        path.chmod(0o400)''')
    path.write_text(source)
    result = replay(derive(program), [], {"world": "small"}, operation="search", options={"goal": goal(2), "depth": 3, "node_cap": 8, "actions": ["advance"]})
    assert result["found"] and len(result["prefix"]) == 2


def test_custom_copy_cannot_turn_a_shared_object_into_a_complete_search(program):
    path = program / "program.py"
    path.write_text(path.read_text().replace("    def units(self):", "    def __deepcopy__(self, memo): return self\n    def units(self):"))
    with pytest.raises(UnsupportedWorld, match="copy or serialization hooks"):
        replay(derive(program), [], {"world": "small"}, operation="search", options={"goal": goal(99), "depth": 3})


def test_secondary_goals_keep_the_step16_boundary_and_the_same_walk(program):
    path = program / "program.py"
    path.write_text(path.read_text().replace("ceiling: int = 3", "ceiling: int = 100"))
    spec = derive(program)
    options = {"seed": 0, "steps": 17, "node_cap": 32, "alphabet_cap": 8}
    single = replay(spec, [], {"world": "small"}, operation="explore", options={**options, "goal": goal(16)})
    witness, = [row for row in single["witnesses"] if row["semantic"] == goal(16)]
    assert len(witness["prefix"]) == 16  # The next iteration resets before action17.
    action = {"kind": "action", "receiver": "system", "name": "advance", "outcome": "success"}
    batch = replay(spec, [], {"world": "small"}, operation="explore", options={**options, "goals": [goal(16), action]})
    assert batch["events"] == single["events"] and batch["extent"] == single["extent"]
    assert batch["checked_goals"] == [goal(16), action]
    assert all(any(row["semantic"] == target for row in batch["witnesses"]) for target in batch["checked_goals"])
    proof = replay(spec, witness["prefix"], witness["start"], operation="prove",
                   options={"goal": goal(16), "outcomes": witness["outcomes"]})
    assert proof["matched"] and proof["execution"]["child_pid"] != single["execution"]["child_pid"]


def test_stale_priority_queue_item_is_discarded_before_native_restore(tmp_path, monkeypatch):
    (tmp_path / "program.py").write_text('''class Program:
    def __init__(self): self._ids, self._value = [], 0
    def add_unit(self, unit_id, name): self._ids.append(unit_id)
    def units(self): return list(self._ids)
    def value(self, unit_id): return self._value
    def first(self):
        if self._value == 0: self._value = 1
        elif self._value == 1: self._value = 2
        elif self._value == 2: self._value = 4
    def short(self):
        if self._value == 0: self._value = 3
        elif self._value == 3: self._value = 4
''')
    original = project.run_isolated_process
    control = '''from flowguard.behave import explore as walk, project as native
restored = []
restore, receipt = native._Session.restore_checkpoint, native._Session.receipt
def observe_restore(self, checkpoint):
    restored.append([row["name"] for row in checkpoint["prefix"]])
    return restore(self, checkpoint)
def observe_receipt(self):
    return {**receipt(self), "control_restores": restored}
def rank(session, goal, observed, hints=None):
    value = walk.plain(session.query("system", "value", ["U1"]))
    return {0: 0, 1: -100, 2: -100, 3: -20, 4: 0}[value]
native._Session.restore_checkpoint = observe_restore
native._Session.receipt = observe_receipt
walk._guard_distance = rank
'''
    def observed(command, **kwargs):
        command = list(command)
        command[2] = control + command[2]
        return original(command, **kwargs)
    monkeypatch.setattr(project, "run_isolated_process", observed)
    facts = replay(derive(tmp_path), [], {"world": "small"}, operation="search",
                   options={"goal": goal(99), "priority": True, "depth": 4, "node_cap": 8, "alphabet_cap": 8})
    assert not facts["found"] and facts["extent"]["complete"] and facts["extent"]["visited"] == 5
    assert ["first", "first", "first"] not in facts["execution"]["control_restores"]


@pytest.mark.parametrize("target", [goal(99), {"kind": "action", "name": "absent", "outcome": "success"}])
def test_search_keeps_leaf_facts_without_copying_finished_query_action_nodes(program, monkeypatch, target):
    original = project.run_isolated_process
    control = '''from flowguard.behave import project as native
checkpoints, restores = [], []
checkpoint, restore, receipt = native._Session.checkpoint, native._Session.restore_checkpoint, native._Session.receipt
def counted_checkpoint(self):
    checkpoints.append(len(self.prefix))
    return checkpoint(self)
def counted_restore(self, saved):
    restores.append(len(saved["prefix"]))
    return restore(self, saved)
def counted_receipt(self):
    return {**receipt(self), "control_checkpoints": checkpoints, "control_restores": restores}
native._Session.checkpoint = counted_checkpoint
native._Session.restore_checkpoint = counted_restore
native._Session.receipt = counted_receipt
'''
    def observed(command, **kwargs):
        command = list(command)
        command[2] = control + command[2]
        return original(command, **kwargs)
    monkeypatch.setattr(project, "run_isolated_process", observed)
    result = replay(derive(program), [], {"world": "small"}, operation="search", options={
        "goal": target, "depth": 2, "node_cap": 8, "alphabet_cap": 8, "actions": ["advance"]})
    assert not result["found"] and result["extent"]["complete"]
    assert result["extent"]["visited"] == 3 and result["extent"]["attempted"] == 2
    assert [row["call"] for row in result["answers"]] == [{"name": "advance", "args": ["U1"]}]
    assert 2 not in result["execution"]["control_checkpoints"]
    assert 2 not in result["execution"]["control_restores"]

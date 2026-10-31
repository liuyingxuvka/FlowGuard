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

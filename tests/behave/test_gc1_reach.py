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
    assert proof["execution"]["child_pid"] not in result["runs"][0]["facts"]["execution"]["child_pids"]

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


def test_missing_goals_share_one_secondary_walk_but_keep_fresh_negative_proofs(tmp_path, monkeypatch):
    from flowguard.behave import project
    (tmp_path / "program.py").write_text(PROGRAM)
    original = project.run_isolated_process
    control = '''from flowguard.behave import explore as walk, project as native
walks = []
explore, receipt = walk.explore, native._Session.receipt
def observe_walk(*args, **kwargs):
    walks.append({"seed": kwargs.get("seed", 0), "goals": kwargs.get("goals", [])})
    return explore(*args, **kwargs)
def observe_receipt(self):
    return {**receipt(self), "control_walks": walks}
walk.explore = observe_walk
native._Session.receipt = observe_receipt
'''
    def observed(command, **kwargs):
        command = list(command)
        command[2] = control + command[2]
        return original(command, **kwargs)
    monkeypatch.setattr(project, "run_isolated_process", observed)
    result = audit(tmp_path, worlds=["small"], seeds=[0], steps=2,
                   node_cap=16, alphabet_cap=32, use_cache=False)
    assert not result["errors"]
    facts = result["runs"][0]["facts"]
    secondary = [row for row in facts["execution"]["phases"]["reach"]["control_walks"] if row["seed"] == 1]
    assert len(secondary) == 1 and len(secondary[0]["goals"]) > 1
    action, = [row for row in result["items"] if is_advance(row)]
    assert action["search"]["complete"] and action["proof"]["matched"]
    assert action["proof"]["proof"]["extent"]["complete"]
    assert action["proof"]["proof"]["execution"]["child_pid"] not in facts["execution"]["child_pids"]


def test_direct_ui_positive_precedes_deep_search_and_fresh_replays(tmp_path, monkeypatch):
    from flowguard.behave import project
    from flowguard.behave.skeleton import derive

    view = '''
class View:
    def __init__(self, program, staff=False):
        self.program = program
        self.staff = staff
        self.stack = [("home", {})]
        self.dynamic = {"dynamic": ("dynamic", {})}
    @property
    def screen(self): return self.stack[-1][0]
    def options(self):
        self.program.units()
        if not self.staff: return []
        return ["panel", "blocked", "dynamic"]
    def choose(self, option, **inputs):
        if option == "panel": self.stack.append(("panel", {}))
        if option == "blocked":
            raise Refusal("blocked")
            self.stack.append(("blocked", {}))
        if option in self.dynamic: self.stack.append(self.dynamic[option])
'''
    (tmp_path / "program.py").write_text(PROGRAM + view)
    spec = derive(tmp_path)
    assert spec["ui_facts"]["option_inputs"].get("panel") == []
    assert "dynamic" not in spec["ui_facts"]["option_inputs"]
    original = project.run_isolated_process
    control = '''from flowguard.behave import checks, project as native
run_session = native._run_session
def controlled(request, arena, observed):
    if not request.get("options", {}).get("control_reach"):
        return run_session(request, arena, observed)
    session = native._Session(request["spec"], request.get("start", {}), arena, observed)
    session.base_prefix = list(request["calls"])
    session.reset()
    searched, choices = [], []
    native_step = session.step
    def step(recipe, **kwargs):
        row = native_step(recipe, **kwargs)
        if recipe.get("name") == session.spec["ui_methods"]["choose"]:
            choices.append({"option": recipe["args"][0], "outcome": row["outcome"]})
        return row
    session.step = step
    def capped(session, **options):
        searched.append({"goal": options["goal"], "choices_before": list(choices)})
        return {"found": False, "extent": {"complete": False, "capped": True, "reason": "control stops deep search"}}
    checks.directed_search = capped
    facts = {"witnesses": [], "states": [], "extent": {"node_cap": 8, "alphabet_cap": 8, "successful_step_budget": 1}}
    result = checks.reach(session, facts, known=request["options"].get("known", []),
                          origin="control-start", depth=request["options"]["depth"])
    return {**result, "control_searched": searched, "execution": session.receipt()}
native._run_session = controlled
'''
    def observed(command, **kwargs):
        command = list(command)
        command[2] = control + command[2]
        return original(command, **kwargs)
    monkeypatch.setattr(project, "run_isolated_process", observed)
    base = [{"name": "tick", "args": ["U1"]}]
    start = {"world": "small", "seed": 7}
    facts = project.replay(spec, base, start, options={"control_reach": True, "depth": 3})
    screen = {"kind": "screen", "value": "panel", "ui_class": spec["ui"]}
    positive, = [row for row in facts["coverage"] if row["goal"] == screen]
    assert positive["prefix"][:len(base)] == base and positive["start"] == start
    assert len(positive["prefix"]) - len(base) <= 3
    assert positive["origin"] == "source-bound-ui-positive"
    assert not any(row["goal"] == screen for row in facts["control_searched"])
    assert facts["control_searched"][0]["goal"]["kind"] == "query"
    choices = facts["control_searched"][0]["choices_before"]
    assert {"option": "panel", "outcome": "success"} in choices
    assert {"option": "blocked", "outcome": "refusal"} in choices
    assert not any(row["option"] == "dynamic" for row in choices)
    assert not facts["candidates"]
    for value in ("blocked", "dynamic"):
        assert not any(row["goal"].get("kind") == "screen" and row["goal"].get("value") == value for row in facts["coverage"])
        assert any(row["goal"].get("kind") == "screen" and row["goal"].get("value") == value for row in facts["unknown"])
    proof = project.replay(spec, positive["prefix"], start, operation="prove",
                           options={"goal": screen, "outcomes": positive["outcomes"]})
    assert proof["matched"] and proof["execution"]["child_pid"] != facts["execution"]["child_pid"]
    shallow = project.replay(spec, base, start, options={"control_reach": True, "depth": 2})
    assert not any(row["goal"] == screen for row in shallow["coverage"])
    known = [{"semantic": {**screen, "origin": "control-start"}, **positive}]
    preferred = project.replay(spec, base, start, options={"control_reach": True, "depth": 3, "known": known})
    assert any(row["goal"] == screen for row in preferred["control_searched"])
    assert not any(row["option"] == "panel" for row in preferred["control_searched"][0]["choices_before"])

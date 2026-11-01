"""Predictors, UI offers and actions must agree at the same native state."""

import json
import sys

import pytest

from flowguard.behave.engine import audit
from flowguard.behave.project import replay
from flowguard.behave.report import item_id, render
from flowguard.behave.skeleton import derive

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot behavior needs Python 3.12")

PROGRAM = '''class Refusal(Exception): pass

class Program:
    def __init__(self):
        self._ids = []
        self._value = 0
    def add_unit(self, unit_id, name): self._ids.append(unit_id)
    def units(self): return list(self._ids)
    def advance(self, unit_id):
        ACTION
        self._value = 1
    def PREDICTOR(self, unit_id): return ANSWER
'''


def run(root):
    return audit(root, worlds=["small"], seeds=[0], steps=2, node_cap=16,
                 alphabet_cap=32, use_cache=False)


@pytest.mark.parametrize("predictor,answer,action,expected,observed,fixed", [
    ("why_not_advance", "None", 'raise Refusal("blocked")', True, "refusal", '"blocked"'),
    ("can_advance", "False", "pass", False, "success", "True"),
])
def test_generated_state_checks_both_directions_and_consistent_control(
        tmp_path, predictor, answer, action, expected, observed, fixed):
    path = tmp_path / "program.py"
    source = PROGRAM.replace("PREDICTOR", predictor).replace("ACTION", action)
    path.write_text(source.replace("ANSWER", answer))
    result = run(tmp_path)
    assert not result["errors"]
    items = [row for row in result["items"] if row["semantic"].get("check") == "GC2"]
    assert items
    item = next(row for row in items if row["semantic"]["predictor"] == predictor)
    assert item["label"] == "CONTRADICTION"
    assert item["semantic"]["expected"] is expected
    assert item["semantic"]["observed"] == observed
    assert item["comparison"]["action"]["args"] == ["U1"]
    assert item["comparison"]["predictor"]["kwargs"] == {"unit_id": "U1"}
    assert len(item["prefix"]) == len(item["outcomes"])
    assert item["proof"]["matched"] and item["proof"]["state"] == "reproduced"
    assert item["proof"]["proof"]["compared"] == 1
    assert item["proof"]["proof"]["execution"]["child_pid"] != result["runs"][0]["facts"]["execution"]["child_pid"]
    shown = next(row for row in json.loads(render(result, as_json=True))["items"] if row["id"] == item["id"])
    comparison = shown["comparison"]
    assert comparison["predictor"] == item["comparison"]["predictor"]
    assert comparison["action"] == item["comparison"]["action"]
    assert comparison["expected_permission"] is expected and comparison["observed"] == observed
    assert comparison["predictor_value"] is (None if predictor.startswith("why_not_") else expected)
    assert set(comparison["answer"]) == {"call", "outcome", "exception", "value"}
    assert comparison["answer"]["call"]["args"] == ["U1"]
    assert comparison["answer"]["outcome"] == observed
    assert comparison["before_key"]
    if observed == "refusal":
        assert comparison["answer"]["exception"]["message"] == "blocked"
        assert "advance -> refusal 'blocked'" in render(result)

    path.write_text(source.replace("ANSWER", fixed))
    corrected = run(tmp_path)
    assert not corrected["errors"]
    assert not any(row["semantic"].get("check") == "GC2" for row in corrected["items"])


def test_nonboolean_can_answer_is_unknown_instead_of_truthy_permission(tmp_path):
    (tmp_path / "program.py").write_text(PROGRAM.replace("PREDICTOR", "can_advance")
                                        .replace("ACTION", "pass").replace("ANSWER", '"yes"'))
    result = run(tmp_path)
    assert not result["errors"]
    assert not any(row["semantic"].get("check") == "GC2" for row in result["items"])
    assert result["runs"][0]["facts"]["agreement"]["unknown"]

    # An actual action's extra nondefault argument is outside its predictor's scope.
    source = PROGRAM.replace("PREDICTOR", "why_not_advance").replace("ANSWER", "None")
    source = source.replace("def advance(self, unit_id):", "def advance(self, unit_id, enabled=True):")
    (tmp_path / "program.py").write_text(source.replace("ACTION", 'if enabled is not True: raise Refusal("unsupported option")'))
    spec = derive(tmp_path)
    prefix = [{"name": "add_unit", "args": ["U1", "first"]}]
    actual = {"name": "advance", "args": ["U1", 1]}
    trace = replay(spec, [*prefix, actual])
    assert [row["outcome"] for row in trace["steps"]] == ["success", "refusal"]
    states = [{"test": "observed-parameters", "prefix": prefix, "outcomes": ["success"]},
              {"test": "observed-parameters", "prefix": [*prefix, actual], "outcomes": ["success", "refusal"]}]
    compared = replay(spec, [], operation="agreement", options={"facts": {}, "states": states})
    assert not compared["candidates"]
    assert any("not verified defaults" in row["reason"] for row in compared["unknown"])


VIEW = '''
class View:
    def __init__(self, program, unit_id, staff=False):
        self.program = program
        self.unit_id = unit_id
        self.staff = staff
        self.screen = "home"
    def options(self):
        OFFER_GUARD
        return ["next"]
    def choose(self, option, **inputs):
        if option == "next":
            CHOOSE_GUARD
            self.program.advance(self.unit_id)
'''


@pytest.mark.parametrize("offered", [False, True])
def test_ui_absence_is_not_permission_but_offered_refusal_contradicts(tmp_path, offered):
    path = tmp_path / "program.py"
    base = PROGRAM.replace("PREDICTOR", "why_not_advance").replace("ACTION", "pass").replace("ANSWER", "None")
    view = VIEW.replace("OFFER_GUARD", "pass" if offered else 'if not self.staff: return []')
    if offered:
        path.write_text(base + view.replace("CHOOSE_GUARD", 'if not self.staff: raise Refusal("staff only")'))
    else:
        phase = VIEW.replace("OFFER_GUARD", 'if self.screen != "home": return []')
        phase = phase.replace('            CHOOSE_GUARD\n            self.program.advance(self.unit_id)',
                              '            if self.screen == "home": self.screen = "confirm"\n'
                              '            elif self.screen == "confirm": self.program.advance(self.unit_id)')
        path.write_text(base.replace("return None", 'return "blocked"').replace("        pass\n        self._value = 1", '        if self._value == 0: raise Refusal("blocked")\n        self._value = 1') + phase)
    result = run(tmp_path)
    assert not result["errors"]
    items = [row for row in result["items"] if row["semantic"].get("check") == "GC2"]
    if not offered:
        assert not items
        assert not result["runs"][0]["facts"]["agreement"]["unknown"]
        previous = {"predictor": {"receiver": "ui:0", "name": "options"}, "predictor_mode": "offered",
                    "option": "next", "action": {"receiver": "ui:0", "name": "choose", "args": ["next"], "kwargs": {}},
                    "other_predictor": {"receiver": "system", "name": "why_not_advance", "kwargs": {"unit_id": "U1"}},
                    "other_mode": "why_not", "expected_permission": True, "observed": False}
        construction = {"construct": "ui", "receiver": "ui:0", "args": ["U1"], "kwargs": {"staff": False}}
        for prefix in ([construction], [construction, previous["action"]]):
            recheck = replay(derive(tmp_path), prefix, {"world": "small"}, operation="agreement-proof", options={"comparison": previous})
            assert not recheck["matched"] and recheck["not_applicable"]
            assert not recheck["candidates"] and not recheck["unknown"]
    else:
        assert items
        item = next(row for row in items if row["comparison"]["predictor_mode"] == "offered"
                    and "other_predictor" not in row["comparison"])
        assert item["comparison"]["option"] == "next"
        assert item["comparison"]["action"]["name"] == "choose"
        assert item["semantic"]["expected"] is True
        assert item["proof"]["matched"] and item["proof"]["proof"]["compared"] == 1
        assert item["semantic"]["observed"] == "refusal"
        shown = next(row for row in json.loads(render(result, as_json=True))["items"] if row["id"] == item["id"])
        assert shown["comparison"]["predictor"]["name"] == "options"
        assert shown["comparison"]["answer"]["exception"]["message"] == "staff only"
        assert "choose -> refusal 'staff only'" in render(result)
        assert item["semantic"]["receiver"] == "program:View"
        assert item["semantic"]["actor"] == {"unit_id": "U1", "staff": False}
        renamed = {**item["comparison"], "predictor": {"receiver": "ui:renamed", "name": "options"},
                   "action": {**item["comparison"]["action"], "receiver": "ui:renamed"}}
        recheck = replay(derive(tmp_path), [{"construct": "ui", "receiver": "ui:renamed", "args": ["U1"]}],
                         {"world": "small"}, operation="agreement-proof", options={"comparison": renamed})
        assert recheck["matched"]
        assert recheck["candidates"][0]["semantic"] == item["semantic"]
        assert item_id(recheck["candidates"][0]["semantic"]) == item["id"]

    path.write_text(base + VIEW.replace("OFFER_GUARD", "pass").replace("CHOOSE_GUARD", "pass"))
    corrected = run(tmp_path)
    assert not corrected["errors"]
    assert not any(row["semantic"].get("check") == "GC2" for row in corrected["items"])


BRANCH_PROGRAM = '''from dataclasses import dataclass
from pathlib import Path

class Refusal(Exception): pass

@dataclass
class Limits:
    ceiling: int = 1

class Program:
    def __init__(self, limits: Limits = None):
        self.limits = limits or Limits()
        self._ids, self._value = [], 0
        self._ledger = []
        self._alias = self._ledger
        self._cycle = []
        self._cycle.append(self._cycle)
    def add_unit(self, unit_id, name): self._ids.append(unit_id)
    def units(self): return list(self._ids)
    def alpha(self, unit_id):
        if self._value >= self.limits.ceiling or Path("branch.bin").exists(): raise Refusal("used")
        if self._alias is not self._ledger or self._cycle[0] is not self._cycle: raise Refusal("broken alias")
        self._value += 1
        self._ledger.append("alpha")
        Path("branch.bin").write_bytes(b"alpha")
        return "alpha"
    def beta(self, unit_id):
        if self._value >= self.limits.ceiling or Path("branch.bin").exists(): raise Refusal("used")
        if self._alias is not self._ledger or self._cycle[0] is not self._cycle: raise Refusal("broken alias")
        self._value += 1
        self._ledger.append("beta")
        Path("branch.bin").write_bytes(b"beta")
        return "beta"
    def can_alpha(self, unit_id): return self._value < self.limits.ceiling
    def can_beta(self, unit_id): return True
'''


def test_agreement_branches_match_independent_prefix_baselines_without_leaks(tmp_path):
    (tmp_path / "program.py").write_text(BRANCH_PROGRAM)
    spec = derive(tmp_path)
    alpha, beta = ({"name": name, "args": ["U1"]} for name in ("alpha", "beta"))
    small, default = {"world": "small"}, {"world": "default"}
    states = [
        {"test": "calls", "start": small, "prefix": [], "outcomes": []},
        {"test": "calls", "start": small, "prefix": [alpha], "outcomes": ["success"]},
        {"test": "calls", "start": small, "prefix": [beta], "outcomes": ["success"]},
        {"test": "calls", "start": default, "prefix": [alpha], "outcomes": ["success"]},
    ]
    result = replay(spec, [], small, operation="agreement", options={"facts": {}, "states": states})
    assert not result["unknown"]
    assert {(row["start"]["world"], row["prefix"][0]["name"]) for row in result["candidates"]} == {
        ("small", "alpha"), ("small", "beta"), ("default", "alpha"),
    }
    for row in result["candidates"]:
        assert row["semantic"]["predictor"] == "can_beta"
        assert row["outcomes"] == ["success"]
        independent = replay(spec, row["prefix"], row["start"], operation="agreement-proof",
                             options={"comparison": row["comparison"]})
        assert independent["matched"] and not independent["unknown"]
        assert independent["candidates"][0]["semantic"] == row["semantic"]
        assert independent["candidates"][0]["comparison"] == row["comparison"]

"""Public execution facts cover native branches without normative execution."""

import sys

import pytest

from flowguard.behave.project import replay
from flowguard.behave.skeleton import derive

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="native capture needs Python 3.12")

PROGRAM = '''class Refusal(Exception): pass

class Program:
    def __init__(self): self._units = {}
    def add_unit(self, unit_id, name): self._units[unit_id] = 0
    def units(self): return list(self._units)
    def advance(self, unit_id):
        self._units[unit_id] += 1
        return self._units[unit_id]
    def can_advance(self, unit_id): return True
    def can_blocked(self, unit_id): return True
    def blocked(self, unit_id):
        self._units[unit_id] += 0
        raise Refusal("blocked")
    def denied_count(self, unit_id): raise Refusal("unavailable")
    def count(self, unit_id): return self._units[unit_id]
'''


def spec(root):
    (root / "program.py").write_text(PROGRAM)
    value = derive(root)
    value["capture_shape"] = {"wire": 2, "queries": value["entity_queries"]}
    return value


def test_ts2_ledger_keeps_only_the_validated_shipped_prefix(tmp_path):
    value = spec(tmp_path)
    events = [{"name": "add_unit", "args": ["U1", "one"], "outcome": "success"},
              {"name": "advance", "args": ["U1"], "outcome": "success"},
              {"name": "advance", "args": ["U1"], "outcome": "refusal"}]
    result = replay(value, [], operation="witnesses", options={"recordings": [
        {"test": "test_sample", "settings": {}, "events": events, "stop": None}]})
    assert "unsupported" not in result, result
    assert "rule_captures" in result, "TS2 currently drops its actual public facts"
    from flowguard.behave.capture import failure_context, iter_steps
    rows = list(iter_steps(result["rule_captures"]))
    advances = [row for row in rows if row["call"].get("name") == "advance"]
    assert len(advances) == 1
    assert failure_context(advances[0])["outcomes"] == ["success", "success"]
    from flowguard.behave.explore import plain
    assert plain(advances[0]["after"]["values"][0]["value_graph"]) == 1
    assert result["divergences"][0]["index"] == 2


def test_refusals_share_views_and_preserve_the_exact_later_public_prefix(tmp_path):
    value = spec(tmp_path)
    calls = [{"name": "blocked", "args": ["U1"]}] * 8 + [{"name": "advance", "args": ["U1"]}]
    result = replay(value, calls, {"world": "small"})
    assert "unsupported" not in result, result
    from flowguard.behave.capture import failure_context, iter_steps
    from flowguard.behave.explore import plain
    captured = result["rule_captures"]
    row, = list(iter_steps(captured))
    assert failure_context(row) == {"start": {"world": "small"}, "prefix": calls,
                                    "outcomes": ["refusal"] * 8 + ["success"]}
    assert len(captured["states"]) == len(captured["observations"]) == 2
    assert plain(row["args_graph"]) == {"unit_id": "U1"}
    assert plain(result["steps"][-1]["value"]) == 1
    assert plain(row["after"]["values"][0]["value_graph"]) == 1
    assert "denied_count" in row["after"]["unknown"]  # Pure refusal does not discard other facts.
    branch = replay(value, [], {"world": "small"}, operation="agreement-proof", options={"comparison": {
        "predictor": {"receiver": "system", "name": "can_blocked", "kwargs": {"unit_id": "U1"}}, "predictor_mode": "can",
        "action": {"name": "blocked", "args": ["U1"]}}})
    assert "unsupported" not in branch, branch
    assert branch["candidates"][0]["comparison"]["observed"] == "refusal"
    assert len(branch["rule_captures"]["prefixes"]) == 1  # Abandoned refusal branch has no rule witness.
    assert not branch["rule_captures"]["steps"]


SETTINGS_PROGRAM = '''import json
from pathlib import Path
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class Settings:
    factor: int = 3
    def to_data(self): return asdict(self)

class Program:
    def __init__(self, settings=None):
        self._settings = settings if settings is not None else Settings()
        self._units = {}
    def add_unit(self, unit_id, name): self._units[unit_id] = 0
    def units(self): return list(self._units)
    def advance(self, unit_id): self._units[unit_id] = self._settings.factor
    def count(self, unit_id): return self._units[unit_id]
    def _data(self): return {"settings": self._settings.to_data(), "units": self._units}
    def save(self, path): Path(path).write_text(json.dumps(self._data()))
    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text())
        result = cls(Settings(**data["settings"]))
        result._units = data["units"]
        return result
'''


def test_gc5_captures_actual_shipped_baselines_and_excludes_hypothetical_variants(tmp_path):
    (tmp_path / "program.py").write_text(SETTINGS_PROGRAM)
    value = derive(tmp_path)
    value["capture_shape"] = {"wire": 2, "queries": value["entity_queries"]}
    result = replay(value, [], {"world": "small"}, operation="settings", options={
        "setting": "factor", "alphabet_cap": 8, "traces": [{"start": {"world": "small"},
            "prefix": [{"name": "advance", "args": ["U1"]}], "outcomes": ["success"]}]})
    assert "unsupported" not in result, result
    assert result["profiles"] and any(row["replays"] for row in result["profiles"])
    from flowguard.behave.capture import failure_context, iter_steps
    from flowguard.behave.explore import plain
    captured = result["rule_captures"]
    assert captured["complete"], captured["missing"]
    steps = list(iter_steps(captured))
    advances = [row for row in steps if row["call"].get("name") == "advance"]
    assert advances and all(plain(row["after"]["values"][0]["value_graph"]) == 3 for row in advances)
    assert any(row["call"].get("name") == "save" for row in steps)
    assert all(not failure_context(row)["start"].get("settings") for row in steps)

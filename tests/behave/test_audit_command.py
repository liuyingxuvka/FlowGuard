"""Audit combines native checks while sharing identical public test work."""

import sys

import pytest

from flowguard.behave import engine
from flowguard.behave.engine import audit

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot behavior needs Python 3.12")

PROGRAM = '''class Refusal(Exception): pass
class Program:
    def __init__(self):
        self._units = []
        self._value = 0
        with open(__file__.replace("program.py", "data.txt")) as source:
            self._data = source.read()
    def add_unit(self, unit_id, name): self._units.append(unit_id)
    def units(self): return list(self._units)
    def advance(self, unit_id):
        if self._value == 4: raise RuntimeError("fifth advance")
        self._value += 1
    def why_not_advance(self, unit_id): return None
    def value(self, unit_id): return self._value
    def status(self, unit_id): return "ready" if self._value else "new"
'''


def public_tests(root, advances=1):
    (root / "program.py").write_text(PROGRAM)
    (root / "data.txt").write_text("first")
    (root / "tests").mkdir()
    (root / "tests/test_sample.py").write_text('''from program import Program
def test_public():
    subject = Program()
    subject.add_unit("U7", "seven")
''' + '    subject.advance("U7")\n' * advances)


def test_audit_phase_dispatch_matches_native_audit(tmp_path):
    from flowguard.behave.project import replay
    from flowguard.behave.skeleton import derive

    source = ("from dataclasses import dataclass\n@dataclass(frozen=True)\n"
              "class Settings:\n    labels: tuple = ('first', 'second')\n") + PROGRAM
    source = source.replace("    def __init__(self):", "    def __init__(self, settings: Settings = None):")
    source = source.replace("        self._units = []", "        self._settings = settings or Settings()\n        self._units = []")
    (tmp_path / "program.py").write_text(source)
    (tmp_path / "data.txt").write_text("phase input")
    spec = derive(tmp_path)
    start = {"world": "small", "seed": 3}
    options = {"seed": 3, "steps": 1, "node_cap": 8, "alphabet_cap": 16,
               "known": [], "test_replay": {"witnesses": [], "prefixes": []},
               "shared_test_probes": True}
    whole = replay(spec, [], start, operation="audit", options=options)
    walk = replay(spec, [], start, operation="audit-phase", options={**options, "phase": "walk"})
    assert walk["phase"] == "walk"
    for key in ("extent", "events", "witnesses", "features", "states", "traces", "failures"):
        assert walk[key] == whole[key]
    assert walk["execution"]["child_pid"] != whole["execution"]["child_pid"]
    for phase, field in (("crash", "crashes"), ("agreement", "agreement"),
                         ("reach", "reach"), ("stuck", "stuck")):
        result = replay(spec, [], start, operation="audit-phase",
                        options={**options, "phase": phase, "walk": walk})
        assert result["phase"] == phase
        actual = {key: value for key, value in result.items()
                  if key not in {"phase", "execution", "footprint", "handoff"}}
        assert actual == whole[field]


def test_audit_phase_rejects_changed_handoff(tmp_path):
    import copy
    from flowguard.behave.project import UnsupportedWorld, replay
    from flowguard.behave.skeleton import derive

    (tmp_path / "program.py").write_text(PROGRAM)
    (tmp_path / "data.txt").write_text("phase input")
    spec = derive(tmp_path)
    start = {"world": "small", "seed": 3}
    options = {"seed": 3, "steps": 1, "node_cap": 8, "alphabet_cap": 16}
    walk = replay(spec, [], start, operation="audit-phase", options={**options, "phase": "walk"})
    for field in ("outcomes", "observation", "results_graph", "last"):
        changed = copy.deepcopy(walk)
        if field == "outcomes":
            changed["handoff"][field][0] = "refusal"
        elif field == "observation":
            changed["handoff"][field]["graph"]["nodes"] = []
        elif field == "results_graph":
            changed["handoff"][field]["nodes"] = []
        else:
            changed["handoff"][field]["outcome"] = "refusal"
        with pytest.raises(UnsupportedWorld, match="complete handoff"):
            replay(spec, [], start, operation="audit-phase",
                   options={**options, "phase": "crash", "walk": changed})


def test_completed_phases_survive_failure_and_real_input_change_invalidates(tmp_path, monkeypatch):
    import json
    from flowguard.behave.project import UnsupportedWorld

    (tmp_path / "program.py").write_text(PROGRAM)
    data = tmp_path / "data.txt"
    data.write_text("first")
    actual, calls = engine.replay, []
    interruptions = {"agreement": "deliberate interruption before native agreement",
                     "reach": "deliberate interruption before native reach"}

    def interrupted(*args, **kwargs):
        if kwargs.get("operation") == "audit-phase":
            phase = kwargs["options"]["phase"]
            calls.append(phase)
            if phase in interruptions:
                raise UnsupportedWorld(interruptions[phase])
        return actual(*args, **kwargs)

    monkeypatch.setattr(engine, "replay", interrupted)
    options = dict(worlds=["small"], seeds=[0], steps=5, node_cap=8, alphabet_cap=16)
    partial = audit(tmp_path, **options)
    assert not partial["runs"] and len(partial["partial_runs"]) == 1
    progress, = partial["phase_progress"]
    assert calls == ["walk", "crash", "agreement", "reach", "stuck"]
    assert progress["done"] == ["walk", "crash", "stuck"]
    assert progress["pending"] == ["agreement", "reach"]
    failures = [{"phase": phase, "reason": reason} for phase, reason in interruptions.items()]
    assert progress["failures"] == failures
    assert progress["reason"] == interruptions["agreement"]
    assert [{key: row[key] for key in ("phase", "reason")} for row in partial["errors"]] == failures
    saved = [json.loads(path.read_text())["facts"]["phase"]
             for path in engine.cache_root(tmp_path).glob("phase-*.json")]
    assert sorted(saved) == ["crash", "stuck", "walk"]
    assert "stuck" in partial["partial_runs"][0]["facts"]["execution"]["phases"]
    crash, = [item for item in partial["items"] if item["label"] == "CRASH"]
    assert crash["proof"]["matched"]
    assert crash["proof"]["proof"]["execution"]["child_pid"] not in partial["partial_runs"][0]["facts"]["execution"]["child_pids"]
    from flowguard.behave.report import render
    assert json.loads(render(partial, as_json=True))["verdict"] != "CLEAR"

    calls.clear()
    interruptions.clear()
    finished = audit(tmp_path, **options)
    assert len(finished["runs"]) == 1 and not finished["partial_runs"]
    assert calls == ["agreement", "reach"]
    assert finished["phase_progress"][0]["reused"] == ["walk", "crash", "stuck"]
    assert finished["phase_progress"][0]["failures"] == []
    calls.clear()
    assert audit(tmp_path, **options)["facts_reused"] == 1
    assert calls == []
    data.write_text("actual changed input")
    changed = audit(tmp_path, **options)
    assert calls == ["walk", "crash", "agreement", "reach", "stuck"]
    assert changed["phase_progress"][0]["reused"] == []


def test_identical_test_probes_run_once_and_actual_input_invalidates(tmp_path, monkeypatch):
    public_tests(tmp_path)
    original, calls = engine.replay, []
    def recorded(*args, **kwargs):
        calls.append((kwargs.get("operation"), kwargs.get("options", {})))
        return original(*args, **kwargs)
    monkeypatch.setattr(engine, "replay", recorded)
    options = dict(worlds=["small"], seeds=[0, 1], steps=1, node_cap=8, alphabet_cap=16)
    first = audit(tmp_path, **options)
    assert first["test_probes"]["shared"]
    assert first["test_probes"]["agreement"]["compared"] > 0
    assert sum(operation == "witnesses" for operation, _ in calls) == 1
    phases = [options for operation, options in calls if operation == "audit-phase"]
    assert phases and all(options["shared_test_probes"] for options in phases)
    second = audit(tmp_path, **options)
    assert second["facts_reused"] == 2
    assert sum(operation == "witnesses" for operation, _ in calls) == 1
    (tmp_path / "data.txt").write_text("a real changed input")
    changed = audit(tmp_path, **options)
    assert changed["facts_reused"] == 0
    assert sum(operation == "witnesses" for operation, _ in calls) == 2


def test_test_starts_have_separate_budget_and_real_origin(tmp_path):
    public_tests(tmp_path, advances=4)
    result = audit(tmp_path, worlds=["small"], seeds=[0], steps=2, node_cap=8, alphabet_cap=16, use_cache=False)
    assert len(result["runs"]) == 1
    assert result["runs"][0]["facts"]["extent"]["successful_step_budget"] == 2
    assert not result["runs"][0]["facts"]["crashes"]["candidates"]
    assert result["test_starts"]["runs"] == 1
    assert result["test_starts"]["extent"]["successful_step_budget"] == 2
    actual = [item for item in result["items"] if item["label"] == "CRASH"
              and item.get("origin", "").startswith("test-start: ")]
    assert actual and all(item["proof"]["matched"] for item in actual)


def test_base_comparison_preserves_ordinary_crash_checks(tmp_path):
    from .test_gc8_diff import PROGRAM as BASE, source
    path = source(tmp_path)
    path.write_text(BASE.replace('        self._mode = "ready"', '        self._mode = "closed"')
                   .replace('        self._mode = "idle"\n    def status', '        self._mode = "idle"\n        raise RuntimeError("retreat failed")\n    def status'))
    result = audit(tmp_path, base="base", worlds=["small"], seeds=[0], steps=2, node_cap=16, alphabet_cap=16, use_cache=False)
    assert result["diff"]["base_ref"] == "base"
    assert any(item["semantic"]["check"] == "GC6" and item["label"] == "CRASH" for item in result["items"])
    assert any(item["semantic"]["check"] == "GC8" and item["label"] == "LOST" for item in result["items"])
    assert "GC8" not in result["missing_checks"]

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
    assert all(options["shared_test_probes"] for operation, options in calls if operation == "audit")
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

"""Rules judge captured native facts; a failure needs its own fresh replay."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from flowguard.behave.engine import audit
from flowguard.map.requests import store_request

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot behavior needs Python 3.12")


PROGRAM = '''class Program:
    def __init__(self): self._units = {}
    def add_unit(self, unit_id, name): self._units[unit_id] = 0
    def units(self): return list(self._units)
    def tick(self, unit_id): self._units[unit_id] = ACTUAL
    def count(self, unit_id): return self._units[unit_id]
'''

NORM = '''from flowguard.behave.rules import rule, owner

@rule(owner("R1", "The count must be at most 3."))
def test_count_limit(step):
    if step.name == "tick":
        for unit in step.after.units():
            assert step.after.count(unit) <= LIMIT, "count exceeds the owner bound"
'''


def project(root, *, actual=4, limit=3):
    (root / "program.py").write_text(PROGRAM.replace("ACTUAL", str(actual)))
    path = root / "tests/rules/counting/test_count.py"
    path.parent.mkdir(parents=True)
    path.write_text(NORM.replace("LIMIT", str(limit)))
    store_request(root, b"The count must be at most 3.\n", identifier="R1")
    return path


def run(root, **options):
    return audit(root, worlds=["small"], seeds=[0], steps=1, node_cap=8,
                 alphabet_cap=8, **options)


def test_owner_step_rule_is_judged_offline_and_freshly_reproduced(tmp_path):
    project(tmp_path)
    result = run(tmp_path, use_cache=False)
    assert not result["errors"], result["errors"]
    broken = [row for row in result["items"] if row["label"] == "BROKEN"]
    assert len(broken) == 1, result.get("rules")
    item = broken[0]
    assert item["proof"]["matched"] and item["proof"]["state"] == "reproduced"
    assert item["proof"]["judgment_identity"] == result["rules"]["identity"]
    assert item["proof"]["rule_closure"] == item["semantic"]["closure"]
    assert item["proof"]["proof"]["execution"]["child_pid"] != result["runs"][0]["facts"]["execution"]["child_pid"]
    assert item["rule_evidence"]["provenance"][0]["kind"] == "owner"
    assert item["prefix"] == [{"name": "tick", "args": ["U1"]}]
    proof = item["proof"]["proof"]
    assert not any("tests/rules/" in path for path in proof["footprint"]["files"])
    assert any("tests/rules/" in path for path in proof["judgment_footprint"]["files"])
    assert result["runs"][0]["facts"]["events"][0]["resolved_args"] == {"unit_id": "U1"}
    from flowguard.behave.report import render
    payload = json.loads(render(result, as_json=True))
    shown = next(row for row in payload["items"] if row["id"] == item["id"])
    assert shown["proof"] == "python -m flowguard.behave why " + item["id"]
    assert payload["rules"]["identity"] == result["rules"]["identity"]
    assert shown["rule_evidence"]["message"] == "count exceeds the owner bound"
    assert shown["rule_evidence"]["provenance"][0]["kind"] == "owner"
    assert "BROKEN counting.test_count_limit" in render(result) and "owner R1" in render(result)
    replayed = subprocess.run([sys.executable, "-m", "flowguard.behave", "why", item["id"],
                               "--root", str(tmp_path), "--json"],
                              cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True)
    assert replayed.returncode == 0, replayed.stderr
    current = json.loads(replayed.stdout)
    assert current["state"] == "reproduced" and current["matched"]
    assert current["details"]["rule"]["message"] == "count exceeds the owner bound"
    assert current["details"]["rule"]["provenance"][0]["request"] == "R1"


def test_correct_owner_bound_is_clean_in_the_captured_requested_scope(tmp_path):
    project(tmp_path, actual=3)
    result = run(tmp_path, use_cache=False)
    assert not result["errors"] and not [row for row in result["items"] if row["label"] == "BROKEN"]
    rule, = result["rules"]["rules"]
    assert rule["status"] == "clean" and rule["evaluated"] and rule["assertion_hits"]
    assert result["rules"]["capture_scope"]["complete"]


def test_only_norm_edit_reuses_execution_and_cached_callback_rejudges_without_native_work(tmp_path, monkeypatch):
    from flowguard.behave import engine
    path = project(tmp_path)
    first = run(tmp_path)
    assert any(row["label"] == "BROKEN" for row in first["items"])
    path.write_text(NORM.replace("LIMIT", "4"))
    second = run(tmp_path)
    assert second["identity"] == first["identity"]
    assert second["rules"]["identity"] != first["rules"]["identity"]
    assert second["facts_reused"] == len(second["runs"]) == 1
    assert second["runs"][0]["facts"]["execution"] == first["runs"][0]["facts"]["execution"]
    assert not any(row["label"] == "BROKEN" for row in second["items"])
    def forbidden(*args, **kwargs):
        raise AssertionError("a cached-only judgment started native work")
    monkeypatch.setattr(engine, "replay", forbidden)
    cached = engine.judge_cached_rules(tmp_path)
    assert cached["identity"] == second["rules"]["identity"]
    path.write_text(NORM.replace("LIMIT", "3"))
    assert engine.judge_cached_rules(tmp_path)["candidates"]


def test_uncaptured_query_is_not_judged_and_state_failure_has_a_fresh_proof(tmp_path):
    path = project(tmp_path)
    path.write_text(NORM.replace("LIMIT", "3").replace("step.after.count(unit)", "step.after.unknown_count(unit)"))
    result = run(tmp_path)
    assert not any(row["label"] == "BROKEN" for row in result["items"])
    assert result["rules"]["not_judged"]
    assert result["rules"]["rules"][0]["status"] == "not-judged"
    path.write_text('''from flowguard.behave.rules import rule, owner

@rule(owner("R1", "The count must be at most 3."))
def test_count_limit(state):
    for unit in state.units():
        assert state.count(unit) <= 3, "state exceeds owner bound"
''')
    corrected_scope = run(tmp_path)
    item, = [row for row in corrected_scope["items"] if row["label"] == "BROKEN"]
    assert item["semantic"]["fixture"] == "state" and item["proof"]["matched"]


def test_cached_callback_without_facts_does_not_create_a_cache_or_start_native_work(tmp_path, monkeypatch):
    from flowguard.behave import engine
    project(tmp_path, actual=3)
    monkeypatch.setattr(engine, "replay", lambda *a, **k: pytest.fail("native work"))
    assert engine.judge_cached_rules(tmp_path) is None
    assert not engine.cache_root(tmp_path, create=False).exists()


def test_unrecorded_directed_branch_prevents_an_authoritative_rule_clean_claim(tmp_path):
    project(tmp_path, actual=3)
    source = tmp_path / "program.py"
    source.write_text(source.read_text() + "\n    def spare(self, unit_id): self._units[unit_id] = 0\n")
    result = run(tmp_path, use_cache=False)
    assert not result["errors"], result["errors"]
    assert result["runs"][0]["facts"]["events"][0]["call"]["name"] == "tick"
    assert any(row["goal"].get("name") == "spare" for row in result["runs"][0]["facts"]["reach"]["coverage"])
    rule, = result["rules"]["rules"]
    assert rule["evaluated"] and rule["assertion_hits"] and rule["status"] == "not-judged"
    assert not result["rules"]["capture_scope"]["complete"]
    assert any("reach" in reason for reason in result["rules"]["capture_scope"]["missing"])

"""Real Git sources and opposite-side replay decide bounded change claims."""

import json
from pathlib import Path
import subprocess
import sys

import pytest

from flowguard.behave.diffcmd import compare
from flowguard.behave.engine import prove
from flowguard.behave.project import replay
from flowguard.behave.skeleton import derive

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot behavior needs Python 3.12")

PROGRAM = '''class Refusal(Exception): pass
class Program:
    def __init__(self):
        self._units = []
        self._mode = "idle"
        self._steps = 0
    def add_unit(self, unit_id, name): self._units.append(unit_id)
    def units(self): return list(self._units)
    def advance(self, unit_id):
        self._mode = "ready"
    def retreat(self, unit_id):
        self._mode = "idle"
    def status(self, unit_id):
        if self._mode == "ready": return "ready"
        if self._mode == "closed": return "closed"
        return "idle"
'''


def source(root):
    path = root / "program.py"
    path.write_text(PROGRAM)
    for args in (("init", "-q"), ("config", "user.name", "Fixture"), ("config", "user.email", "fixture@example.invalid"),
                 ("add", "program.py"), ("commit", "-qm", "public baseline"), ("tag", "base")):
        subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
    return path


def test_lost_needs_witness_and_two_misses(tmp_path):
    path = source(tmp_path)
    blocked = PROGRAM.replace('        self._mode = "ready"', '        raise Refusal("blocked")\n        self._mode = "ready"')
    path.write_text(blocked)
    goal = {"kind": "query", "receiver": "system", "query": "status", "entity": "unit", "value": "ready"}
    options = dict(worlds=["small"], seeds=[0], steps=4, node_cap=32, alphabet_cap=16, depth=2,
                   checks=False, saved=False, targets=[goal], use_cache=False)
    result = compare(tmp_path, "base", **options)
    item, = result["items"]
    assert item["label"] == "LOST" and item["proof"]["matched"]
    assert item["diff_evidence"]["old"]["matched"]
    assert not item["diff_evidence"]["current"]["matched"]
    assert item["diff_evidence"]["opposite_search"]["extent"]["complete"]
    assert item["diff_evidence"]["opposite_search"]["origin"] == "nearest-guard-complete-search"
    assert prove(tmp_path, item, persist=False)["matched"]
    command = subprocess.run([sys.executable, "-m", "flowguard.behave", "audit", "--root", str(tmp_path),
                              "--base", "base", "--world", "small", "--seeds", "0", "--steps", "4", "--node-cap", "32", "--alphabet-cap", "16", "--json"],
                             cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True)
    assert command.returncode == 0, command.stderr
    assert json.loads(command.stdout)["diff"]["base_ref"] == "base"
    path.write_text(blocked.replace('        self._mode = "idle"\n    def status', '        self._mode = "idle"\n        self._steps += 1\n    def status'))
    capped = compare(tmp_path, "base", **{**options, "node_cap": 1})
    assert not capped["items"] and capped["diff"]["unknown"]
    path.write_text(PROGRAM)
    assert not compare(tmp_path, "base", **options)["items"]


def test_transition_confirmed_by_witness_replay(tmp_path):
    path = source(tmp_path)
    path.write_text(PROGRAM.replace('        self._mode = "ready"', '        self._mode = "closed"'))
    facts = replay(derive(tmp_path), [], {"world": "small", "seed": 0}, operation="diff",
                   options={"steps": 4, "node_cap": 32, "alphabet_cap": 16, "checks": False})
    witness = next(row for row in facts["witnesses"] if row["semantic"].get("kind") == "transition"
                   and row["semantic"]["before"] == "idle" and row["semantic"]["value"] == "closed")
    goal = {**witness["semantic"], "direction": "NEW"}
    options = dict(worlds=["small"], seeds=[0], steps=4, node_cap=32, alphabet_cap=16, depth=2,
                   checks=False, saved=False, targets=[goal], use_cache=False)
    result = compare(tmp_path, "base", **options)
    item, = result["items"]
    assert item["semantic"]["kind"] == "transition" and item["label"] == "NEW"
    assert item["proof"]["matched"] and not item["diff_evidence"]["old"]["matched"]
    assert item["diff_evidence"]["current"]["matched"]
    assert prove(tmp_path, item, persist=False)["matched"]
    # A different old starting value is not an old exit from the current value.
    native = {"semantic": {"check": "GC3", "kind": "query", "query": "status", "entity": "unit", "value": "closed"},
              "search_goal": {"kind": "query", "query": "status", "args": ["U1"], "value": "closed", "comparison": "ne"},
              "negative": True, "prefix": [{"name": "advance", "args": ["U1"]}], "start": {"world": "small"},
              "bounds": {"depth": 0, "node_cap": 16, "alphabet_cap": 16}}
    wrong_start = {"semantic": {"check": "GC8", "kind": "new_stuck", "subject": native["search_goal"]},
                   "goal": native["search_goal"], "base_revision": item["base_revision"], "context": item["context"],
                   "bounds": item["bounds"], "native_case": native}
    rejected = prove(tmp_path, wrong_start, persist=False)
    assert not rejected["matched"] and "starting categorical value" in rejected["reason"]
    path.write_text(PROGRAM)
    corrected = compare(tmp_path, "base", **options)
    assert not corrected["items"] and corrected["diff"]["transitions"]

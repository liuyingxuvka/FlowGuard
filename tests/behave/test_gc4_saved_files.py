"""Old bytes and loading outcomes are reproduced through the one native worker."""

import base64
import hashlib
import json
import subprocess
import sys

import pytest

from flowguard.behave.engine import audit, cache_root, collect_saves, old_releases, prove
from flowguard.behave.project import replay
from flowguard.behave.report import item_id, render
from flowguard.behave.skeleton import derive
from flowguard.behave.why import why

pytestmark = pytest.mark.skipif(sys.version_info < (3, 12), reason="pilot behavior needs Python 3.12")

PROGRAM = '''import json
from pathlib import Path
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    limit: int = 2

class Refusal(Exception): pass

class Program:
    def __init__(self, settings=None):
        self._settings = settings if settings is not None else Settings()
        self._units = {}
    def add_unit(self, unit_id, name): self._units[unit_id] = 0
    def units(self): return list(self._units)
    def advance(self, unit_id):
        if self._units[unit_id] != 0: raise Refusal("not new")
        self._units[unit_id] = 1
    def finish(self, unit_id):
        if self._units[unit_id] != 1: raise Refusal("not active")
        self._units[unit_id] = 2
    def close(self, unit_id):
        if self._units[unit_id] != 2: raise Refusal("not done")
        self._units[unit_id] = 0
    def status(self, unit_id):
        if self._units[unit_id] == 0: return "new"
        if self._units[unit_id] == 1: return "active"
        return "done"
    def save(self, path):
        Path(path).write_text(json.dumps({"schema": 1, "units": self._units,
                                        "config": {"limit": self._settings.limit}EXTRA}))
    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text())
        if "units" not in data: raise Refusal("not a saved world")
        # LOAD_POLICY
        result = cls(Settings(**data["config"]))
        result._units = data["units"]
        return result
'''


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def history(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.name", "Native control")
    git(tmp_path, "config", "user.email", "native@example.invalid")
    path = tmp_path / "program.py"
    path.write_text(PROGRAM.replace("EXTRA", ""))
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "first save format")
    git(tmp_path, "tag", "r1")
    path.write_text(PROGRAM.replace("EXTRA", ', "metadata": {"native": True}'))
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    (fixtures / "committed.json").write_text(json.dumps({"schema": 1, "units": {"U1": 1}, "config": {"limit": 7}}))
    (fixtures / "unrelated.json").write_text('{"not": "a saved file"}')
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "second keys with the same version number")
    git(tmp_path, "tag", "r2")
    return tmp_path


def test_reachable_releases_use_actual_saved_keys_and_keep_committed_loader_inputs(history):
    releases = old_releases(history)
    assert [row["tag"] for row in releases["sources"]] == ["r2", "r1"]
    path = history / "program.py"
    path.write_text(path.read_text().replace('data["units"]', 'data["records"]'))
    (history / "fixtures" / "current.json").write_text(json.dumps({"records": {"U7": 0}, "config": {"limit": 9}}))
    # The committed loader, rather than a release tag, accepts this new fixture format.
    path.write_text(path.read_text().replace('if "units" not in data:', 'if "records" not in data:'))
    git(history, "add", ".")
    git(history, "commit", "-qm", "new committed fixture and loader without a release tag")
    collected = collect_saves(history, steps=2, node_cap=8, alphabet_cap=32)
    assert not collected["no_saved_files"]
    generated = [row for row in collected["saves"] if row["recipe"]]
    assert {row["source"]["tag"] for row in generated} == {"r1", "r2"}
    assert len({json.dumps(row["schema"], sort_keys=True) for row in generated}) == 2
    fixtures = [row for row in collected["saves"] if row["recipe"] is None]
    assert any(row["file"]["name"] == "fixtures/committed.json" for row in fixtures)
    current = next(row for row in fixtures if row["file"]["name"] == "fixtures/current.json")
    assert current["source"]["revision"] == git(history, "rev-parse", "HEAD")
    assert current["source"]["tag"] is None
    assert current["source"]["kind"] == "current-fixture"
    assert not any(row["file"]["name"] == "fixtures/unrelated.json" for row in fixtures)
    assert all(row["old_load"]["outcome"] == "success" for row in collected["saves"])
    assert all(hashlib.sha256(base64.b64decode(row["file"]["bytes"])).hexdigest() == row["file"]["sha256"] for row in generated)
    path.write_text(path.read_text().replace("# LOAD_POLICY", 'raise Refusal("current fixture retired")'))
    refused = replay(derive(history), [], operation="saved", options={"saves": [current], "steps": 1, "node_cap": 2})
    candidate, = refused["candidates"]
    assert candidate["label"] == "LOST" and refused["files"][0]["status"] == "candidate"
    assert candidate["saved_file"]["source"]["kind"] == "current-fixture"
    assert candidate["saved_file"]["recipe"] is None  # HEAD loader acceptance, not an old release save.
    assert git(history, "diff", "--", "program.py")
    assert prove(history, candidate, persist=False)["matched"]
    no_acceptance = replay(derive(history), [], operation="saved", options={"saves": [{**current, "old_load": {}}], "steps": 1, "node_cap": 2})
    assert not no_acceptance["candidates"] and no_acceptance["files"][0]["status"] == "unchecked"


def test_old_acceptance_new_migration_refusal_is_proved_lost_and_why_rechecks(history):
    path = history / "program.py"
    original = path.read_text()
    path.write_text(original.replace("# LOAD_POLICY", 'raise Refusal("migrate or regenerate this file")'))
    result = audit(history, worlds=["small"], seeds=[0], steps=1, node_cap=2, alphabet_cap=32, use_cache=False)
    loading = [item for item in result["items"] if item["semantic"]["kind"] == "loading"]
    assert loading and not result["errors"]
    item = loading[0]
    assert item["label"] == "LOST" and item["id"].startswith("L-")
    assert item["proof"]["matched"] and "LOST" in render(result)
    assert item_id({**item["semantic"], "seed": 999, "order": 7}) == item["id"]
    path.write_text(original)
    changed = why(history, item["id"])
    assert changed["state"] == "no-longer-reproduces" and not changed["matched"]


def test_loading_crash_is_not_swallowed_as_a_designed_refusal(history):
    collected = collect_saves(history, steps=1, node_cap=2, alphabet_cap=32)
    saved = collected["saves"][0]
    path = history / "program.py"
    path.write_text(path.read_text().replace("# LOAD_POLICY", 'raise ValueError("broken decoder")'))
    facts = replay(derive(history), [], operation="saved", options={"saves": [saved], "steps": 1, "node_cap": 2})
    candidate, = facts["candidates"]
    assert candidate["label"] == "LOADING CRASH"
    assert candidate["semantic"]["kind"] == "loading_crash"
    assert prove(history, candidate, persist=False)["matched"]


def test_both_declared_refusals_are_information_and_loaded_config_prefix_survives_resets(history):
    collected = collect_saves(history, steps=1, node_cap=2, alphabet_cap=32)
    saved = next(row for row in collected["saves"] if row["file"]["name"] == "fixtures/committed.json")
    spec = derive(history)
    loaded = replay(spec, [], operation="saved", options={"saves": [saved], "steps": 17, "node_cap": 64, "alphabet_cap": 32})
    assert loaded["files"][0]["status"] == "loaded"
    assert all(row["prefix"][0]["name"] == "load" for row in loaded["candidates"])
    assert loaded["files"][0]["extent"]["successful"] == 17
    assert not loaded["unknown"]
    assert loaded["files"][0]["missing_checks"] == ["GC2", "GC5", "GC6", "GC7", "GC8", "GC9"]
    path = history / "program.py"
    path.write_text(path.read_text().replace("# LOAD_POLICY", 'raise Refusal("retired")'))
    invalid = {"name": "invalid.json", "bytes": base64.b64encode(b'{}').decode("ascii")}
    old = replay(derive(saved["source"]["root"]), [], operation="saves", options={"generate": False, "committed": [invalid]})
    saved = {**old["saves"][0], "source": saved["source"]}
    assert saved["old_load"]["outcome"] == "refusal"
    refused = replay(derive(history), [], operation="saved", options={"saves": [saved], "steps": 1, "node_cap": 2})
    assert refused["files"][0]["status"] == "designed_progress" and not refused["candidates"]


def test_no_history_or_saved_fixture_is_explicit_scope(tmp_path, monkeypatch):
    (tmp_path / "program.py").write_text(PROGRAM.replace("EXTRA", ""))
    collected = collect_saves(tmp_path, steps=1, node_cap=2)
    assert collected["no_saved_files"] and not collected["saves"]
    assert collected["unknown"]
    assert collected["fixture_scope"]["extensions"] == [".json"]
    assert collected["fixture_scope"]["other_formats"] == "not screened"
    (tmp_path / "program.py").write_text(PROGRAM.split("    def save(self, path):", 1)[0])
    monkeypatch.setattr("flowguard.behave.engine.old_releases", lambda root: pytest.fail("history must not be inspected without persistence"))
    absent = collect_saves(tmp_path, steps=1, node_cap=2)
    assert absent["no_saved_files"] and absent["sources"] == absent["saves"] == []
    assert absent["no_history"] is None
    assert absent["unknown"][0]["scope"] == "not-applicable"
    monkeypatch.undo()
    # A genuine loaded configuration can reach active while the fresh shipped root cannot.
    program = PROGRAM.replace("EXTRA", "").replace('        if self._units[unit_id] != 0:',
              '        if self._settings.limit < 7: raise Refusal("disabled under shipped settings")\n        if self._units[unit_id] != 0:')
    (tmp_path / "program.py").write_text(program)
    data = json.dumps({"schema": 1, "units": {"U1": 1}, "config": {"limit": 7}}).encode()
    start = {"files": {"loaded.json": base64.b64encode(data).decode("ascii")}}
    prefix = [{"receiver": "system", "name": "load", "args": [{"$file": "loaded.json"}], "replace": True}]
    loaded = replay(derive(tmp_path), prefix, start)
    assert loaded["steps"][0]["outcome"] == "success"
    semantic = {"check": "GC3", "kind": "query", "receiver": "system", "query": "status", "value": "active",
                "origin": {"kind": "saved-file", "source": "native-control", "file": hashlib.sha256(data).hexdigest(), "schema": None}}
    evidence = {"semantic": semantic, "prefix": prefix, "start": start, "outcomes": ["success"]}
    directory = cache_root(tmp_path) / "witnesses"
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "loaded-control.json").write_text(json.dumps(evidence))
    fresh = audit(tmp_path, worlds=["small"], seeds=[0], steps=1, node_cap=8, alphabet_cap=32, use_cache=False)
    assert any(row["semantic"].get("query") == "status" and row["semantic"].get("value") == "active"
               for row in fresh["runs"][0]["facts"]["reach"]["candidates"])
    assert fresh["saved_files"]["fixture_scope"]["other_formats"] == "not screened"
    assert "other formats not screened" in render(fresh)

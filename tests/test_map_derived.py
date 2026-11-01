"""Source queries preserve real bindings, complete reach and read-only scope."""

import json
from pathlib import Path
import subprocess

from flowguard.map.derived import render, where
from flowguard.map.discover import discover_inventory
from flowguard.map.inventory import build_inventory


def git(root, *arguments):
    return subprocess.check_output(["git", "-C", str(root), *arguments], stderr=subprocess.PIPE).decode().strip()


def repository(root):
    git(root, "init", "-q")
    git(root, "config", "user.name", "Fixture")
    git(root, "config", "user.email", "fixture@example.invalid")


def facts(root):
    inventory = build_inventory(root, [], with_bodies=False, write_cache=False)
    return inventory, discover_inventory(root, inventory, write_cache=False)


PROGRAM = '''import argparse
from pathlib import Path
LIMIT = 3
FILE: str = "state.json"
class Service:
    def __init__(self):
        self.count = 0
        self.initial = "kept"
    def bump(self): self.count += 1
    def replace(self): self.count = LIMIT
    def current(self): return self.count
SERVICE = Service()
def first(): SERVICE.bump()
def second(): SERVICE.replace()
def saved():
    path = Path("records") / FILE
    path.write_text("data")
def parser():
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command")
    first_parser = commands.add_parser("first")
    first_parser.set_defaults(run=first)
    second_parser = commands.add_parser("second")
    second_parser.set_defaults(run=second)
    commands.add_parser("orphan")
    return root
'''


def test_source_reads_initial_fields_and_named_file_destinations(tmp_path):
    (tmp_path / "app.py").write_text(PROGRAM)
    inv, raw = facts(tmp_path)
    file = raw["files"]["app.py"]
    assert "Service.initial" not in file["state"]
    assert file["all_state"]["Service.initial"] == ["Service.__init__"]
    assert "Service.count" in file["functions"]["Service.bump"]["reads"]
    assert "Service.count" in file["functions"]["Service.bump"]["writes"]
    result = where(tmp_path, "LIMIT", inv=inv, raw=raw)
    assert result["constants"][0]["value"] == 3
    assert any(row["symbol"] == "Service.replace" for row in result["references"])
    keyflows = where(tmp_path, view="keyflows", inv=inv, raw=raw)
    counter = next(row for row in keyflows["shared_state"] if row["term"] == "Service.count")
    assert len(counter["entries"]) == 2 and len(counter["writers"]) == 3
    store = next(row for row in keyflows["stores"] if row["symbol"] == "saved")
    assert store["last_component"] == "state.json" and store["value"].replace("\\", "/") == "records/state.json"
    assert not (tmp_path / ".flowguard").exists()


def test_commands_use_their_own_registration_and_unknown_stays_unknown(tmp_path):
    (tmp_path / "app.py").write_text(PROGRAM + '''
def other_parser():
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="command")
    first_parser = commands.add_parser("first")
    first_parser.set_defaults(run=second)
    return root
def dispatched_parser():
    root = argparse.ArgumentParser()
    commands = root.add_subparsers(dest="verb")
    commands.add_parser("dispatch")
    return root
def dispatch():
    options = dispatched_parser().parse_args()
    if options.verb == "dispatch":
        first()
''')
    inv, raw = facts(tmp_path)
    entries = [row for row in raw["files"]["app.py"]["entrypoints"] if row["name"] == "first"]
    assert len(entries) == 2
    assert entries[0]["handlers"] == ["app.py#first"]
    assert entries[1]["handlers"] == ["app.py#second"]
    dispatch = next(row for row in raw["files"]["app.py"]["entrypoints"] if row["name"] == "dispatch")
    assert dispatch["handlers"] == ["app.py#first"]
    result = where(tmp_path, "Service.bump", inv=inv, raw=raw)
    function, = result["functions"]
    assert function["reaching_entries"]
    assert function["unresolved_entries"]
    assert any("orphan" in entry for entry in function["unresolved_entries"])
    assert "never" not in render(result).lower()


def test_reach_is_complete_beyond_old_limits_but_default_views_are_compact(tmp_path):
    size = 2005
    source = "\n".join("def f%d(): return %s" % (index, "f%d()" % (index + 1) if index + 1 < size else "1") for index in range(size))
    (tmp_path / "wide.py").write_text(source + '\nif __name__ == "__main__": f0()\n')
    inv, raw = facts(tmp_path)
    result = where(tmp_path, "f2004", inv=inv, raw=raw)
    assert result["functions"][0]["reaching_entries"]
    tree = where(tmp_path, inv=inv, raw=raw)
    assert "functions" not in tree and tree["unexpanded_functions"] == size
    assert tree["modules"][0]["functions"] == size
    flow = where(tmp_path, view="flow", inv=inv, raw=raw)
    assert "functions" not in flow and "edges" not in flow
    assert flow["unexpanded_edges"] == size - 1
    assert flow["module_edges"][0]["calls"] == size - 1
    assert "unexpanded" in render(tree)


def test_text_uses_same_reference_blobs_and_keeps_wip_parse_errors_visible(tmp_path):
    repository(tmp_path)
    (tmp_path / "core.py").write_text("def old_name(): return 1\n")
    (tmp_path / "guide.md").write_text("Use `old_name` from `core.py`.\n")
    (tmp_path / ".gitattributes").write_text("core.py export-ignore\nguide.md export-ignore\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "old public tree")
    git(tmp_path, "tag", "old")
    (tmp_path / "core.py").write_text("def new_name(): return 2\n")
    (tmp_path / "guide.md").write_text("Use `new_name`.\n")
    (tmp_path / "broken.py").write_text("def not_ready(:\n")
    before = git(tmp_path, "status", "--porcelain")
    historical = where(tmp_path, "guide.md", view="text", at="old")
    assert historical["references"][0]["name"] == "old_name"
    assert historical["references"][0]["state"] == "found in static source"
    current = where(tmp_path, view="text")
    assert current["unexpanded_texts"] == 1 and "references" not in current
    assert any("broken.py" in message for message in current["unknown"])
    assert git(tmp_path, "status", "--porcelain") == before
    assert not (tmp_path / ".flowguard").exists()


def test_architecture_reuse_needs_boolean_shape_and_available_binding(tmp_path):
    (tmp_path / "policy.py").write_text('''TIERS = (1, 2)
def allowed(tier): return tier in TIERS
def duplicate(tier):
    if tier in TIERS: return "accepted"
    return "refused"
def shadowed(tier):
    TIERS = (9,)
    if tier in TIERS: return "other rule"
def numeric(value): return value > 0
def numeric_copy(value):
    if value > 0: return 1
''')
    result = where(tmp_path, view="arch")
    reuse = [row for row in result["drift"] if row["class"] == 1]
    assert any(row["source"] == "policy.py#duplicate" and row["helper"] == "policy.py#allowed" for row in reuse)
    assert not any(row["source"] in {"policy.py#shadowed", "policy.py#numeric_copy"} for row in reuse)


def test_supplied_test_reach_stays_separate_from_shipped_hits(tmp_path):
    (tmp_path / "core.py").write_text("def helper(): return 1\n")
    result = where(tmp_path, "helper", execution={"state": "recorded", "coverage": {"hit_functions": []},
                    "test_reach": {"core.py#helper": ["tests/test_core.py::test_live"]}})
    observed = result["functions"][0]["execution"]
    assert observed["shipped_observed"] is False
    assert observed["tests"] == ["tests/test_core.py::test_live"]
    stale = where(tmp_path, "helper", execution={"state": "stale", "test_reach": {"core.py#helper": ["old"]}})
    assert stale["functions"][0]["execution"]["tests"] == "not recorded in this clone"
    tests_only = where(tmp_path, "helper", execution={"state": "recorded", "coverage": None,
                      "test_reach": {"core.py#helper": ["tests/test_core.py::test_live"]}})
    assert tests_only["functions"][0]["execution"]["shipped_observed"] is None


def test_request_and_change_lookup_uses_real_immutable_records(tmp_path):
    from flowguard.map.common import sha256_bytes
    from flowguard.map.records import prepare_change, publish_change
    from flowguard.map.requests import store_request
    repository(tmp_path)
    source = tmp_path / "core.py"
    source.write_text("def changed(): return 1\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "source baseline")
    baseline = git(tmp_path, "rev-parse", "HEAD")
    store_request(tmp_path, b"Keep the changed function visible.\n", identifier="R8")
    source.write_text("def changed(): return 2\n")
    prepared = prepare_change(tmp_path, goal="R8: static lookup fixture", links=[{"id": "R8", "part": True}],
        base={"git": baseline}, inputs={"core.py": sha256_bytes(source.read_bytes())},
        merged={"schema": "flowguard.map.v1", "components": [], "flows": []}, model_bytes={}, deleted=[],
        checked="Fixture record for static lookup, not a product promotion", changed_paths=["core.py"])
    publish_change(tmp_path, prepared)
    request = where(tmp_path, "R8")
    assert request["requests"][0]["id"] == "R8"
    assert request["changes"][0]["implemented_by"] == ["core.py:changed"]
    change = where(tmp_path, prepared["id"])
    assert change["changes"][0]["id"] == prepared["id"]
    function = where(tmp_path, "changed")["functions"][0]
    assert function["last_requests"] == ["R8"] and function["last_change"] == prepared["id"]
    assert function["changed_since"]["state"] == "unknown"

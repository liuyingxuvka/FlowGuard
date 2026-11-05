"""Retained source/request functions do not enter removed map/target owners."""
import json
import os
from pathlib import Path
import subprocess
import sys

from flowguard.map.derived import where
from flowguard.map.requests import glossary_entries, owner_words, retire_request, store_request


def write(root, path, text):
    destination = root / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(text, encoding="utf-8")


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE).decode().strip()


def test_retained_modules_import_without_any_legacy_map_or_target_owner(tmp_path):
    engine = Path(__file__).resolve().parents[1]
    script = r'''import importlib.abc, sys
class RefuseLegacy(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname in {"flowguard.map.mapfile", "flowguard.map.target", "flowguard.map.targetfile", "flowguard.map.proof"}:
            raise AssertionError("retained static module imported " + fullname)
sys.meta_path.insert(0, RefuseLegacy())
from flowguard.map import derived, requests, records, textrules
from flowguard.map.flow_sources import declarations
from flowguard.flow.project import request_lines
from pathlib import Path
root = Path(sys.argv[1])
requests.store_request(root, b"original owner words", identifier="R1")
assert request_lines(root, ["R1"]) == [("R1", "original owner words")]
(root / "app.py").write_text("raise AssertionError(\"source must not execute\")\ndef query(): return 1\n")
(root / ".flowguard/map.json").write_text("{broken old map")
assert derived.where(root, "query")["functions"][0]["id"] == "app.py#query"
textrules.report(root)
print("retained owners imported")
'''
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)], cwd=tmp_path,
                            env={**os.environ, "PYTHONPATH": str(engine)}, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_malformed_obsolete_artifacts_do_not_change_any_static_source_view(tmp_path):
    write(tmp_path, "app.py", 'raise AssertionError("source queries must not execute this")\nVALUE = 1\ndef read(): return VALUE\n')
    write(tmp_path, "guide.md", "Use `read` to inspect `VALUE`.\n")
    before = {(view, name): where(tmp_path, name, view=view) for view, name in
              (("tree", None), ("name", "read"), ("flow", "read"), ("arch", None),
               ("keyflows", None), ("text", "guide.md"))}
    for name in ("map.json", "target/map.json", "target/base.json", "changes/broken.json"):
        write(tmp_path, ".flowguard/" + name, "{broken obsolete record")
    for key, expected in before.items():
        assert where(tmp_path, key[1], view=key[0]) == expected


def test_request_archival_ignores_broken_old_target_and_receipt(tmp_path, monkeypatch):
    from flowguard.map import records
    write(tmp_path, ".flowguard/target/map.json", "{broken")
    write(tmp_path, ".flowguard/target/base.json", "{broken")
    write(tmp_path, ".flowguard/changes/old.json", "{broken")
    monkeypatch.setattr(records, "change_records", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("request lookup entered removed change records")))
    raw = "owner wording\r\n未经改写\r\n".encode()
    stored = store_request(tmp_path, raw, identifier="R1")
    assert "stored_during" not in stored
    assert (tmp_path / ".flowguard/requests/R1.md").read_bytes() == raw
    assert owner_words(tmp_path)["rows"][0]["first_line"] == "owner wording"


def test_request_integrity_retirement_and_owner_glossary_remain_real_byte_facts(tmp_path):
    raw = "Keep the original boundary.\r\n".encode()
    store_request(tmp_path, raw, identifier="R1")
    glossary = "边界 = boundary, scope\r\n".encode()
    store_request(tmp_path, glossary, identifier="G1", kind="glossary")
    assert glossary_entries(glossary) == [("边界", ("boundary", "scope"))]
    assert (tmp_path / ".flowguard/requests/G1.md").read_bytes() == glossary
    retire_request(tmp_path, "R1")
    rows = {row["id"]: row for row in owner_words(tmp_path)["rows"]}
    assert rows["R1"]["retired"] and not rows["G1"]["retired"]
    (tmp_path / ".flowguard/requests/G1.md").write_text("AI replacement words")
    changed = {row["id"]: row for row in owner_words(tmp_path)["rows"]}["G1"]
    assert changed["edited"] and changed["first_line"] == ""
    assert (tmp_path / ".flowguard/requests/R1.md").read_bytes() == raw


def test_source_ownership_comes_from_modules_and_flow_coverage_not_old_map(tmp_path):
    write(tmp_path, "app.py", "from helper import answer\ndef run(): return answer()\n")
    write(tmp_path, "helper.py", "def answer(): return 1\n")
    write(tmp_path, ".flowguard/map.json", json.dumps({"components": [
        {"id": "fabricated", "files": ["app.py", "helper.py"]}], "flows": []}))
    write(tmp_path, ".flowguard/flow/answer.py", 'from flowguard.flow import Model\n'
          'm=Model("answer", covers=["helper.py:answer"])\nMODEL=m\n')
    result = where(tmp_path, "answer")
    assert result["functions"][0]["owner"] == "helper.py"
    assert result["functions"][0]["model_bindings"][0]["model"] == "answer"
    drift = where(tmp_path, view="arch")["drift"]
    assert any(row["kind"] == "module_without_boundary" and row["external_owner"] == "app.py"
               for row in drift)


def test_git_ref_source_view_ignores_obsolete_map_and_never_imports_source(tmp_path):
    git(tmp_path, "init", "-q")
    write(tmp_path, "app.py", 'raise AssertionError("not imported")\ndef old(): return 1\n')
    write(tmp_path, ".flowguard/map.json", "{broken")
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "old")
    old = git(tmp_path, "rev-parse", "HEAD")
    write(tmp_path, "app.py", "def current(): return 2\n")
    assert where(tmp_path, "old", at=old)["functions"][0]["id"] == "app.py#old"
    assert not (tmp_path / ".flowguard/cache").exists()
    assert not where(tmp_path, "old")["functions"]

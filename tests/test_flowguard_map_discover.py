"""Discovery (reverse wrap): entrypoints, side effects and state writers from real code."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flowguard.map.discover import component_summary, discover, file_facts

ROOT = Path(__file__).resolve().parents[1]

APP = '''
import requests
from notes.store import NoteStore

class App:
    def __init__(self):
        self.routes = {}
    def route(self, path, methods=None):
        def wrap(fn):
            self.routes[path] = fn
            return fn
        return wrap

app = App()
store = NoteStore("notes.db")

@app.route("/notes", methods=["POST"])
def create_note(body):
    store.add(body)
    requests.post("https://hooks.example/notes", json=body)

@app.route("/notes")
def list_notes():
    return store.all()

def tally(items):
    requests = []
    requests.append(len(items))
    return requests
'''

STORE = '''
import sqlite3

class NoteStore:
    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.count = 0
    def add(self, body):
        cur = self.conn.cursor()
        cur.execute("insert into notes values (?)", (body,))
        self.count += 1
    def all(self):
        return self.conn.cursor().execute("select * from notes").fetchall()
'''

CLI = '''
import argparse
import shutil

def main(argv=None):
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("backup")
    if p.parse_args(argv).cmd == "backup":
        shutil.copy("notes.db", "notes.bak")

if __name__ == "__main__":
    main()
'''


def write_project(root: Path) -> None:
    (root / "notes").mkdir()
    (root / "tests").mkdir()
    (root / "notes" / "__init__.py").write_text("", encoding="utf-8")
    (root / "notes" / "app.py").write_text(APP, encoding="utf-8")
    (root / "notes" / "store.py").write_text(STORE, encoding="utf-8")
    (root / "notes" / "cli.py").write_text(CLI, encoding="utf-8")
    (root / "tests" / "test_store.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)


def map_cli(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "flowguard", "map", "--root", str(root), *args],
                          cwd=ROOT, capture_output=True, text=True, check=False)


class DiscoverTests(unittest.TestCase):
    def test_routes_commands_effects_and_state_writers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_project(root)
            raw = discover(root, {"notes/app.py": "notes.app", "notes/store.py": "notes.store",
                                  "notes/cli.py": "notes.cli", "notes/__init__.py": "notes"})
            found = component_summary(raw, ["notes/app.py", "notes/store.py", "notes/cli.py"])
        self.assertIn("http_route POST /notes -> notes/app.py:create_note", found["entrypoints"])
        self.assertIn("http_route GET /notes -> notes/app.py:list_notes", found["entrypoints"])
        self.assertIn("cli_command backup -> notes/cli.py:main", found["entrypoints"])
        # POST reaches the database through NoteStore.add and the network directly.
        self.assertEqual(["db", "network"], found["entrypoint_effect_reach"]["http_route POST /notes"])
        self.assertEqual(["fs_write"], found["entrypoint_effect_reach"]["cli_command backup"])
        self.assertEqual(["NoteStore.__init__", "NoteStore.add"], found["state_writers"]["NoteStore.count"])

    def test_local_variable_named_like_a_library_is_not_an_effect(self) -> None:
        facts = file_facts(APP, "notes.app", "notes", "notes/app.py")
        self.assertEqual([], facts["functions"]["tally"]["effects"])
        self.assertEqual("network", facts["functions"]["create_note"]["effects"][0][0])

    def test_scan_hints_and_lint_findings_come_from_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_project(root)
            self.assertEqual(0, map_cli(root, "scan").returncode)
            data = json.loads((root / ".flowguard" / "map.json").read_text(encoding="utf-8"))
            hints = data["components"][0]["_hint"]["discovered"]
            self.assertIn("http_route POST /notes -> notes/app.py:create_note", hints["entrypoints"])
            lint = map_cli(root, "lint").stdout
            self.assertIn("WARN  entrypoint_unlisted", lint)
            self.assertIn("notes/app.py:create_note", lint)
            self.assertIn("effects_undeclared", lint)
            self.assertNotIn("notes/app.py is not imported", lint)
            # Listing the entrypoints and declaring effects clears those findings.
            data["components"][0]["entrypoints"] = ["notes/app.py:create_note", "notes/app.py:list_notes", "notes/cli.py:main"]
            data["components"][0]["side_effects"] = ["writes notes to sqlite", "posts a webhook", "copies the database file"]
            (root / ".flowguard" / "map.json").write_text(json.dumps(data), encoding="utf-8")
            lint = map_cli(root, "lint").stdout
            self.assertNotIn("entrypoint_unlisted", lint)
            self.assertNotIn("effects_undeclared", lint)

    def test_discover_command_prints_reach(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_project(root)
            map_cli(root, "scan")
            out = map_cli(root, "discover").stdout
        self.assertIn("reach   http_route POST /notes -> db, network", out)


if __name__ == "__main__":
    unittest.main()

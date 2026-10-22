"""Discovery (reverse wrap): entrypoints, side effects and state writers from real code."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

from flowguard.map.discover import component_summary, console_scripts, discover, discover_inventory, file_facts
from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory
from flowguard.map.lint import entrypoint_coverage_findings, run_lint, scoped_architecture_findings
from flowguard.map.scan import guess_tests, new_map, propose_components

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
            hints = data["components"][0]["_hint"]
            self.assertEqual({"file_count", "loc", "public_symbols_sample"}, set(hints))
            self.assertEqual([], data["components"][0]["entrypoints"])
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


class DiscoveryBoundaryTests(unittest.TestCase):
    def test_console_scripts_from_all_packaging_formats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "cli.py").write_text("def main(): pass\n", encoding="utf-8")
            (root / "pyproject.toml").write_text('[project.scripts]\ntoml-cli = "cli:main"\n', encoding="utf-8")
            (root / "setup.cfg").write_text('[options.entry_points]\nconsole_scripts =\n    cfg-cli = cli:main\n', encoding="utf-8")
            (root / "setup.py").write_text('setup(entry_points={"console_scripts": ["py-cli = cli:main"]})', encoding="utf-8")
            self.assertEqual({"toml-cli", "cfg-cli", "py-cli"}, {name for name, _, _ in console_scripts(root)})
            raw = discover_inventory(root, build_inventory(root, DEFAULT_IGNORE))
            scripts = [entry for entry in raw["files"]["cli.py"]["entrypoints"] if entry["kind"] == "console_script"]
            self.assertEqual(3, len(scripts))
            self.assertTrue(all(entry["symbol"] == "main" for entry in scripts))

    def test_local_imports_and_callback_arguments_reach_effects_without_leaking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sink.py").write_text('def save():\n    open("db", "w").write("x")\n'
                                           'class Store:\n    def save(self):\n        open("class-db", "w")\n', encoding="utf-8")
            (root / "app.py").write_text(
                'def entry():\n    from sink import save as callback\n    register(callback)\n'
                'def unrelated():\n    callback()\n'
                'def class_entry():\n    from sink import Store\n    Store().save()\n', encoding="utf-8")
            raw = discover(root, {"app.py": "app", "sink.py": "sink"}, write_cache=False)
            found = component_summary(raw, ["app.py"])
            self.assertEqual(["sink.py#save"], raw["edges"]["app.py#entry"])
            self.assertNotIn("app.py#unrelated", raw["edges"])
            self.assertIn("sink.py#Store.save", raw["edges"]["app.py#class_entry"])
            from flowguard.map.discover import reachable_effects
            self.assertEqual({"fs_write"}, set(reachable_effects(raw, "app.py#entry")))

    def test_constructors_env_copy_and_initializer_only_state_are_not_effects(self) -> None:
        facts = file_facts(
            'import requests\nimport os\nclass Store:\n'
            '    def __init__(self):\n        self.client = requests.Session()\n        self.cache = {}\n'
            'def harmless():\n    client = requests.Session()\n    env = os.environ.copy()\n'
            'def send():\n    client = requests.Session()\n    client.post("https://example.org")\n',
            "app", "", "app.py")
        self.assertEqual({}, facts["state"])
        self.assertEqual([], facts["functions"]["harmless"]["effects"])
        self.assertEqual([], facts["functions"]["Store.__init__"]["effects"])
        self.assertEqual(["network"], [kind for kind, _, _ in facts["functions"]["send"]["effects"]])

    def test_reverse_entry_coverage_warns_even_without_any_model_and_respects_explicit_reason(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app.py").write_text(
                'def refund():\n    open("refund.txt", "w").write("done")\n'
                'def pure():\n    return 1\n', encoding="utf-8")
            inv = build_inventory(root, DEFAULT_IGNORE)
            raw = discover_inventory(root, inv)
            data = {"components": [{"id": "orders", "files": ["app.py"], "models": [],
                                   "entrypoints": ["app.py:refund", "app.py:pure"]}]}
            findings = entrypoint_coverage_findings(raw, data, inv, {})
            self.assertEqual(["entrypoint_unmodeled"], [finding.code for finding in findings])
            self.assertIn("refund", findings[0].message)
            data["components"][0]["models"] = [".flowguard/models/orders.py"]
            self.assertEqual([], entrypoint_coverage_findings(raw, data, inv,
                             {".flowguard/models/orders.py": {"app.py:refund"}}))

    def test_scoped_architecture_reports_cycle_error_with_import_lines_and_preserves_debt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.py").write_text("import b\ndef act(): return b.run()\n", encoding="utf-8")
            (root / "b.py").write_text("import a\ndef run(): return 1\n", encoding="utf-8")
            inv = build_inventory(root, DEFAULT_IGNORE)
            data = {"components": [{"id": "a", "files": ["a.py"], "layer": "low", "tests": [], "models": []},
                                   {"id": "b", "files": ["b.py"], "layer": "high", "tests": [], "models": []}],
                    "layers": ["high", "low"], "flows": [], "accepted_debts": []}
            findings = scoped_architecture_findings(root, data, inv, {"a"})
            cycle = next(finding for finding in findings if finding.code == "dependency_cycle")
            self.assertEqual("error", cycle.level)
            self.assertIn("a.py:1 import b", cycle.message)
            layer = next(finding for finding in findings if finding.code == "layer_violation")
            self.assertIn("a.py:1 import b", layer.message)
            data["accepted_debts"] = [{"code": "dependency_cycle", "component": "a", "contains": "a <-> b", "reason": "legacy constraint"}]
            accepted = scoped_architecture_findings(root, data, inv, {"a"})
            self.assertEqual("info", next(finding.level for finding in accepted if finding.code == "dependency_cycle"))
            self.assertEqual([], scoped_architecture_findings(root, data, inv, set()))

    def test_scan_max_components_and_import_test_guess_preserve_unique_ownership(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for number in range(30):
                target = root / "pkg" / f"part{number}"
                target.mkdir(parents=True)
                for child in range(10):
                    (target / f"mod{child}.py").write_text(f"def public{child}(): return {child}\n", encoding="utf-8")
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_api.py").write_text("from pkg.part0 import mod0\ndef test_api(): assert mod0.public0() == 0\n", encoding="utf-8")
            (tests / "_util.py").write_text("from pkg.part0 import mod0\n", encoding="utf-8")
            inv = build_inventory(root, DEFAULT_IGNORE)
            proposals = propose_components(inv, max_components=5)
            self.assertLessEqual(len(proposals), 5)
            from flowguard.map.mapfile import component_files
            owned = [path for component in proposals for path in component_files(component, inv)]
            self.assertEqual(set(inv.source) - set(inv.tests), set(owned))
            self.assertEqual(len(owned), len(set(owned)))
            self.assertTrue(all(len(component["_hint"]["public_symbols_sample"]) <= 8 for component in proposals))
            self.assertEqual(["tests/test_api.py"], guess_tests(["pkg/part0/mod0.py"], inv.tests, inv))
            with self.assertRaisesRegex(ValueError, "at least 1"):
                propose_components(inv, max_components=0)

    def test_renamed_local_variables_match_duplicate_bodies_but_global_calls_do_not(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = ("def total(items):\n    result = 0\n    for item in items:\n"
                        "        if item > 0:\n            result += item * 2\n"
                        "        else:\n            result -= item\n    result *= 2\n    return transform(result)\n")
            renamed = original.replace("total", "sum_values").replace("items", "values").replace("item", "value").replace("result", "answer")
            (root / "a.py").write_text(original, encoding="utf-8")
            (root / "b.py").write_text(renamed, encoding="utf-8")
            (root / "c.py").write_text(renamed.replace("transform", "different_operation"), encoding="utf-8")
            inv = build_inventory(root, DEFAULT_IGNORE)
            data = {"components": [{"id": name, "files": [f"{name}.py"], "tests": [], "models": []}
                                   for name in ("a", "b", "c")], "flows": [], "layers": [], "accepted_debts": []}
            duplicates = [finding for finding in run_lint(root, data, inv) if finding.code == "duplicate_code"]
            self.assertEqual(1, len(duplicates))
            self.assertIn("['a', 'b']", duplicates[0].message)
            self.assertNotIn("c.py", duplicates[0].message)

    def test_registered_runners_and_pytest_hooks_are_real_external_importers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "library.py").write_text("def work(): return 1\n", encoding="utf-8")
            (root / "plugin.py").write_text("def pytest_sessionstart(session): pass\n", encoding="utf-8")
            runner = root / ".flowguard/verification/owners/sample/run_checks.py"
            runner.parent.mkdir(parents=True)
            runner.write_text("from library import work\n", encoding="utf-8")
            inv = build_inventory(root, DEFAULT_IGNORE)
            data = {"components": [{"id": "library", "files": ["library.py", "plugin.py"], "tests": [],
                                   "models": [runner.relative_to(root).as_posix()]}], "flows": [], "layers": [], "accepted_debts": []}
            findings = run_lint(root, data, inv)
            self.assertFalse(any(finding.code == "never_imported" for finding in findings))


if __name__ == "__main__":
    unittest.main()


def test_unlisted_entrypoints_group_by_component_and_strength(tmp_path):
    from flowguard.map.lint import discovery_findings

    source = tmp_path / "commands.py"
    source.write_text("import click\n" + "\n".join(
        f"@click.command()\ndef command_{i}(): pass\n" for i in range(5)))
    data = {"components": [{"id": "commands", "files": ["commands.py"], "entrypoints": []}]}
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    raw = discover_inventory(tmp_path, inv)
    findings = [f for f in discovery_findings(raw, data, inv) if f.code == "entrypoint_unlisted"]
    assert len(findings) == 1
    assert findings[0].level == "warn"
    assert "5 entrypoints" in findings[0].message
    assert "full list: python -m flowguard map discover --component commands" in findings[0].message
    # At the threshold the individual anchors remain visible, with unchanged severity.
    raw["files"]["commands.py"]["entrypoints"] = raw["files"]["commands.py"]["entrypoints"][:3]
    findings = [f for f in discovery_findings(raw, data, inv) if f.code == "entrypoint_unlisted"]
    assert len(findings) == 3
    assert all(f.level == "warn" for f in findings)


@pytest.mark.parametrize('operation', ['self.value = 1', 'self.value[0] = 1', 'self.value[0] += 1',
                                      'self.value += 1', 'del self.value[0]', 'del self.value',
                                      'self.value.append(1)'])
def test_state_writes_include_delete_and_existing_assignment_forms(operation):
    source = ('class Proxy:\n    def __init__(self):\n        self.value = []\n        self.label = "only init"\n'
              '    def write(self):\n        ' + operation + '\n')
    facts = file_facts(source, 'proxy', '', 'proxy.py')
    assert facts['functions']['Proxy.write']['writes'] == ['Proxy.value']
    assert facts['state']['Proxy.value'] == ['Proxy.__init__', 'Proxy.write']
    assert 'Proxy.label' not in facts['state']
    assert 'Proxy.label' not in facts['functions']['Proxy.__init__']['writes']


@pytest.mark.parametrize('design_only', [False, True])
def test_new_writer_of_modeled_state_is_reported(tmp_path, monkeypatch, design_only):
    from flowguard.map import discover as discovery
    from flowguard.map.check import run_check
    from flowguard.map.cli import _context

    def write(path, text):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')

    write('pkg/__init__.py', '')
    write('pkg/proxy.py', '''class Proxy:
    def __init__(self):
        self._parts = []
        self._map = {}
        self.label = 'only init'
    def __setitem__(self, key, value):
        self._parts[0] = value
        self._map[key] = 0
    def move_to_end(self, key):
        self._parts.append(key)
        self._map[key] = 1
    def __delitem__(self, key):
        del self._map[key]

class Other:
    def __init__(self):
        self._map = {}
    def clear(self, key):
        del self._map[key]
''')
    write('other.py', 'class Proxy:\n    def __delitem__(self, key):\n        del self._map[key]\n')
    model = ('MODEL_ID="proxy_model"\nCOMPONENTS=["proxy"]\n'
             'IMPLEMENTED_BY={"Set":"pkg/proxy.py:Proxy.__setitem__"}\n'
             'def build_explorer(): pass\n'
             'def conformance():\n    from pkg.proxy import Proxy\n    return Proxy()\n')
    if design_only:
        model += 'DESIGN_ONLY="Planned state boundary"\n'
    write('.flowguard/models/proxy.py', model)
    data = dict(schema='flowguard.map.v1', components=[
        dict(id='proxy', files=['pkg/*.py'], summary='Proxy ordering', responsibilities=['order parts'],
             tests=[], models=[], depends_on=[], status='draft'),
        dict(id='other', files=['other.py'], summary='Other', responsibilities=['unrelated state'],
             tests=[], models=[], depends_on=[], status='draft')])
    write('.flowguard/map.json', json.dumps(data))
    current, inv = _context(tmp_path)
    raw = discover_inventory(tmp_path, inv)
    assert 'Proxy.__delitem__' in raw['files']['pkg/proxy.py']['state']['Proxy._map']
    original = discovery.discover_inventory
    calls = []

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(discovery, 'discover_inventory', counted)
        warnings = [f for f in run_check(tmp_path, current, inv) if f.code == 'model_writer_unbound']
    assert len(calls) == 1
    if design_only:
        assert not warnings
        return
    assert len(warnings) == 2
    assert all(f.level == 'warn' and f.component == 'proxy' for f in warnings)
    assert all('model proxy_model' in f.message and 'pkg/proxy.py:Proxy.__setitem__' in f.message for f in warnings)
    assert any('pkg/proxy.py:Proxy.move_to_end' in f.message for f in warnings)
    assert any('pkg/proxy.py:Proxy.__delitem__' in f.message for f in warnings)
    assert map_cli(tmp_path, 'check').returncode == 0
    assert len([f for f in run_lint(tmp_path, current, inv) if f.code == 'model_writer_unbound']) == 2

    data['accepted_debts'] = [dict(code='model_writer_unbound', component='proxy', contains=symbol,
                                    reason='An existing ordering path awaits model extension')
                              for symbol in ['Proxy.move_to_end', 'Proxy.__delitem__']]
    write('.flowguard/map.json', json.dumps(data))
    current, inv = _context(tmp_path)
    assert [f.level for f in run_check(tmp_path, current, inv) if f.code == 'model_writer_unbound'] == ['info', 'info']
    lint = run_lint(tmp_path, current, inv)
    assert len([f for f in lint if f.code == 'model_writer_unbound' and f.level == 'info']) == 2
    assert not any(f.code == 'debt_stale' for f in lint)

    # Exclusions come from every registered model, including a separate runner.
    data.pop('accepted_debts')
    runner = '.flowguard/verification/owners/proxy_writer/run_checks.py'
    data['components'][0]['models'] = [runner]
    write(runner, 'from flowguard.map.runner import run_owner\n'
          'IMPLEMENTED_BY={"Delete":"pkg/proxy.py:Proxy.__delitem__"}\n'
          'NOT_MODELED={"pkg/proxy.py:Proxy.move_to_end":"Ordering is covered by its direct test"}\n'
          'raise SystemExit(run_owner(lambda:0))\n')
    write('.flowguard/map.json', json.dumps(data))
    current, inv = _context(tmp_path)
    assert not any(f.code == 'model_writer_unbound' for f in run_check(tmp_path, current, inv))

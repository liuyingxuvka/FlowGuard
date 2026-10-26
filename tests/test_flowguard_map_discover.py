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

    def test_registered_contracts_and_pytest_hooks_are_real_external_importers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "library.py").write_text("def work(): return 1\n", encoding="utf-8")
            (root / "plugin.py").write_text("def pytest_sessionstart(session): pass\n", encoding="utf-8")
            model = root / ".flowguard/models/sample.py"
            model.parent.mkdir(parents=True)
            model.write_text('MODEL_ID="sample"\nIMPLEMENTED_BY={"Work":"library.py:work"}\n'
                             'from library import work\ndef build_explorer(): pass\ndef conformance(): pass\n', encoding="utf-8")
            inv = build_inventory(root, DEFAULT_IGNORE)
            data = {"components": [{"id": "library", "files": ["library.py", "plugin.py"], "tests": [],
                                   "models": [model.relative_to(root).as_posix()]}], "flows": [], "layers": [], "accepted_debts": []}
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


def test_new_writer_of_modeled_state_is_reported(tmp_path, monkeypatch):
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

    # Exclusions come from every registered model, including a separate contract.
    data.pop('accepted_debts')
    separate = '.flowguard/models/proxy_writer.py'
    data['components'][0]['models'] = [separate]
    write(separate, 'MODEL_ID="proxy_writer"\n'
          'IMPLEMENTED_BY={"Delete":"pkg/proxy.py:Proxy.__delitem__"}\n'
          'NOT_MODELED={"pkg/proxy.py:Proxy.move_to_end":"Ordering is covered by its direct test"}\n'
          'def build_explorer(): pass\ndef conformance(): pass\n')
    write('.flowguard/map.json', json.dumps(data))
    current, inv = _context(tmp_path)
    assert not any(f.code == 'model_writer_unbound' for f in run_check(tmp_path, current, inv))


def test_external_promise_needs_a_model_or_a_reason(tmp_path):
    (tmp_path / "cli.py").write_text("def business(value):\n    return value + 1\n\ndef main():\n    return business(0)\n")
    (tmp_path / "pyproject.toml").write_text('[project.scripts]\nplain = "cli:main"\n')
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests/test_cli.py").write_text(
        "from cli import business\n\ndef test_business():\n    assert business(0) == 1\n")
    directory = tmp_path / ".flowguard/models"
    directory.mkdir(parents=True)
    model = directory / "business.py"
    source = '''from flowguard import FunctionResult, Invariant, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact
MODEL_ID = "business"
COMPONENTS = ["commands"]
IMPLEMENTED_BY = {"Increment": "cli.py:business"}
TESTED_BY = {"incremented": ["tests/test_cli.py:test_business"]}
NOT_MODELED = {}
class Increment:
    name = "Increment"
    def __init__(self, delta=1): self.delta = delta
    def apply(self, value, state):
        return [FunctionResult(value + self.delta, (value, value + self.delta))]
def explorer(delta=1):
    return Explorer(Workflow((Increment(delta),)), initial_states=((0, 1),), external_inputs=(0, 1),
                    max_sequence_length=1, progress_steps=0,
                    invariants=(Invariant("incremented", "increments once", lambda s, t: s[1] == s[0] + 1),))
def build_explorer(): return explorer()
def broken_variants(): return {"no_increment": explorer(0)}
def conformance():
    from cli import business
    return CodeFactsReport(tuple(Fact("incremented", business(n) == n + 1, str(n)) for n in (0, 1)))
'''
    model.write_text(source)
    data = {"schema": "flowguard.map.v1", "components": [dict(
        id="commands", summary="Console command", responsibilities=["serve the console command"],
        files=["cli.py"], entrypoints=["cli.py:main"], tests=["tests/test_cli.py"],
        models=[".flowguard/models/business.py"], depends_on=[], status="draft")]}
    (tmp_path / ".flowguard/map.json").write_text(json.dumps(data))
    proof = map_cli(tmp_path, "models", "business", "--tests")
    assert proof.returncode == 0 and "PASS  business" in proof.stdout, proof.stdout + proof.stderr
    result = map_cli(tmp_path, "check")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "external promise cli.py:main (console_script) has no model anchor" in result.stdout
    assert "model it, or declare NOT_MODELED with a reason" in result.stdout
    reason = {"cli.py:main": "The pure console adapter is tested directly; the finite model covers business arithmetic."}
    model.write_text(source.replace("NOT_MODELED = {}", "NOT_MODELED = " + repr(reason)))
    result = map_cli(tmp_path, "check")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "entrypoint_unmodeled" not in result.stdout
    assert 'IMPLEMENTED_BY = {"Increment": "cli.py:business"}' in model.read_text()

    # A declared bare method is a valid anchor for a decorated class handler.
    command = tmp_path / "cli.py"
    command.write_text(command.read_text() + '\nclass Events:\n    def handler(self, fn):\n        return fn\nevents = Events()\nclass Controller:\n    @events.handler\n    def handle(self):\n        return "ready"\n')
    data["components"][0]["entrypoints"].append("cli.py:handle")
    (tmp_path / ".flowguard/map.json").write_text(json.dumps(data))
    result = map_cli(tmp_path, "check")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "external promise cli.py:handle (handler) has no model anchor" in result.stdout
    reason["cli.py:handle"] = "The registered pure class handler has no business state; its body returns readiness."
    model.write_text(source.replace("NOT_MODELED = {}", "NOT_MODELED = " + repr(reason)))
    result = map_cli(tmp_path, "check")
    assert result.returncode == 0 and "entrypoint_unmodeled" not in result.stdout, result.stdout + result.stderr

    # A real top-level function wins over a same-name decorated class method.
    command.write_text(command.read_text() + '\ndef handle():\n    return "plain"\n')
    del reason["cli.py:handle"]
    model.write_text(source.replace("NOT_MODELED = {}", "NOT_MODELED = " + repr(reason)))
    result = map_cli(tmp_path, "check")
    assert result.returncode == 0 and "entrypoint_unmodeled" not in result.stdout, result.stdout + result.stderr


def test_attribute_calls_resolve_to_the_assigned_class(tmp_path):
    marker = tmp_path / "fg232-user-code-imported.txt"
    sources = {
        "fg232_shelf/__init__.py": "",
        "fg232_shelf/members.py": (
            "class Members:\n"
            "    def may_borrow(self): return True\n"
            "    def shared(self): return True\n"),
        "fg232_shelf/catalog.py": (
            "class Catalog:\n"
            "    def take(self): return True\n"
            "    def flush(self): return True\n"
            "    def shared(self): return True\n"),
        "fg232_shelf/decoy.py": (
            "class Decoy:\n"
            "    def may_borrow(self): return False\n"
            "    def take(self): return False\n"
            "    def shared(self): return False\n"),
        "fg232_shelf/outside.py": "class Outside:\n    def flush(self): return False\n",
        "fg232_shelf/loans.py": (
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('imported')\n"
            "from fg232_shelf.members import Members\n"
            "import fg232_shelf.catalog as stock\n"
            "class LoanService:\n"
            "    def __init__(self, catalog=None, dependency=None):\n"
            "        self.members = Members()\n"
            "        self.catalog = catalog or stock.Catalog()\n"
            "        self.unknown = dependency\n"
            "    def borrow(self):\n"
            "        self.members.may_borrow()\n"
            "        return self.catalog.take()\n"
            "    def flush(self): return self.unknown.flush()\n"
            "    def ambiguous(self): return self.unknown.shared()\n"),
    }
    for relative, source in sources.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    data = {"schema": "flowguard.map.v1", "components": [
        dict(id=name, files=[f"fg232_shelf/{name}.py"], tests=[], models=[],
             summary=name, responsibilities=[name], status="draft",
             depends_on=["members", "catalog", "decoy"] if name == "loans" else [])
        for name in ("loans", "members", "catalog", "decoy", "outside")], "flows": [
            dict(id="borrow", steps=["loans:LoanService.borrow", "members:Members.may_borrow", "catalog:Catalog.take"]),
            dict(id="flush", steps=["loans:LoanService.flush", "catalog:Catalog.flush"])],
        "layers": [], "accepted_debts": []}
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    raw = discover_inventory(tmp_path, inv, data=data)
    assert set(raw["edges"]["fg232_shelf/loans.py#LoanService.borrow"]) == {
        "fg232_shelf/members.py#Members.may_borrow", "fg232_shelf/catalog.py#Catalog.take"}
    # Catalog has no __init__: the qualified constructor still identifies its class exactly.
    assert raw["edges"]["fg232_shelf/loans.py#LoanService.flush"] == ["fg232_shelf/catalog.py#Catalog.flush"]
    assert not raw["edges"].get("fg232_shelf/loans.py#LoanService.ambiguous")
    unscoped = discover_inventory(tmp_path, inv, data=None, write_cache=False)
    assert not unscoped["edges"].get("fg232_shelf/loans.py#LoanService.flush")
    assert not [finding for finding in run_lint(tmp_path, data, inv) if finding.code == "flow_step_unreached"]
    assert not marker.exists()
    assert not any(name == "fg232_shelf" or name.startswith("fg232_shelf.") for name in sys.modules)


_INJECTED_STORE = '''import json


class NoteStore:
    def __init__(self, path):
        self.path = path
        self.notes = {}

    def save(self, note_id, text):
        self.notes[note_id] = text
        with open(self.path, "w") as handle:
            json.dump(self.notes, handle)

    def delete(self, note_id):
        self.notes.pop(note_id, None)
        with open(self.path, "w") as handle:
            json.dump(self.notes, handle)
'''
_INJECTED_SERVICE = '''class NoteService:
    def __init__(self, store):
        self.store = store

    def add(self, note_id, text):
        self.store.save(note_id, text)

    def delete(self, note_id):
        self.store.delete(note_id)
'''
_INJECTED_CLI = '''from notes.service import NoteService
from notes.store import NoteStore


def main():
    service = NoteService(NoteStore("notes.json"))
    service.add("a", "first note")
'''


def _injected_project(root: Path, *, service: str = _INJECTED_SERVICE, cli: str | None = _INJECTED_CLI) -> dict:
    """The constructor-injection shape: cli builds NoteService(NoteStore(...)); service never imports store."""
    files = {"notes/__init__.py": "", "notes/store.py": _INJECTED_STORE, "notes/service.py": service}
    if cli is not None:
        files["notes/cli.py"] = cli
    for relative, source in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    def component(cid, path, layer, depends_on, entrypoints):
        return dict(id=cid, layer=layer, summary=f"{cid} notes", responsibilities=[f"{cid} notes"], files=[path],
                    entrypoints=entrypoints, state=[], side_effects=[], depends_on=depends_on, tests=[], models=[],
                    status="draft")
    components = [dict(component("store", "notes/store.py", "storage", [], []), files=["notes/store.py", "notes/__init__.py"]),
                  component("service", "notes/service.py", "domain", ["store"], ["notes/service.py:NoteService.add"])]
    if cli is not None:
        components.append(component("cli", "notes/cli.py", "interface", ["service", "store"], ["notes/cli.py:main"]))
    data = {"schema": "flowguard.map.v1", "project": "notes", "layers": ["interface", "domain", "storage"],
            "ignore": [], "components": components, "flows": [], "accepted_debts": []}
    (root / ".flowguard").mkdir(exist_ok=True)
    (root / ".flowguard/map.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def test_injected_collaborator_resolves_to_its_class(tmp_path):
    """An attribute assigned from a constructor parameter resolves through the class passed at every call site."""
    for variant, service, cli in (
            ("call-site", _INJECTED_SERVICE, _INJECTED_CLI),
            ("annotation", "from notes.store import NoteStore\n\n\n" + _INJECTED_SERVICE.replace(
                "def __init__(self, store):", "def __init__(self, store: NoteStore):"), None)):
        root = tmp_path / variant
        data = _injected_project(root, service=service, cli=cli)
        inv = build_inventory(root, DEFAULT_IGNORE)
        for scoped in (None, data):
            raw = discover_inventory(root, inv, data=scoped, write_cache=False)
            assert "notes/store.py#NoteStore.save" in raw["edges"].get("notes/service.py#NoteService.add", []), variant
            writes = raw["files"]["notes/service.py"]["functions"]["NoteService.delete"]["writes"]
            assert "NoteService.store" not in writes, (variant, writes)


def test_deps_write_keeps_an_injected_dependency(tmp_path):
    """dep_unused does not fire for an injected collaborator, deps --write keeps it, effect reach still sees it."""
    _injected_project(tmp_path)
    check = map_cli(tmp_path, "check")
    assert not [line for line in check.stdout.splitlines() if "dep_unused" in line and "service" in line], check.stdout
    written = map_cli(tmp_path, "deps", "--write")
    assert written.returncode == 0, written.stderr
    data = json.loads((tmp_path / ".flowguard/map.json").read_text(encoding="utf-8"))
    assert "store" in next(c for c in data["components"] if c["id"] == "service")["depends_on"], written.stdout
    after = map_cli(tmp_path, "check").stdout
    assert any("entrypoint_unmodeled" in line and ("notes/cli.py:main" in line or "NoteService.add" in line)
               for line in after.splitlines()), after


def test_write_into_an_injected_object_is_a_foreign_state_write(tmp_path):
    """Writing an attribute of another component's injected object is foreign_state_write."""
    service = _INJECTED_SERVICE + "\n    def clear(self):\n        self.store.notes = {}\n"
    data = _injected_project(tmp_path, service=service)
    inv = build_inventory(tmp_path, DEFAULT_IGNORE)
    found = [f for f in run_lint(tmp_path, data, inv) if f.code == "foreign_state_write"]
    assert any("NoteStore.notes" in f.message and f.component == "service" for f in found), found


def test_discovery_finds_each_entry_and_effect_shape(tmp_path):
    """Console scripts and main guards are entrypoints, writes belong to their writer, string words invent nothing."""
    from flowguard.map.discover import reachable_effects

    files = {
        "tool.py": "def run():\n    return 0\n",
        "pyproject.toml": "[project]\nname = 'probe'\n[project.scripts]\nprobe-tool = 'tool:run'\n",
        "save.py": "def save(text):\n    with open('out.txt', 'w') as handle:\n        handle.write(text)\n\n\n"
                   "if __name__ == '__main__':\n    save('x')\n",
        "counter.py": "class Counter:\n    def __init__(self):\n        self.count = 0\n\n    def bump(self):\n        self.count += 1\n",
        "words.py": "HELP = 'run subprocess or open a socket'\n\n\ndef describe():\n    return 'subprocess.run and requests.post'\n",
    }
    for relative, source in files.items():
        (tmp_path / relative).write_text(source, encoding="utf-8")
    raw = discover_inventory(tmp_path, build_inventory(tmp_path, [], write_cache=False), write_cache=False)
    entries = {(e["kind"], path, e["symbol"]) for path, facts in raw["files"].items() for e in facts["entrypoints"]}
    assert ("console_script", "tool.py", "run") in entries
    assert ("main_guard", "save.py", "<module>") in entries and ("main_call", "save.py", "save") in entries
    assert set(reachable_effects(raw, "save.py#save")) == {"fs_write"}
    assert raw["files"]["counter.py"]["state"]["Counter.count"] == ["Counter.__init__", "Counter.bump"]
    words = raw["files"]["words.py"]
    assert not words["entrypoints"] and not any(fn["effects"] for fn in words["functions"].values())
    assert not (tmp_path / ".flowguard").exists()


# FG-404: call graph edges and private-use diagnostics share a resolver.
def _resolution_case(tmp_path, files, caller, callee, *, import_roots=(), private=True):
    from flowguard.map.lint import private_use_findings
    for relative, source in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    source_path = caller.partition("#")[0]
    target_path = callee.partition("#")[0]
    groups = {"caller": [source_path]}
    others = sorted(set(files) - {source_path})
    if others:
        groups["helper"] = others
    data = {"schema": "flowguard.map.v1", "import_roots": list(import_roots), "components": [
        {"id": name, "summary": name, "responsibilities": ["execute the " + name], "files": paths,
         "tests": [], "models": [], "status": "draft"} for name, paths in groups.items()]}
    inv = build_inventory(tmp_path, [], write_cache=False, import_roots=import_roots)
    raw = discover_inventory(tmp_path, inv, write_cache=False, data=data)
    assert callee in raw["edges"].get(caller, []), raw["edges"]
    findings = private_use_findings(tmp_path, data, inv)
    assert bool(findings) == private, findings
    if private:
        assert any("_private" in f.message and f.component == "caller" for f in findings)
        assert target_path in inv.file_deps[source_path]
    return data, inv, raw


def test_nested_function_call_resolves(tmp_path):
    _resolution_case(tmp_path, {"runner.py": "def outer():\n    def _private(): return 1\n    def inner(): return _private()\n    return inner()\n"},
                     "runner.py#outer.inner", "runner.py#outer._private", private=False)


def test_import_local_to_enclosing_function_resolves(tmp_path):
    _resolution_case(tmp_path, {"pkg/__init__.py": "", "pkg/runner.py":
        "def outer():\n    from .helper import _private\n    def inner(): return _private()\n    return inner()\n",
        "pkg/helper.py": "def _private(): return 1\n"},
        "pkg/runner.py#outer.inner", "pkg/helper.py#_private")


def test_sibling_script_import_resolves(tmp_path):
    _resolution_case(tmp_path, {"scripts/runner.py": "from helper import _private\ndef run(): return _private()\n",
        "scripts/helper.py": "def _private(): return 1\n"},
        "scripts/runner.py#run", "scripts/helper.py#_private")


def test_import_root_import_resolves(tmp_path):
    data, inv, raw = _resolution_case(tmp_path, {
        "scripts/runner.py": "from helper import _private\ndef run(): return _private()\n",
        "library/helper.py": "def _private(): return 1\n"},
        "scripts/runner.py#run", "library/helper.py#_private", import_roots=("library",))
    without = build_inventory(tmp_path, [], write_cache=False)
    unresolved = discover_inventory(tmp_path, without, write_cache=False)
    assert "library/helper.py#_private" not in unresolved["edges"].get("scripts/runner.py#run", [])


def test_module_resolver_keeps_package_then_script_then_root_precedence():
    from flowguard.map.inventory import resolve_module, resolve_import
    files = {"scripts/runner.py", "scripts/helper.py", "library/helper.py", "other/helper.py", "library/pkg/__init__.py"}
    assert resolve_module("helper", "scripts/runner.py", {"helper": "package/helper.py"}, files, ("library",)) == "package/helper.py"
    assert resolve_module("helper", "scripts/runner.py", {}, files, ("library",)) == "scripts/helper.py"
    assert resolve_module("helper", "scripts/runner.py", {}, files | {"scripts/__init__.py"}, ("library", "other")) == "library/helper.py"
    assert resolve_module("pkg", "runner.py", {}, files, ("library",)) == "library/pkg/__init__.py"
    assert resolve_import("helper:_private", {}, importer="scripts/runner.py", py_paths=files) == "scripts/helper.py"

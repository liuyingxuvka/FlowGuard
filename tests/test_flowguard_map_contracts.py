"""Finite checks for declared model/code/test links and current map operation."""

import json
import subprocess
from pathlib import Path

from flowguard.__main__ import main
from flowguard.map.cli import _context
from flowguard.map.check import run_check
from flowguard.map.lint import run_lint


def write(root, relative, content):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def project(tmp_path):
    write(tmp_path, "app.py", "def run():\n    return True\n")
    write(tmp_path, "tests/test_app.py", "from app import run\n\ndef test_run():\n    assert run() is True\n")
    data = {"schema": "flowguard.map.v1", "components": [{
        "id": "app", "summary": "Runs the application", "responsibilities": ["run the app"],
        "files": ["app.py"], "entrypoints": ["app.py:run"], "tests": ["tests/test_app.py"],
        "models": [], "depends_on": [], "status": "draft",
    }]}
    save(tmp_path, data)
    return data


def save(root, data):
    write(root, ".flowguard/map.json", json.dumps(data))


def findings(root):
    data, inv = _context(root)
    return run_check(root, data, inv)


def test_unlisted_owner_runner_is_an_error_until_registered(tmp_path):
    data = project(tmp_path)
    runner = ".flowguard/verification/owners/app/run_checks.py"
    write(tmp_path, runner, "from flowguard.map.runner import run_owner\nraise SystemExit(run_owner(lambda: 0))\n")
    write(tmp_path, ".flowguard/models/owners/app/model.py", "VALUE = 1\n")
    assert "model_unbound" in {f.code for f in findings(tmp_path)}
    data["components"][0]["models"] = [runner]
    save(tmp_path, data)
    assert "model_unbound" not in {f.code for f in findings(tmp_path)}


CONTRACT = '''MODEL_ID = "one"
COMPONENTS = ["app"]
IMPLEMENTED_BY = {"Run": "app.py:run"}
def build_explorer():
    pass
'''


def test_model_binding_is_required_for_components_and_implementation_owners(tmp_path):
    data = project(tmp_path)
    path = ".flowguard/models/one.py"
    write(tmp_path, path, CONTRACT)
    assert "model_binding_missing" in {f.code for f in findings(tmp_path)}
    data["components"][0]["models"] = [path]
    save(tmp_path, data)
    assert "model_binding_missing" not in {f.code for f in findings(tmp_path)}


def test_deleted_or_renamed_test_breaks_declared_model_test_link(tmp_path):
    data = project(tmp_path)
    path = ".flowguard/models/one.py"
    write(tmp_path, path, CONTRACT + '\nTESTED_BY = {"returns_true": ["tests/test_app.py:test_run"]}\n')
    data["components"][0]["models"] = [path]
    save(tmp_path, data)
    assert "model_test_broken" not in {f.code for f in findings(tmp_path)}
    write(tmp_path, "tests/test_app.py", "def test_renamed():\n    assert True\n")
    assert "model_test_broken" in {f.code for f in findings(tmp_path)}


def test_dangerous_unmodeled_entry_and_invalid_negative_scope_are_visible(tmp_path):
    data = project(tmp_path)
    write(tmp_path, "app.py", "def run():\n    open('out.txt', 'w').write('x')\n    return True\n")
    assert "entrypoint_unmodeled" in {f.code for f in findings(tmp_path)}
    write(tmp_path, ".flowguard/models/one.py", CONTRACT + '\nNOT_MODELED = {"app.py:run": "Filesystem integration is tested directly, not a finite business proof."}\n')
    data["components"][0]["models"] = [".flowguard/models/one.py"]
    save(tmp_path, data)
    assert "entrypoint_unmodeled" not in {f.code for f in findings(tmp_path)}
    write(tmp_path, ".flowguard/models/one.py", CONTRACT + '\nNOT_MODELED = []\n')
    assert "model_contract" in {f.code for f in findings(tmp_path)}


def test_flow_relation_is_an_info_hint_for_unrelated_functions(tmp_path):
    data = project(tmp_path)
    write(tmp_path, "app.py", "def run():\n    return True\n\ndef finish():\n    return False\n")
    data["flows"] = [{"id": "journey", "steps": ["app:run", "app:finish"]}]
    save(tmp_path, data)
    d, inv = _context(tmp_path)
    assert any(f.code == "flow_step_unreached" and f.level == "info" for f in run_lint(tmp_path, d, inv))
    write(tmp_path, "app.py", "def run():\n    return finish()\n\ndef finish():\n    return False\n")
    d, inv = _context(tmp_path)
    assert not any(f.code == "flow_step_unreached" for f in run_lint(tmp_path, d, inv))


def test_new_uncommitted_map_does_not_block_first_change(tmp_path, capsys):
    write(tmp_path, "app.py", "def run():\n    return True\n")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "app.py"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "initial"], check=True)
    assert main(["map", "scan", "--root", str(tmp_path)]) == 0
    assert main(["change", "--root", str(tmp_path)]) == 0
    assert "BLOCKED" not in capsys.readouterr().out
    result = subprocess.check_output(["git", "-C", str(tmp_path), "status", "--porcelain", "--untracked-files=all"], text=True)
    assert ".flowguard/cache/" not in result


def test_legacy_project_read_points_to_upgrade_guide(tmp_path, capsys):
    write(tmp_path, ".flowguard/project.toml", 'version = "0.69.9"\n')
    assert main(["read", "--root", str(tmp_path)]) == 2
    assert "upgrade_from_0_69.md" in capsys.readouterr().err


def test_read_ignores_retired_words_in_agent_instructions(tmp_path, capsys):
    project(tmp_path)
    write(tmp_path, "AGENTS.md", "We retired `flowguard self-review` long ago.\n")
    write(tmp_path, ".flowguard/project.toml", 'version = "0.69.9"\n')
    assert main(["read", "--root", str(tmp_path)]) == 0
    assert "app" in capsys.readouterr().out


def test_capability_aliases_use_real_template_factories(tmp_path, capsys):
    for name in ("architecture-reduction", "behavior-commitment", "code-structure", "contract-exhaustion",
                 "field-lifecycle", "model-mesh", "model-test",
                 "topology-hazard", "ui-flow"):
        assert main(["template", name, "--write", str(tmp_path / name)]) == 0, name
        out = capsys.readouterr().out
        assert "then run: python -m flowguard map models " in out and "/docs/" not in out, name


def test_change_warns_when_another_owner_mutates_declared_state(tmp_path, capsys):
    write(tmp_path, 'owner.py', 'ORDERS = {}\n')
    write(tmp_path, 'client.py', 'from owner import ORDERS\n\ndef bill():\n    ORDERS[1] = "billed"\n')
    data = {'schema': 'flowguard.map.v1', 'components': [
        {'id': 'owner', 'summary': 'Owns order state', 'responsibilities': ['own orders'],
         'status': 'draft', 'files': ['owner.py'], 'state': ['ORDERS'], 'tests': [], 'models': [], 'depends_on': []},
        {'id': 'client', 'summary': 'Bills orders', 'responsibilities': ['bill orders'],
         'status': 'draft', 'files': ['client.py'], 'tests': [], 'models': [], 'depends_on': ['owner']},
    ]}
    save(tmp_path, data)
    main(['change', '--root', str(tmp_path), 'client.py'])
    assert 'ARCH WARN' in capsys.readouterr().out
    current, inv = _context(tmp_path)
    assert any(f.code == 'foreign_state_write' for f in run_lint(tmp_path, current, inv))
    write(tmp_path, 'client.py', 'from owner import ORDERS\n\ndef bill():\n    ORDERS = {}\n    ORDERS[1] = "local"\n')
    current, inv = _context(tmp_path)
    assert not any(f.code == 'foreign_state_write' for f in run_lint(tmp_path, current, inv))


def test_string_literals_are_dependency_evidence_only_for_exact_modules_or_symbols(tmp_path):
    from flowguard.map.mapfile import dependency_evidence
    write(tmp_path, "pkg/__init__.py", "")
    write(tmp_path, "pkg/b.py", "def func():\n    return 1\n")
    save(tmp_path, {"schema": "flowguard.map.v1", "components": [
        {"id": "a", "summary": "A", "responsibilities": ["a"], "files": ["pkg/a.py"], "entrypoints": [],
         "tests": [], "models": [], "depends_on": [], "status": "draft"},
        {"id": "b", "summary": "B", "responsibilities": ["b"], "files": ["pkg/__init__.py", "pkg/b.py"],
         "entrypoints": [], "tests": [], "models": [], "depends_on": [], "status": "draft"},
    ]})
    write(tmp_path, "pkg/a.py", 'import logging\nSCHEMA = "pkg.b.v1"\nLOG = logging.getLogger("pkg.b.events")\n')
    data, inv = _context(tmp_path)
    assert "b" not in dependency_evidence(data, inv)["a"]
    for condition in ('x != "pkg.b"', 'module != "pkg"'):
        write(tmp_path, "pkg/a.py", f"if {condition}:\n    pass\n")
        data, inv = _context(tmp_path)
        assert "b" not in dependency_evidence(data, inv)["a"], condition
    for literal in ('"pkg.b"', '"pkg.b:func"', '"pkg.b.func"'):
        write(tmp_path, "pkg/a.py", f"import importlib\nTARGET = importlib.import_module({literal})\n")
        data, inv = _context(tmp_path)
        assert "b" in dependency_evidence(data, inv)["a"], literal
    for text in ('_EXPORTS = {"pkg.b": ("func",)}\ndef __getattr__(name):\n    pass\n',
                 'TARGET = __import__("pkg")\n',
                 'TARGET = "pkg.b:func"\n',
                 'TARGET = "pkg.b.func"\n'):
        write(tmp_path, "pkg/a.py", text)
        data, inv = _context(tmp_path)
        assert "b" in dependency_evidence(data, inv)["a"], text


def test_import_literals_survive_inventory_cache(tmp_path):
    import os
    from flowguard.map.inventory import CACHE_SCHEMA, build_inventory
    from flowguard.map.common import DEFAULT_IGNORE
    write(tmp_path, "a.py", 'TARGET = __import__("pkg")\n')
    os.utime(tmp_path / "a.py", (1, 1))
    first = build_inventory(tmp_path, DEFAULT_IGNORE)
    cached = json.loads((tmp_path / ".flowguard/cache/inventory.json").read_text())
    assert cached["schema"] == CACHE_SCHEMA == "flowguard.map.inventory_cache.v5"
    assert cached["files"]["a.py"]["import_literals"] == ["pkg"]
    second = build_inventory(tmp_path, DEFAULT_IGNORE)
    assert first.py["a.py"].import_literals == second.py["a.py"].import_literals == {"pkg"}


def test_read_unknown_component_fails_and_names_the_read_command(tmp_path, capsys):
    project(tmp_path)
    assert main(["read", "--root", str(tmp_path), "--component", "nope"]) == 1
    assert "python -m flowguard read" in capsys.readouterr().out


def test_accepted_debts_mean_the_same_in_check_and_lint(tmp_path):
    data = project(tmp_path)
    write(tmp_path, "app.py", "def run():\n    open('out.txt', 'w').write('x')\n    return True\n")
    write(tmp_path, "lib.py", "VALUE = 1\n")
    data["components"].append({"id": "lib", "summary": "Lib", "responsibilities": ["hold a value"], "files": ["lib.py"],
                               "entrypoints": [], "tests": [], "models": [], "depends_on": [], "status": "draft"})
    data["components"][0]["depends_on"] = ["lib"]
    data["accepted_debts"] = [
        {"code": "dep_unused", "component": "app", "contains": "lib", "reason": "loaded by path at runtime"},
        {"code": "entrypoint_unmodeled", "component": "app", "reason": "file output is covered by an integration test"}]
    save(tmp_path, data)
    d, inv = _context(tmp_path)
    levels = {f.code: f.level for f in run_check(tmp_path, d, inv)}
    assert "dep_unused" not in levels and levels.get("entrypoint_unmodeled") == "info"
    assert "debt_stale" not in {f.code for f in run_lint(tmp_path, d, inv)}
    write(tmp_path, "app.py", "import lib\n\ndef run():\n    open('out.txt', 'w').write('x')\n    return lib.VALUE\n")
    d, inv = _context(tmp_path)
    assert any(f.code == "debt_stale" and "loaded by path" in f.message for f in run_lint(tmp_path, d, inv))


def test_change_prints_info_only_for_changed_owners(tmp_path, capsys):
    data = project(tmp_path)
    write(tmp_path, "lib.py", "def save():\n    open('out.txt', 'w').write('x')\n")
    data["components"].append({"id": "lib", "summary": "Lib", "responsibilities": ["save"], "files": ["lib.py"],
                               "entrypoints": ["lib.py:save"], "tests": [], "models": [], "depends_on": [], "status": "draft"})
    data["accepted_debts"] = [{"code": "entrypoint_unmodeled", "component": "lib", "reason": "covered by an integration test"}]
    save(tmp_path, data)
    main(["change", "--root", str(tmp_path), "app.py"])
    out = capsys.readouterr().out
    assert "INFO" not in out and "not repeated here" in out


def test_find_and_check_point_at_the_existing_owner(tmp_path, capsys):
    data = project(tmp_path)
    write(tmp_path, "shop/orders.py", "def place():\n    return 1\n")
    data["components"].append({"id": "orders", "summary": "Places orders", "responsibilities": ["place orders"],
                               "files": ["shop/orders.py"], "entrypoints": [], "tests": [], "models": [],
                               "depends_on": [], "state": ["order status"], "status": "draft"})
    save(tmp_path, data)
    assert main(["read", "--root", str(tmp_path), "--find", "order"]) == 0
    out = capsys.readouterr().out
    assert "state: order status" in out and "create a new component only when none does" in out
    write(tmp_path, "shop/refunds.py", "def refund():\n    return 1\n")
    assert [f.message for f in findings(tmp_path) if f.code == "file_unmapped"] == [
        "shop/refunds.py has no owning component; the files next to it belong to orders: "
        "add it there unless it is a new responsibility"]
    write(tmp_path, "shop/billing.py", "def bill():\n    return 1\n")
    data["components"].append({"id": "billing", "summary": "Bills orders", "responsibilities": ["bill orders"],
                               "files": ["shop/billing.py"], "entrypoints": [], "tests": [], "models": [],
                               "depends_on": [], "status": "draft"})
    save(tmp_path, data)
    assert [f.message for f in findings(tmp_path) if f.code == "file_unmapped"] == [
        "shop/refunds.py has no owning component; the files next to it belong to billing, orders: "
        "add it to the one that owns its responsibility"]


def test_cycle_debt_covers_only_its_members(tmp_path):
    from flowguard.map.common import Finding
    from flowguard.map.lint import apply_accepted_debts
    from flowguard.map.mapfile import validate_map

    data = project(tmp_path)
    data["components"] = [{"id": cid, "summary": cid, "responsibilities": [],
                           "files": [cid + ".py"], "tests": [], "depends_on": [], "models": [], "status": "draft"}
                          for cid in ("a", "b", "c")]
    write(tmp_path, "a.py", "import b\n")
    write(tmp_path, "b.py", "import a\n")
    write(tmp_path, "c.py", "VALUE = 1\n")
    data["accepted_debts"] = [{"code": "dependency_cycle", "members": ["a", "b"], "reason": "existing pair"}]

    def lint():
        save(tmp_path, data)
        current, inv = _context(tmp_path)
        return run_lint(tmp_path, current, inv)

    assert next(f for f in lint() if f.code == "dependency_cycle").level == "info"
    write(tmp_path, "b.py", "import a\nimport c\n")
    write(tmp_path, "c.py", "import a\n")
    grown = lint()
    cycle = next(f for f in grown if f.code == "dependency_cycle")
    assert cycle.level == "error" and "new members c" in cycle.message
    assert not any(f.code == "debt_stale" for f in grown)
    write(tmp_path, "b.py", "import a\n")
    write(tmp_path, "c.py", "VALUE = 1\n")
    for debt in ({"component": "a", "contains": "b"},
                 {"component": "a", "contains": "a <-> b; imports:"},
                 {"members": ["a", "b", "c"]}):
        data["accepted_debts"] = [{"code": "dependency_cycle", "reason": "compatible debt", **debt}]
        found = lint()
        cycle = next(f for f in found if f.code == "dependency_cycle")
        assert cycle.level == "info"
        assert not any(f.code == "debt_stale" for f in found)
        if "members" in debt:
            assert "cycle shrank" in cycle.message
    write(tmp_path, "b.py", "VALUE = 2\n")
    assert any(f.code == "debt_stale" for f in lint())
    merged, used = apply_accepted_debts(
        [Finding("error", "dependency_cycle", "a", "a <-> b <-> c <-> d")],
        [{"code": "dependency_cycle", "members": ["a", "b"], "reason": "left"},
         {"code": "dependency_cycle", "members": ["b", "c", "d"], "reason": "right"}])
    assert used == {0, 1}
    assert merged[0].level == "error" and "new members a" in merged[0].message
    data["accepted_debts"][0]["members"] = "a,b"
    assert any("members" in error for error in validate_map(data))


def test_model_tree_parent_defaults_and_nesting_warnings(tmp_path):
    from flowguard.map.mapfile import read_model_contract

    data = project(tmp_path)
    parent = CONTRACT.replace('"one"', '"parent"') + "\nimport child\nimport _shared\n"
    child = CONTRACT.replace('"one"', '"child"') + "\nfrom _shared import VALUE\n"
    write(tmp_path, ".flowguard/models/parent.py", parent)
    write(tmp_path, ".flowguard/models/child.py", child)
    write(tmp_path, ".flowguard/models/_shared.py", "PARENT = None\nimport _leaf\nVALUE = 1\n")
    write(tmp_path, ".flowguard/models/_leaf.py", "import _shared\n")
    contract = read_model_contract(tmp_path / ".flowguard/models/parent.py")
    assert contract.get("imports") == ["_shared", "child"]
    from flowguard.map.tree import build_tree

    def tree():
        current, inv = _context(tmp_path)
        return build_tree(tmp_path, current, inv)

    current = tree()
    assert (current.nodes["child"].parent, current.nodes["child"].source) == ("parent", "import")
    assert (current.nodes["parent"].parent, current.nodes["parent"].source) == ("app", "COMPONENTS")
    assert current.nodes["child"].home == "app"
    assert current.importers(".flowguard/models/_shared.py") == {"parent", "child"}
    assert current.importers(".flowguard/models/_leaf.py") == {"parent", "child"}
    assert current.ancestors("child") == ["parent"]
    assert [n.id for n in current.children("parent", "model")] == ["child"]
    assert not current.findings

    write(tmp_path, ".flowguard/models/child.py", child + '\nPARENT = "nope"\n')
    assert "parent_unknown" in {f.code for f in tree().findings}
    assert tree().nodes["child"].parent == "parent"
    write(tmp_path, ".flowguard/models/child.py", child + '\nPARENT = "app"\n')
    assert "parent_import_mismatch" in {f.code for f in tree().findings}
    write(tmp_path, ".flowguard/models/parent.py", parent + '\nPARENT = "child"\n')
    write(tmp_path, ".flowguard/models/child.py", child + '\nPARENT = "parent"\n')
    current = tree()
    assert "parent_cycle" in {f.code for f in current.findings}
    assert all(node.parent_kind != "model" for node in current.nodes.values())
    assert not current.ancestors("child")

    write(tmp_path, "other.py", "def run(): return False\n")
    data["components"].append({"id": "other", "files": ["other.py"], "status": "draft"})
    save(tmp_path, data)
    write(tmp_path, ".flowguard/models/parent.py", parent)
    write(tmp_path, ".flowguard/models/child.py", child.replace("app.py:run", "other.py:run"))
    current = tree()
    assert "child_outside_parent" in {f.code for f in current.findings}
    assert all(f.level == "warn" for f in current.findings)
    assert "child_outside_parent" in {f.code for f in findings(tmp_path)}
    write(tmp_path, ".flowguard/models/child.py", child)
    write(tmp_path, ".flowguard/models/second.py", child.replace('"child"', '"second"') + '\nPARENT = "parent"\n')
    assert "duplicate_child_owner" in {f.code for f in tree().findings}
    write(tmp_path, ".flowguard/models/second.py", child.replace('"child"', '"system"'))
    assert "model_contract" in {f.code for f in findings(tmp_path)}


def test_parent_literal_validation_and_sibling_loading(tmp_path):
    import sys
    import pytest
    from flowguard.map.mapfile import model_registry, read_model_contract
    from flowguard.map.proof import _load

    project(tmp_path)
    path = tmp_path / ".flowguard/models/one.py"
    for invalid in ('""', 'None', '[]', '42'):
        write(tmp_path, ".flowguard/models/one.py", CONTRACT + f"\nPARENT = {invalid}\n")
        with pytest.raises(ValueError, match="PARENT"):
            read_model_contract(path)
        assert any(i.code == "model_contract" for i in model_registry(tmp_path).issues)
    write(tmp_path, ".flowguard/models/one.py", CONTRACT + '\nPARENT = "system"\n')
    assert read_model_contract(path)["PARENT"] == "system"
    write(tmp_path, ".flowguard/models/sibling_for_load_probe.py", "VALUE = 73\n")
    write(tmp_path, ".flowguard/models/load_probe.py", "import sibling_for_load_probe\nVALUE = sibling_for_load_probe.VALUE\n")
    original = list(sys.path)
    try:
        assert _load(tmp_path, tmp_path / ".flowguard/models/load_probe.py").VALUE == 73
        assert str(tmp_path / ".flowguard/models") in sys.path
    finally:
        sys.path[:] = original
        sys.modules.pop("sibling_for_load_probe", None)
        sys.modules.pop("_flowguard_model_load_probe", None)


def test_model_tree_legacy_anchor_runner_and_root_defaults(tmp_path):
    from flowguard.map.tree import build_tree

    data = project(tmp_path)
    write(tmp_path, ".flowguard/models/anchored.py", CONTRACT.replace('"one"', '"anchored"').replace('COMPONENTS = ["app"]', 'COMPONENTS = []'))
    write(tmp_path, ".flowguard/models/rooted.py", 'MODEL_ID = "rooted"\nDESIGN_ONLY = "Abstract probe"\ndef build_explorer(): pass\n')
    runner = ".flowguard/verification/owners/native/run_checks.py"
    write(tmp_path, runner, "VALUE = 1\n")
    data["components"][0]["models"] = [runner]
    save(tmp_path, data)
    current, inv = _context(tmp_path)
    tree = build_tree(tmp_path, current, inv)
    assert (tree.nodes["anchored"].parent, tree.nodes["anchored"].source) == ("app", "anchor")
    assert (tree.nodes["native"].parent, tree.nodes["native"].source) == ("app", "listed")
    assert (tree.nodes["rooted"].parent, tree.nodes["rooted"].source) == ("system", "default")
    assert not tree.findings

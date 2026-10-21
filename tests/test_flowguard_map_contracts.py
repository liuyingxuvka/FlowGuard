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
    for name in ("existing-model", "behavior-commitment", "code-structure", "contract-exhaustion",
                 "field-lifecycle", "model-mesh", "model-miss", "model-test",
                 "topology-hazard", "structure-mesh", "test-mesh", "ui-flow"):
        assert main(["template", name, "--write", str(tmp_path / name)]) == 0, name
        out = capsys.readouterr().out
        assert "then run: python -m flowguard map models " in out and "/docs/" not in out, name
    assert main(["template", "architecture-reduction"]) == 2
    assert "protocol.md" in capsys.readouterr().out


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
    for literal in ('"pkg.b"', '"pkg.b:func"', '"pkg.b.func"'):
        write(tmp_path, "pkg/a.py", f"import importlib\nTARGET = importlib.import_module({literal})\n")
        data, inv = _context(tmp_path)
        assert "b" in dependency_evidence(data, inv)["a"], literal


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

"""Tests grouped by their model or native component."""
from __future__ import annotations

import json
import shutil
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
from _fg_helpers import flowguard_map_discover421_ROOT as ROOT, flowguard_map_discover421_APP as APP, flowguard_map_discover421_STORE as STORE, flowguard_map_discover421_CLI as CLI, flowguard_map_discover421_write_project as write_project, flowguard_map_discover421_map_cli as map_cli, flowguard_map_discover421__INJECTED_STORE as _INJECTED_STORE, flowguard_map_discover421__INJECTED_SERVICE as _INJECTED_SERVICE, flowguard_map_discover421__INJECTED_CLI as _INJECTED_CLI, flowguard_map_discover421__injected_project as _injected_project, flowguard_map_discover421__resolution_case as _resolution_case, flowguard_map_discover421_literal_fixture as literal_fixture, flowguard_map_discover421_json as json, flowguard_map_discover421_shutil as shutil, flowguard_map_discover421_subprocess as subprocess, flowguard_map_discover421_sys as sys, flowguard_map_discover421_tempfile as tempfile, flowguard_map_discover421_unittest as unittest, flowguard_map_discover421_Path as Path, flowguard_map_discover421_pytest as pytest, flowguard_map_discover421_component_summary as component_summary, flowguard_map_discover421_console_scripts as console_scripts, flowguard_map_discover421_discover as discover, flowguard_map_discover421_discover_inventory as discover_inventory, flowguard_map_discover421_file_facts as file_facts, flowguard_map_discover421_DEFAULT_IGNORE as DEFAULT_IGNORE, flowguard_map_discover421_build_inventory as build_inventory, flowguard_map_discover421_entrypoint_coverage_findings as entrypoint_coverage_findings, flowguard_map_discover421_run_lint as run_lint, flowguard_map_discover421_scoped_architecture_findings as scoped_architecture_findings, flowguard_map_discover421_guess_tests as guess_tests, flowguard_map_discover421_new_map as new_map, flowguard_map_discover421_propose_components as propose_components

def test_external_promise_needs_a_model_or_a_reason(tmp_path):
    import json
    import shutil
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
    from _fg_helpers import flowguard_map_discover421_ROOT as ROOT, flowguard_map_discover421_APP as APP, flowguard_map_discover421_STORE as STORE, flowguard_map_discover421_CLI as CLI, flowguard_map_discover421_write_project as write_project, flowguard_map_discover421_map_cli as map_cli, flowguard_map_discover421__INJECTED_STORE as _INJECTED_STORE, flowguard_map_discover421__INJECTED_SERVICE as _INJECTED_SERVICE, flowguard_map_discover421__INJECTED_CLI as _INJECTED_CLI, flowguard_map_discover421__injected_project as _injected_project, flowguard_map_discover421__resolution_case as _resolution_case, flowguard_map_discover421_literal_fixture as literal_fixture, flowguard_map_discover421_json as json, flowguard_map_discover421_shutil as shutil, flowguard_map_discover421_subprocess as subprocess, flowguard_map_discover421_sys as sys, flowguard_map_discover421_tempfile as tempfile, flowguard_map_discover421_unittest as unittest, flowguard_map_discover421_Path as Path, flowguard_map_discover421_pytest as pytest, flowguard_map_discover421_component_summary as component_summary, flowguard_map_discover421_console_scripts as console_scripts, flowguard_map_discover421_discover as discover, flowguard_map_discover421_discover_inventory as discover_inventory, flowguard_map_discover421_file_facts as file_facts, flowguard_map_discover421_DEFAULT_IGNORE as DEFAULT_IGNORE, flowguard_map_discover421_build_inventory as build_inventory, flowguard_map_discover421_entrypoint_coverage_findings as entrypoint_coverage_findings, flowguard_map_discover421_run_lint as run_lint, flowguard_map_discover421_scoped_architecture_findings as scoped_architecture_findings, flowguard_map_discover421_guess_tests as guess_tests, flowguard_map_discover421_new_map as new_map, flowguard_map_discover421_propose_components as propose_components
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


def test_deps_write_keeps_an_injected_dependency(tmp_path):
    """dep_unused does not fire for an injected collaborator, deps --write keeps it, effect reach still sees it."""
    import json
    import shutil
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
    from _fg_helpers import flowguard_map_discover421_ROOT as ROOT, flowguard_map_discover421_APP as APP, flowguard_map_discover421_STORE as STORE, flowguard_map_discover421_CLI as CLI, flowguard_map_discover421_write_project as write_project, flowguard_map_discover421_map_cli as map_cli, flowguard_map_discover421__INJECTED_STORE as _INJECTED_STORE, flowguard_map_discover421__INJECTED_SERVICE as _INJECTED_SERVICE, flowguard_map_discover421__INJECTED_CLI as _INJECTED_CLI, flowguard_map_discover421__injected_project as _injected_project, flowguard_map_discover421__resolution_case as _resolution_case, flowguard_map_discover421_literal_fixture as literal_fixture, flowguard_map_discover421_json as json, flowguard_map_discover421_shutil as shutil, flowguard_map_discover421_subprocess as subprocess, flowguard_map_discover421_sys as sys, flowguard_map_discover421_tempfile as tempfile, flowguard_map_discover421_unittest as unittest, flowguard_map_discover421_Path as Path, flowguard_map_discover421_pytest as pytest, flowguard_map_discover421_component_summary as component_summary, flowguard_map_discover421_console_scripts as console_scripts, flowguard_map_discover421_discover as discover, flowguard_map_discover421_discover_inventory as discover_inventory, flowguard_map_discover421_file_facts as file_facts, flowguard_map_discover421_DEFAULT_IGNORE as DEFAULT_IGNORE, flowguard_map_discover421_build_inventory as build_inventory, flowguard_map_discover421_entrypoint_coverage_findings as entrypoint_coverage_findings, flowguard_map_discover421_run_lint as run_lint, flowguard_map_discover421_scoped_architecture_findings as scoped_architecture_findings, flowguard_map_discover421_guess_tests as guess_tests, flowguard_map_discover421_new_map as new_map, flowguard_map_discover421_propose_components as propose_components
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


class DiscoverTests(unittest.TestCase):
    def test_scan_hints_and_lint_findings_come_from_discovery(self) -> None:
        import json
        import shutil
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
        from _fg_helpers import flowguard_map_discover421_ROOT as ROOT, flowguard_map_discover421_APP as APP, flowguard_map_discover421_STORE as STORE, flowguard_map_discover421_CLI as CLI, flowguard_map_discover421_write_project as write_project, flowguard_map_discover421_map_cli as map_cli, flowguard_map_discover421__INJECTED_STORE as _INJECTED_STORE, flowguard_map_discover421__INJECTED_SERVICE as _INJECTED_SERVICE, flowguard_map_discover421__INJECTED_CLI as _INJECTED_CLI, flowguard_map_discover421__injected_project as _injected_project, flowguard_map_discover421__resolution_case as _resolution_case, flowguard_map_discover421_literal_fixture as literal_fixture, flowguard_map_discover421_json as json, flowguard_map_discover421_shutil as shutil, flowguard_map_discover421_subprocess as subprocess, flowguard_map_discover421_sys as sys, flowguard_map_discover421_tempfile as tempfile, flowguard_map_discover421_unittest as unittest, flowguard_map_discover421_Path as Path, flowguard_map_discover421_pytest as pytest, flowguard_map_discover421_component_summary as component_summary, flowguard_map_discover421_console_scripts as console_scripts, flowguard_map_discover421_discover as discover, flowguard_map_discover421_discover_inventory as discover_inventory, flowguard_map_discover421_file_facts as file_facts, flowguard_map_discover421_DEFAULT_IGNORE as DEFAULT_IGNORE, flowguard_map_discover421_build_inventory as build_inventory, flowguard_map_discover421_entrypoint_coverage_findings as entrypoint_coverage_findings, flowguard_map_discover421_run_lint as run_lint, flowguard_map_discover421_scoped_architecture_findings as scoped_architecture_findings, flowguard_map_discover421_guess_tests as guess_tests, flowguard_map_discover421_new_map as new_map, flowguard_map_discover421_propose_components as propose_components
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
        import json
        import shutil
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
        from _fg_helpers import flowguard_map_discover421_ROOT as ROOT, flowguard_map_discover421_APP as APP, flowguard_map_discover421_STORE as STORE, flowguard_map_discover421_CLI as CLI, flowguard_map_discover421_write_project as write_project, flowguard_map_discover421_map_cli as map_cli, flowguard_map_discover421__INJECTED_STORE as _INJECTED_STORE, flowguard_map_discover421__INJECTED_SERVICE as _INJECTED_SERVICE, flowguard_map_discover421__INJECTED_CLI as _INJECTED_CLI, flowguard_map_discover421__injected_project as _injected_project, flowguard_map_discover421__resolution_case as _resolution_case, flowguard_map_discover421_literal_fixture as literal_fixture, flowguard_map_discover421_json as json, flowguard_map_discover421_shutil as shutil, flowguard_map_discover421_subprocess as subprocess, flowguard_map_discover421_sys as sys, flowguard_map_discover421_tempfile as tempfile, flowguard_map_discover421_unittest as unittest, flowguard_map_discover421_Path as Path, flowguard_map_discover421_pytest as pytest, flowguard_map_discover421_component_summary as component_summary, flowguard_map_discover421_console_scripts as console_scripts, flowguard_map_discover421_discover as discover, flowguard_map_discover421_discover_inventory as discover_inventory, flowguard_map_discover421_file_facts as file_facts, flowguard_map_discover421_DEFAULT_IGNORE as DEFAULT_IGNORE, flowguard_map_discover421_build_inventory as build_inventory, flowguard_map_discover421_entrypoint_coverage_findings as entrypoint_coverage_findings, flowguard_map_discover421_run_lint as run_lint, flowguard_map_discover421_scoped_architecture_findings as scoped_architecture_findings, flowguard_map_discover421_guess_tests as guess_tests, flowguard_map_discover421_new_map as new_map, flowguard_map_discover421_propose_components as propose_components
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_project(root)
            map_cli(root, "scan")
            out = map_cli(root, "discover").stdout
        self.assertIn("reach   http_route POST /notes -> db, network", out)

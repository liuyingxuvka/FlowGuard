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

def test_unlisted_entrypoints_group_by_component_and_strength(tmp_path):
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


def test_attribute_calls_resolve_to_the_assigned_class(tmp_path):
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


class DiscoveryBoundaryTests(unittest.TestCase):
    def test_reverse_entry_coverage_warns_even_without_any_model_and_respects_explicit_reason(self) -> None:
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

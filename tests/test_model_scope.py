"""Tests grouped by their model or native component."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
import pytest
from flowguard.__main__ import main
from flowguard.map.cli import _context
from flowguard.map.check import run_check
from flowguard.map.lint import run_lint
from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint

def test_anchor_scope_same_with_or_without_parent(tmp_path):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
    helper = _scope_helpers()["scope_fixture"]
    reports = [helper(tmp_path / case, case)[2] for case in ("explicit", "implicit")]
    assert all([f.code for f in report.findings] == ["anchor_outside_home"] for report in reports)
    assert all(report.findings[0].component == "app" and report.findings[0].level == "error" for report in reports)


def test_anchor_outside_home_names_common_ancestor(tmp_path):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
    from flowguard.map.tree import common_ancestor
    data, _, tree = _scope_helpers()["scope_fixture"](tmp_path, "explicit")
    assert common_ancestor(data, ["app", "lib"]) == "base"
    assert common_ancestor(data, ["app", "system"]) == "system"
    assert tree.findings[0].message == (
        ".flowguard/models/m.py: IMPLEMENTED_BY 'Own' -> 'lib.py:value' is in component lib, outside this model's scope "
        '(app + COMPONENTS app); set PARENT = "base" (the common ancestor of app and lib), '
        "bind it read-only with USES, or, if this model really owns that code, add lib to COMPONENTS")


def test_model_ancestor_components_are_in_scope(tmp_path):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
    _, _, tree = _scope_helpers()["scope_fixture"](tmp_path, "ancestor")
    assert not tree.findings
    assert tree.nodes["m"].home == "app" and tree.ancestors("m") == ["p"]


def test_unused_uses_fails_and_is_not_coverage(tmp_path):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
    from flowguard.map.discover import discover_inventory
    from flowguard.map.lint import coverage_facts
    from flowguard.map.proof import run_model
    data, inv, tree = _scope_helpers()["scope_fixture"](tmp_path, "uses")
    assert not tree.findings and tree.models_for_component("lib") == []
    raw = discover_inventory(tmp_path, inv, data=data, write_cache=False)
    coverage = coverage_facts(tmp_path, data, inv, tree, raw)
    assert coverage["lib"]["entry_sources"][0] == 0
    assert "lib.py:value" in coverage["lib"]["unexplained_entries"]
    path = tmp_path / ".flowguard/models/m.py"
    result = run_model(tmp_path, path)
    assert result.status == "fail" and not result.code_gaps
    assert "USES anchor lib.py:value never ran during conformance(); call it there or remove it" in result.problems
    source = path.read_text()
    prefix = '    value = load_anchor(IMPLEMENTED_BY["Own"],root=Path.cwd())()'
    path.write_text(source.replace(prefix, '    (Path.cwd() / "lib.py").read_text()\n' + prefix))
    assert run_model(tmp_path, path).status == "fail"  # reading the file cannot claim that USES ran
    path.write_text(source.replace(prefix, '    load_anchor(USES["Read"],root=Path.cwd())()\n' + prefix))
    result = run_model(tmp_path, path)
    assert result.status == "pass", result.problems

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

def test_capability_aliases_use_real_template_factories(tmp_path, capsys):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
    for name in ("contract-exhaustion",
                 "ui-flow"):
        assert main(["template", name, "--write", str(tmp_path / name)]) == 0, name
        out = capsys.readouterr().out
        assert "next: python -m flowguard map models " in out and "/docs/" not in out, name
    assert main(["template", "architecture-reduction", "--write", str(tmp_path / "architecture-reduction")]) == 2
    assert main(["template", "code-structure", "--write", str(tmp_path / "code-structure")]) == 2
    assert main(["template", "field-lifecycle", "--write", str(tmp_path / "field-lifecycle")]) == 2
    assert main(["template", "behavior-commitment", "--write", str(tmp_path / "behavior-commitment")]) == 2
    assert main(["template", "model-mesh", "--write", str(tmp_path / "model-mesh")]) == 2
    assert main(["template", "model-test", "--write", str(tmp_path / "model-test")]) == 2
    assert main(["template", "topology-hazard", "--write", str(tmp_path / "topology-hazard")]) == 2

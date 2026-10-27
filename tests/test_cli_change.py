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

def test_change_warns_when_another_owner_mutates_declared_state(tmp_path, capsys):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
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


def test_change_prints_info_only_for_changed_owners(tmp_path, capsys):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
    data = project(tmp_path)
    write(tmp_path, "lib.py", "def save():\n    open('out.txt', 'w').write('x')\n")
    data["components"].append({"id": "lib", "summary": "Lib", "responsibilities": ["save"], "files": ["lib.py"],
                               "entrypoints": ["lib.py:save"], "tests": [], "models": [], "depends_on": [], "status": "draft"})
    data["accepted_debts"] = [{"code": "entrypoint_unmodeled", "component": "lib", "reason": "covered by an integration test"}]
    save(tmp_path, data)
    main(["change", "--root", str(tmp_path), "app.py"])
    out = capsys.readouterr().out
    assert "INFO" not in out and "not repeated here" in out

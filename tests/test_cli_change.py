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

from _fg_helpers import (
    flowguard_map_contracts421_project as project,
    flowguard_map_contracts421_save as save,
    flowguard_map_contracts421_write as write,
)

def test_change_warns_when_another_owner_mutates_declared_state(tmp_path, capsys):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint

    write(tmp_path, "owner.py", "ORDERS = {}\n")
    write(
        tmp_path, "client.py", 'from owner import ORDERS\n\ndef bill():\n    ORDERS[1] = "billed"\n'
    )
    data = {
        "schema": "flowguard.map.v1",
        "components": [
            {
                "id": "owner",
                "summary": "Owns order state",
                "responsibilities": ["own orders"],
                "status": "draft",
                "files": ["owner.py"],
                "state": ["ORDERS"],
                "tests": [],
                "models": [],
                "depends_on": [],
            },
            {
                "id": "client",
                "summary": "Bills orders",
                "responsibilities": ["bill orders"],
                "status": "draft",
                "files": ["client.py"],
                "tests": [],
                "models": [],
                "depends_on": ["owner"],
            },
        ],
    }
    save(tmp_path, data)
    main(["change", "--root", str(tmp_path), "client.py"])
    assert "ARCH WARN" in capsys.readouterr().out
    current, inv = _context(tmp_path)
    assert any(f.code == "foreign_state_write" for f in run_lint(tmp_path, current, inv))
    write(
        tmp_path,
        "client.py",
        'from owner import ORDERS\n\ndef bill():\n    ORDERS = {}\n    ORDERS[1] = "local"\n',
    )
    current, inv = _context(tmp_path)
    assert not any(f.code == "foreign_state_write" for f in run_lint(tmp_path, current, inv))


def test_change_prints_info_only_for_changed_owners(tmp_path, capsys):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint

    data = project(tmp_path)
    write(tmp_path, "lib.py", "def save():\n    open('out.txt', 'w').write('x')\n")
    data["components"].append(
        {
            "id": "lib",
            "summary": "Lib",
            "responsibilities": ["save"],
            "files": ["lib.py"],
            "entrypoints": ["lib.py:save"],
            "tests": [],
            "models": [],
            "depends_on": [],
            "status": "draft",
        }
    )
    data["accepted_debts"] = [
        {
            "code": "entrypoint_unmodeled",
            "component": "lib",
            "reason": "covered by an integration test",
        }
    ]
    save(tmp_path, data)
    main(["change", "--root", str(tmp_path), "app.py"])
    out = capsys.readouterr().out
    assert "INFO" not in out and "not repeated here" in out


def test_run_line_counts_files_and_verbose_lists_nodes(tmp_path):
    from test_packaged_cli_surface import _change_run_project, _flowguard

    root = _change_run_project(tmp_path)
    (root / "app.py").write_text("def run():\n    return 1 == 1\n")
    plain = _flowguard(root, "change")
    verbose = _flowguard(root, "change", "--verbose")
    assert plain.returncode == verbose.returncode == 0
    lines = [
        line
        for line in plain.stdout.splitlines()
        if line.startswith("run: python -m flowguard change --run (pytest: ")
    ]
    assert len(lines) == 1 and "tests/test_app.py" in lines[0]
    assert "run: python -m pytest" not in plain.stdout
    assert "run: python -m pytest -q" in verbose.stdout and "tests/test_app.py" in verbose.stdout
    from dataclasses import fields
    from flowguard.map.cli import _context
    from flowguard.map.impact import compute_impact

    data, inv = _context(root)
    impact = compute_impact(root, data, inv, ["app.py"], base="HEAD")
    assert set(impact.to_dict()) == {field.name for field in fields(impact)}

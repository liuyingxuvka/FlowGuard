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

def test_two_components_cannot_own_one_state(tmp_path, capsys):
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
    write(tmp_path, "app.py", "COPIES = {}\n\ndef run():\n    print('prints the result')\n    return True\n")
    write(tmp_path, "loans.py", "LOANS = []\n\ndef record():\n    print('free copies per book')\n")
    owner = data["components"][0]
    owner["state"] = ["free copies per book"]
    empty = ["", "none", "nothing", "none nothing"]
    owner["side_effects"] = list(empty)
    borrower = {"id": "loans", "summary": "Records current loans", "responsibilities": ["record a loan"],
                "files": ["loans.py"], "entrypoints": ["loans.py:record"], "state": ["free copies per book"],
                "side_effects": list(empty), "tests": [], "models": [], "depends_on": [], "status": "draft"}
    data["components"].append(borrower)

    def observe(expected_failure):
        save(tmp_path, data)
        capsys.readouterr()
        assert main(["map", "lint", "--root", str(tmp_path)]) == int(expected_failure)
        lint_output = capsys.readouterr().out
        assert main(["map", "models", "system", "--root", str(tmp_path)]) == int(expected_failure)
        model_output = capsys.readouterr().out
        status = "FAIL" if expected_failure else "PASS"
        assert any(line.split()[:2] == [status, "system"] for line in model_output.splitlines()), model_output
        if not expected_failure:
            assert "duplicate_owner" not in lint_output, lint_output
        return lint_output, model_output

    phrase = "state 'free copies per book' is claimed by ['app', 'loans']"
    lint_output, model_output = observe(True)
    assert phrase in lint_output and phrase in model_output, (lint_output, model_output)
    # Matching uses token identity, while diagnostics retain the declared phrase.
    borrower["state"] = ["book per copies free"]
    lint_output, model_output = observe(True)
    phrase = "state 'book per copies free' is claimed by ['app', 'loans']"
    assert phrase in lint_output and phrase in model_output, (lint_output, model_output)
    owner["state"] += empty
    borrower["state"] = ["current loans", *empty]
    observe(False)
    owner["side_effects"] = ["prints the result", *empty]
    borrower["side_effects"] = ["the result prints", *empty]
    lint_output, model_output = observe(True)
    phrase = "side effect 'prints the result' is claimed by ['app', 'loans']"
    assert phrase in lint_output and phrase in model_output, (lint_output, model_output)
    # The same words in state and side-effect facets do not name the same promise.
    borrower["side_effects"] = ["free copies per book", *empty]
    observe(False)

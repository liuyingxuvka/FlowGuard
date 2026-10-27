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

def test_tested_by_outside_the_component_tests_is_not_nested(tmp_path, capsys):
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
    write(tmp_path, "lib.py", "def helper(): return True\n")
    write(tmp_path, "tests/test_lib.py", "def test_x():\n    assert True\n")
    data["components"].append(dict(id="lib", files=["lib.py"], tests=["tests/test_lib.py"],
                                   status="draft", summary="Library", responsibilities=["help"], depends_on=[]))
    save(tmp_path, data)
    path = ".flowguard/models/one.py"
    contract = CONTRACT + "\ndef conformance():\n    from app import run\n    return run()\n"
    foreign = '\nTESTED_BY = {"returns_true": ["tests/test_lib.py:test_x"]}\n'
    write(tmp_path, path, contract + foreign)
    warnings = [f for f in findings(tmp_path) if f.code == "test_not_nested"]
    assert len(warnings) == 1 and warnings[0].level == "warn" and warnings[0].component == "app"
    assert "one binds tests/test_lib.py" in warnings[0].message
    assert main(["map", "check", "--root", str(tmp_path)]) == 0
    capsys.readouterr()
    assert main(["read", "--root", str(tmp_path), "--component", "app"]) == 0
    assert "returns_true -> tests/test_lib.py:test_x (not nested)" in capsys.readouterr().out

    write(tmp_path, path, contract + '\nTESTED_BY = {"returns_true": ["tests/test_app.py:test_run"]}\n')
    assert not any(f.code == "test_not_nested" for f in findings(tmp_path))
    assert main(["read", "--root", str(tmp_path), "--component", "app"]) == 0
    assert "(not nested)" not in capsys.readouterr().out

    # Any real component in the model's component set can own the binding.
    write(tmp_path, path, contract.replace('["app"]', '["app", "lib"]') + foreign)
    assert not any(f.code == "test_not_nested" for f in findings(tmp_path))
    write(tmp_path, path, contract + foreign)
    data["components"][0]["tests"] = ["tests/test_*.py"]
    save(tmp_path, data)
    assert not any(f.code == "test_not_nested" for f in findings(tmp_path))


def test_one_promise_has_one_owner(tmp_path, capsys):
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
    write(tmp_path, "lib.py", "def helper():\n    return 1\n")
    library = dict(id="lib", summary="Library helper", responsibilities=["provide library help"],
                   files=["lib.py"], entrypoints=["lib.py:helper"], tests=[], models=[],
                   depends_on=[], status="draft")
    data["components"].append(library)
    app = data["components"][0]
    for duplicate in (False, True):
        app["entrypoints"] = ["app.py:run", "lib.py:helper"]
        library["entrypoints"] = ["lib.py:helper"] if duplicate else []
        save(tmp_path, data)
        errors = [f for f in findings(tmp_path) if f.code == "entrypoint_owner"]
        assert errors and all(f.level == "error" for f in errors)
        assert any("lib.py:helper is listed by app but lib.py belongs to lib" in f.message for f in errors)
        if duplicate:
            assert any("lib.py:helper is listed by app and lib; one promise has one owner" in f.message
                       for f in errors)
        assert main(["map", "check", "--root", str(tmp_path)]) == 1
        capsys.readouterr()
        app["entrypoints"] = ["app.py:run"]
        library["entrypoints"] = ["lib.py:helper"]
        save(tmp_path, data)
        assert not any(f.code == "entrypoint_owner" for f in findings(tmp_path))
        assert main(["map", "check", "--root", str(tmp_path)]) == 0
        capsys.readouterr()

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
    flowguard_map_contracts421_write as write,
    flowguard_map_contracts421_project as project,
    flowguard_map_contracts421_save as save,
    flowguard_map_contracts421_findings as findings,
    flowguard_map_contracts421_CONTRACT as CONTRACT,
    flowguard_map_contracts421__placement_port_source as _placement_port_source,
    flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project,
    flowguard_map_contracts421__scope_helpers as _scope_helpers,
    flowguard_map_contracts421_json as json,
    flowguard_map_contracts421_subprocess as subprocess,
    flowguard_map_contracts421_Path as Path,
    flowguard_map_contracts421_pytest as pytest,
    flowguard_map_contracts421_main as main,
    flowguard_map_contracts421__context as _context,
    flowguard_map_contracts421_run_check as run_check,
    flowguard_map_contracts421_run_lint as run_lint,
    map_inventory421_os as os,
)
import pytest, os, json

def test_cycle_debt_covers_only_its_members(tmp_path):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
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
    data["accepted_debts"] = [{"expires": "9999-12-31", "code": "dependency_cycle", "members": ["a", "b"], "reason": "existing pair"}]

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
        data["accepted_debts"] = [{"expires": "9999-12-31", "code": "dependency_cycle", "reason": "compatible debt", **debt}]
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
        [{"expires": "9999-12-31", "code": "dependency_cycle", "members": ["a", "b"], "reason": "left"},
         {"expires": "9999-12-31", "code": "dependency_cycle", "members": ["b", "c", "d"], "reason": "right"}])
    assert used == {0, 1}
    assert merged[0].level == "error" and "new members a" in merged[0].message
    data["accepted_debts"][0]["members"] = "a,b"
    assert any("members" in error for error in validate_map(data))


def test_normalize_newlines_handles_crlf_and_lone_cr(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from flowguard.map.common import content_digest
    mixed = tmp_path / "mixed.py"
    lf = tmp_path / "lf.py"
    mixed.write_bytes(b"a\r\nb\rc\n")
    lf.write_bytes(b"a\nb\nc\n")
    assert content_digest(mixed) == content_digest(lf)
    from flowguard.map.common import normalize_newlines
    assert normalize_newlines(mixed.read_bytes()) == lf.read_bytes()
    assert normalize_newlines(lf.read_bytes()) == lf.read_bytes()
    lf.write_bytes(b"a\nb\nchanged\n")
    assert content_digest(mixed) != content_digest(lf)

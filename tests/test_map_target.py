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
from dataclasses import fields, is_dataclass, replace
import runpy
from flowguard.map.mapfile import load_map
from flowguard.map.port import model_port, port_findings, upward
from flowguard.map.tree import build_tree

from _fg_helpers import (
    flowguard_port421_dispatch_project as dispatch_project,
    flowguard_port421_helpers as helpers,
    flowguard_map_discover421_literal_fixture as literal_fixture,
    flowguard_port421_project as project,
)

def test_target_check_compares_promises_without_git(tmp_path, monkeypatch):
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
    from flowguard.map.target import start_target,add_to_target,check_target,render_target_report
    import os
    h = literal_fixture()
    # This fixture immediately removes .git; no background Git maintenance may
    # still create/delete its lock files after the baseline commit returns.
    with monkeypatch.context() as scoped:
        count = int(os.environ.get("GIT_CONFIG_COUNT", "0"))
        scoped.setenv("GIT_CONFIG_COUNT", str(count + 2))
        for offset, (key, value) in enumerate((("maintenance.auto", "false"), ("gc.auto", "0"))):
            scoped.setenv(f"GIT_CONFIG_KEY_{count + offset}", key)
            scoped.setenv(f"GIT_CONFIG_VALUE_{count + offset}", value)
        h["fixture"](tmp_path)
    # A model namespace and source tree can be used without any Git metadata.
    from flowguard.map.target import _remove_readonly
    shutil.rmtree(tmp_path / '.git', onerror=_remove_readonly)
    assert not (tmp_path / '.git').exists()
    assert start_target(tmp_path,'retire an old rule')==0
    assert add_to_target(tmp_path,'policy')==0
    path=tmp_path/'.flowguard/target/models/policy.py'
    path.write_text(path.read_text().replace('invariants=(RULE,)','invariants=()'))
    report=check_target(tmp_path,models=False)
    assert 'promises: policy: -rule safe' in render_target_report(report)
    assert any(f.code=='promise_removed' for f in report.warnings)


def test_port_lines_without_git(tmp_path):
    from dataclasses import fields, is_dataclass, replace
    from pathlib import Path
    import json
    import runpy
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map
    from flowguard.map.port import model_port, port_findings, upward
    from flowguard.map.tree import build_tree
    from flowguard.map.target import check_target, render_target_report
    data, inv = project(tmp_path)
    call = helpers()['call_target']
    assert call(tmp_path,'start','clarify lending rule') == 0
    assert call(tmp_path,'add','lending') == 0
    path=tmp_path/'.flowguard/target/models/lending.py'
    path.write_text(path.read_text().replace('the lending result is finite','the lending result stays finite'))
    assert 'port: lending unchanged (this model only)' in render_target_report(check_target(tmp_path,models=False))
    path.write_text(path.read_text().replace('("lent","refused")}','("lent","refused","waitlisted")}'))
    report = check_target(tmp_path,models=False)
    assert 'port changed: lending out +waitlisted -> verify desk (parent)' in render_target_report(report)
    assert any(f.code=='port_changed_parent_missing' for f in report.errors)


def test_dispatch_edit_is_not_an_upward_change(tmp_path):
    from dataclasses import fields, is_dataclass, replace
    from pathlib import Path
    import json
    import runpy
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from flowguard.map.mapfile import load_map
    from flowguard.map.port import model_port, port_findings, upward
    from flowguard.map.tree import build_tree
    from flowguard.map.target import check_target, render_target_report
    data, inv = dispatch_project(tmp_path)
    call = helpers()['call_target']
    assert call(tmp_path,'start','add a command choice') == 0
    assert call(tmp_path,'add','cmd') == 0
    path=tmp_path/'.flowguard/target/models/cmd.py'
    path.write_text(path.read_text().replace('"x":"a","y":"b"','"x":"a","y":"b","z":"z"'))
    report=check_target(tmp_path,models=False)
    assert 'port: cmd unchanged (this model only); dispatch +z (edge checked by map check)' in render_target_report(report)
    assert any(f.code=='dispatch_without_child' for f in report.errors)
    source=(tmp_path/'.flowguard/models/a.py').read_text().replace("MODEL_ID='a'", 'MODEL_ID="z"').replace('shelf/loans.py:borrow','shelf/loans.py:third')
    (tmp_path/'.flowguard/target/models/z.py').write_text(source)
    with (tmp_path/'shelf/loans.py').open('a') as f: f.write('def third(value): return "left"\n')
    assert not any(f.code=='dispatch_without_child' for f in check_target(tmp_path,models=False).errors)

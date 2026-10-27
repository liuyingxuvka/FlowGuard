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
from dataclasses import fields, is_dataclass, replace
import runpy
from flowguard.map.mapfile import load_map
from flowguard.map.port import model_port, port_findings, upward
from flowguard.map.tree import build_tree
from _fg_helpers import flowguard_port421_helpers as helpers, flowguard_port421_project as project, flowguard_port421_probe as probe, flowguard_port421_errors as errors, flowguard_port421_rewrite as rewrite, flowguard_port421_dispatch_project as dispatch_project, flowguard_port421_escalation_model as escalation_model, flowguard_port421__select_ports as _select_ports, flowguard_port421_fields as fields, flowguard_port421_is_dataclass as is_dataclass, flowguard_port421_replace as replace, flowguard_port421_Path as Path, flowguard_port421_json as json, flowguard_port421_runpy as runpy, flowguard_port421_DEFAULT_IGNORE as DEFAULT_IGNORE, flowguard_port421_build_inventory as build_inventory, flowguard_port421_load_map as load_map, flowguard_port421_model_port as model_port, flowguard_port421_port_findings as port_findings, flowguard_port421_upward as upward, flowguard_port421_build_tree as build_tree

def test_target_check_compares_promises_without_git(tmp_path):
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
    from flowguard.map.target import start_target,add_to_target,check_target,render_target_report
    h=literal_fixture();h['fixture'](tmp_path)
    # A model namespace and source tree can be used without any Git metadata.
    from flowguard.map.target import _remove_readonly
    shutil.rmtree(tmp_path/'.git',onerror=_remove_readonly)
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
    from _fg_helpers import flowguard_port421_helpers as helpers, flowguard_port421_project as project, flowguard_port421_probe as probe, flowguard_port421_errors as errors, flowguard_port421_rewrite as rewrite, flowguard_port421_dispatch_project as dispatch_project, flowguard_port421_escalation_model as escalation_model, flowguard_port421__select_ports as _select_ports, flowguard_port421_fields as fields, flowguard_port421_is_dataclass as is_dataclass, flowguard_port421_replace as replace, flowguard_port421_Path as Path, flowguard_port421_json as json, flowguard_port421_runpy as runpy, flowguard_port421_DEFAULT_IGNORE as DEFAULT_IGNORE, flowguard_port421_build_inventory as build_inventory, flowguard_port421_load_map as load_map, flowguard_port421_model_port as model_port, flowguard_port421_port_findings as port_findings, flowguard_port421_upward as upward, flowguard_port421_build_tree as build_tree
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
    from _fg_helpers import flowguard_port421_helpers as helpers, flowguard_port421_project as project, flowguard_port421_probe as probe, flowguard_port421_errors as errors, flowguard_port421_rewrite as rewrite, flowguard_port421_dispatch_project as dispatch_project, flowguard_port421_escalation_model as escalation_model, flowguard_port421__select_ports as _select_ports, flowguard_port421_fields as fields, flowguard_port421_is_dataclass as is_dataclass, flowguard_port421_replace as replace, flowguard_port421_Path as Path, flowguard_port421_json as json, flowguard_port421_runpy as runpy, flowguard_port421_DEFAULT_IGNORE as DEFAULT_IGNORE, flowguard_port421_build_inventory as build_inventory, flowguard_port421_load_map as load_map, flowguard_port421_model_port as model_port, flowguard_port421_port_findings as port_findings, flowguard_port421_upward as upward, flowguard_port421_build_tree as build_tree
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

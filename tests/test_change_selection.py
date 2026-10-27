"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_impact_shared_test_binding_and_unknown_helper(impact_project):
    from _fg_helpers import map_impact_of as impact_of
    root, data = impact_project
    data["components"][2]["tests"].append("tests/test_orders.py")
    imp = impact_of(root, data, ["tests/test_orders.py"])
    assert imp.direct == [] and imp.dependents == []
    assert imp.tests == ["tests/test_orders.py"]
    assert imp.model_ids == []
    unknown = impact_of(root, data, [".flowguard/models/owners/unbound/helper.py"])
    assert unknown.blocked and not unknown.models and not unknown.model_ids


@pytest.mark.parametrize("edit", ["comment", "docstring", "code", "untouched"])
@pytest.mark.parametrize("line_endings", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_comment_only_edit_keeps_review_but_selects_no_checks(impact_project, edit, line_endings):
    from _fg_helpers import map_impact_of as impact_of
    from flowguard.map.impact import render_impact
    root, data = impact_project
    path = root / "shop/storage.py"
    text = path.read_text(encoding="utf-8")
    edited = {"comment": text.replace("DB = {}\n", "DB = {}  # in-memory store\n\n"),
              "docstring": '"""Order storage."""\n' + text,
              "code": text.replace("return x", "return x or None"),
              "untouched": text}[edit]
    path.write_bytes(edited.replace("\n", line_endings).encode("utf-8"))
    imp = impact_of(root, data, ["shop/storage.py"], base="HEAD", broad=True)
    assert imp.direct == ["storage"]
    if edit == "comment":
        assert imp.comment_only == ["shop/storage.py"] and "comment-only edits" in render_impact(imp)
        assert imp.dependents == [] and imp.tests == [] and imp.models == []
    else:
        assert imp.comment_only == [] and imp.dependents == ["api", "orders"]
        assert "tests/test_storage.py" in imp.tests and "orders_check" in imp.model_ids










def test_removed_literal_sites_reach_function_selection(tmp_path):
    from _fg_helpers import target__target_life_cycle_fixture_helpers
    impact,text=target__target_life_cycle_fixture_helpers('_literal_fixture')['native_case'](tmp_path,'literal')
    assert {'consumer_model','policy'}==set(impact.model_ids)
    assert 'consumer.py:use' in impact.changed_functions
    assert "consumes 'stale'" in text


def test_uncertain_source_broadens_selection(tmp_path):
    from _fg_helpers import map_function_fixture
    impact=map_function_fixture()['native_case'](tmp_path,'removed')
    assert impact.uncertain_files=={'core.py':'a symbol was removed or renamed'}
    assert {'child','importer','other','parent'}==set(impact.model_ids)
    assert impact.whole_test_files==['tests/test_core.py']


def test_missing_selected_model_is_blocked(tmp_path):
    from _fg_helpers import map_function_fixture
    from flowguard.map.inventory import build_inventory
    from flowguard.map.impact import compute_impact,render_impact
    from flowguard.map.common import DEFAULT_IGNORE
    data=map_function_fixture()['fixture'](tmp_path)
    impact=compute_impact(tmp_path,data,build_inventory(tmp_path,DEFAULT_IGNORE,write_cache=False),['.flowguard/models/missing.py'],base='HEAD')
    assert impact.blocked==['.flowguard/models/missing.py: selected model is missing or is not an executable registered model']
    assert 'BLOCKED' in render_impact(impact)

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

def test_s4a_rename_names_the_consumers(tmp_path):
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
    impact,text=literal_fixture()['native_case'](tmp_path,'literal')
    lines=[line for line in text.splitlines() if line.startswith("consumes 'stale' (produced by producer):")]
    assert len(lines)==2
    assert '.flowguard/models/consumer_model.py:' in lines[0]
    assert 'consumer.py:' in lines[1]
    assert 'consumer_model' in impact.model_ids
    assert 'consumer.py:use' in impact.changed_functions
    assert 'tests/test_result.py' in impact.tests


def test_removed_rule_known_bad_and_test_are_promises(tmp_path):
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
    result,text=literal_fixture()['native_case'](tmp_path,'removed')
    assert 'promises: policy: -rule safe; -known-bad bad; -test safe' in text
    assert len(result.promise_findings)==3
    assert all(f['level']=='warn' and f['code']=='promise_removed' for f in result.promise_findings)


def test_moved_rule_prints_moved_not_promise(tmp_path):
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
    result,text=literal_fixture()['native_case'](tmp_path,'moved')
    assert 'moved: 1 rule(s), 1 known-bad, 1 test(s) from policy to recipient' in text
    assert not result.promise_findings


def test_rule_edit_selects_the_child_only(tmp_path):
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
    impact, text = escalation_model()['native_case'](tmp_path, 'rule')
    assert impact.model_ids == ['lending']
    assert 'port: lending unchanged (this model only)' in text


def test_output_change_selects_parent_not_grandparent(tmp_path):
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
    impact, text = escalation_model()['native_case'](tmp_path, 'output')
    assert impact.model_ids == ['consumer', 'desk', 'lending']
    assert 'out +waitlisted -> verify desk (parent), consumer (HANDOFF)' in text
    assert 'grand' not in impact.model_ids


def test_reads_parent_change_selects_parent(tmp_path):
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
    impact, text = escalation_model()['native_case'](tmp_path, 'reads')
    assert impact.model_ids == ['desk', 'lending']
    assert 'reads +answer -> verify desk (parent)' in text

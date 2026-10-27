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

def test_s4c_dropped_consumer_names_the_producer(tmp_path):
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
    from flowguard.map.impact import compute_impact,render_impact
    h=literal_fixture();data=h['fixture'](tmp_path)
    h['write'](tmp_path,'consumer.py','def use(value): return True\n')
    impact=compute_impact(tmp_path,data,build_inventory(tmp_path,DEFAULT_IGNORE,write_cache=False),['consumer.py'],base='HEAD')
    assert "produces 'stale' (consumed by consumer): producer.py:1" in render_impact(impact)


def test_yaml_key_rename_is_mentioned(tmp_path):
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
    from flowguard.map.impact import compute_impact,render_impact
    h=literal_fixture();data=h['fixture'](tmp_path)
    h['write'](tmp_path,'producer.py','def emit(): return {"code":"ready"}\n')
    h['write'](tmp_path,'consumer.py','def use(row): return row["code"]\n')
    h['write'](tmp_path,'cases.yaml','row:\n  code: ready\n')
    subprocess.run(['git','-C',str(tmp_path),'add','.'],check=True)
    subprocess.run(['git','-C',str(tmp_path),'-c','user.name=FlowGuard','-c','user.email=model@example.invalid','commit','-qm','keys'],check=True,capture_output=True)
    h['write'](tmp_path,'producer.py','def emit(): return {"status":"ready"}\n')
    result=compute_impact(tmp_path,data,build_inventory(tmp_path,DEFAULT_IGNORE,write_cache=False),['producer.py'],base='HEAD')
    text=render_impact(result)
    assert "consumes 'code' (produced by producer): consumer.py:1" in text
    assert "mentions 'code' in 1 text files: cases.yaml" in text


def test_typo_consumer_prints_nothing_produces(tmp_path):
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
    from flowguard.map.impact import compute_impact,render_impact
    h=literal_fixture();data=h['fixture'](tmp_path)
    h['write'](tmp_path,'consumer.py','def use(value): return value == "stale_typo"\n')
    impact=compute_impact(tmp_path,data,build_inventory(tmp_path,DEFAULT_IGNORE,write_cache=False),['consumer.py'],base='HEAD')
    text=render_impact(impact)
    assert "nothing produces 'stale_typo' (consumed at consumer.py:1); check the spelling" in text


def test_split_that_drops_a_field_names_it(tmp_path):
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
    from flowguard.map.impact import compute_impact,render_impact
    h=literal_fixture();data=h['fixture'](tmp_path)
    path=tmp_path/'.flowguard/models/policy.py'
    parent=path.read_text().replace('retained','replacement').replace('    name="Emit"','    name="Emit"\n    reads=()\n    writes=("replacement",)')
    parent+='\nHANDOFF={"policy_child":{"replacement":"replacement"}}\n'
    path.write_text(parent)
    child=parent.replace('MODEL_ID="policy"','MODEL_ID="policy_child"').replace('PARENT="producer"','PARENT="policy"').replace('"producer.py:emit"','"producer.py:fold"').replace('NATIVE_ARGS=()','NATIVE_ARGS=("stale",)')
    child=child[:child.rindex('HANDOFF=')]+'OUTPUTS={"replacement":("stale",)}\n'
    child_path=path.parent/'policy_child.py';child_path.write_text(child)
    with (tmp_path/'producer.py').open('a') as stream:stream.write('def fold(value): return value\n')
    changed=['.flowguard/models/policy.py','.flowguard/models/policy_child.py']
    result=compute_impact(tmp_path,data,build_inventory(tmp_path,DEFAULT_IGNORE,write_cache=False),changed,base='HEAD')
    assert '-field retained' in render_impact(result)
    # The same split retains its old field in the child; this must remove the warning.
    child_path.write_text(child.replace('replacement','retained'))
    path.write_text(parent.replace('"replacement":"replacement"','"retained":"replacement"'))
    preserved=compute_impact(tmp_path,data,build_inventory(tmp_path,DEFAULT_IGNORE,write_cache=False),changed,base='HEAD')
    assert '-field retained' not in render_impact(preserved)


def test_removing_one_of_two_bound_tests_is_named(tmp_path):
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
    from flowguard.map.impact import compute_impact,render_impact
    h=literal_fixture();data=h['fixture'](tmp_path)
    path=tmp_path/'.flowguard/models/policy.py'
    text=path.read_text().replace('"tests/test_result.py:test_result"]','"tests/test_result.py:test_result","tests/test_result.py:test_other"]')
    path.write_text(text)
    with (tmp_path/'tests/test_result.py').open('a') as stream:stream.write('def test_other(): assert True\n')
    subprocess.run(['git','-C',str(tmp_path),'add','.'],check=True)
    subprocess.run(['git','-C',str(tmp_path),'-c','user.name=FlowGuard','-c','user.email=model@example.invalid','commit','-qm','two bound tests'],check=True,capture_output=True)
    path.write_text(text.replace(',"tests/test_result.py:test_other"',''))
    result=compute_impact(tmp_path,data,build_inventory(tmp_path,DEFAULT_IGNORE,write_cache=False),['.flowguard/models/policy.py'],base='HEAD')
    assert len(result.promise_findings)==1
    assert '-test safe (tests/test_result.py:test_other)' in render_impact(result)

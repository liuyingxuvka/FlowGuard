"""Tests of the model and its real native implementation."""
import pytest
from pathlib import Path


def test_identical_info_grouped_into_one_line(capsys, tmp_path, monkeypatch):
    import json
    from pathlib import Path
    from flowguard.map import cli
    from flowguard.map.common import Finding, print_findings
    notes = [Finding("info", "same", f"c{i}", "note") for i in range(24)]
    warnings = [Finding("warn", "same", f"w{i}", "warning") for i in range(3)]
    counts = print_findings(notes + warnings, "lint", as_json=False, limit=80)
    text = capsys.readouterr().out
    assert counts == {"error": 0, "warn": 3, "info": 24}
    assert sum(line.startswith("INFO") for line in text.splitlines()) == 1
    assert "INFO same x24: c0, c1, c10, c11, c12, c13, c14, c15 (+16 more; python -m flowguard map lint --json)" in text
    assert sum(line.startswith("WARN") for line in text.splitlines()) == 3
    print_findings(notes, "lint", as_json=True, limit=1)
    assert len(json.loads(capsys.readouterr().out)["findings"]) == 24
    # Exercise release's real output boundary: findings precede real model execution.
    import runpy
    from types import SimpleNamespace
    helpers = runpy.run_path(str(Path(__file__).parents[1] / ".flowguard/models/model_runs.py"))
    helpers["make_fixture"](tmp_path)
    monkeypatch.setattr(cli, "run_check", lambda *a, **kw: [Finding("info", "same", str(i), "note") for i in range(24)])
    assert cli.cmd_verify(tmp_path, SimpleNamespace(limit=80, jobs=1, shards=None)) == 0
    output = capsys.readouterr().out
    assert sum(line.startswith("INFO same x24:") for line in output.splitlines()) == 1
    assert "PASS  first" in output and "PASS  second" in output

import json
import subprocess
from pathlib import Path
import pytest
from flowguard.__main__ import main
from flowguard.map.cli import _context
from flowguard.map.check import run_check
from flowguard.map.lint import run_lint
from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
import shutil
import sys
import tempfile
import unittest
from flowguard.map.discover import component_summary, console_scripts, discover, discover_inventory, file_facts
from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory
from flowguard.map.lint import entrypoint_coverage_findings, run_lint, scoped_architecture_findings
from flowguard.map.scan import guess_tests, new_map, propose_components
from _fg_helpers import flowguard_map_discover421_ROOT as ROOT, flowguard_map_discover421_APP as APP, flowguard_map_discover421_STORE as STORE, flowguard_map_discover421_CLI as CLI, flowguard_map_discover421_write_project as write_project, flowguard_map_discover421_map_cli as map_cli, flowguard_map_discover421__INJECTED_STORE as _INJECTED_STORE, flowguard_map_discover421__INJECTED_SERVICE as _INJECTED_SERVICE, flowguard_map_discover421__INJECTED_CLI as _INJECTED_CLI, flowguard_map_discover421__injected_project as _injected_project, flowguard_map_discover421__resolution_case as _resolution_case, flowguard_map_discover421_literal_fixture as literal_fixture, flowguard_map_discover421_json as json, flowguard_map_discover421_shutil as shutil, flowguard_map_discover421_subprocess as subprocess, flowguard_map_discover421_sys as sys, flowguard_map_discover421_tempfile as tempfile, flowguard_map_discover421_unittest as unittest, flowguard_map_discover421_Path as Path, flowguard_map_discover421_pytest as pytest, flowguard_map_discover421_component_summary as component_summary, flowguard_map_discover421_console_scripts as console_scripts, flowguard_map_discover421_discover as discover, flowguard_map_discover421_discover_inventory as discover_inventory, flowguard_map_discover421_file_facts as file_facts, flowguard_map_discover421_DEFAULT_IGNORE as DEFAULT_IGNORE, flowguard_map_discover421_build_inventory as build_inventory, flowguard_map_discover421_entrypoint_coverage_findings as entrypoint_coverage_findings, flowguard_map_discover421_run_lint as run_lint, flowguard_map_discover421_scoped_architecture_findings as scoped_architecture_findings, flowguard_map_discover421_guess_tests as guess_tests, flowguard_map_discover421_new_map as new_map, flowguard_map_discover421_propose_components as propose_components
import pytest, os, json
from _fg_helpers import map_views421_pytest as pytest, map_views421_os as os, map_views421_json as json, map_views421_Path as Path

def test_accepted_debts_mean_the_same_in_check_and_lint(tmp_path):
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
    write(tmp_path, "app.py", "def run():\n    open('out.txt', 'w').write('x')\n    return True\n")
    write(tmp_path, "lib.py", "VALUE = 1\n")
    data["components"].append({"id": "lib", "summary": "Lib", "responsibilities": ["hold a value"], "files": ["lib.py"],
                               "entrypoints": [], "tests": [], "models": [], "depends_on": [], "status": "draft"})
    data["components"][0]["depends_on"] = ["lib"]
    data["accepted_debts"] = [
        {"code": "dep_unused", "component": "app", "contains": "lib", "reason": "loaded by path at runtime"},
        {"code": "entrypoint_unmodeled", "component": "app", "reason": "file output is covered by an integration test"}]
    save(tmp_path, data)
    d, inv = _context(tmp_path)
    levels = {f.code: f.level for f in run_check(tmp_path, d, inv)}
    assert "dep_unused" not in levels and levels.get("entrypoint_unmodeled") == "info"
    assert "debt_stale" not in {f.code for f in run_lint(tmp_path, d, inv)}
    write(tmp_path, "app.py", "import lib\n\ndef run():\n    open('out.txt', 'w').write('x')\n    return lib.VALUE\n")
    d, inv = _context(tmp_path)
    assert any(f.code == "debt_stale" and "loaded by path" in f.message for f in run_lint(tmp_path, d, inv))


def test_broken_uses_is_named(tmp_path):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
    data, inv, _ = _scope_helpers()["scope_fixture"](tmp_path, "uses")
    path = tmp_path / ".flowguard/models/m.py"
    path.write_text(path.read_text().replace('"Read": "lib.py:value"', '"Read": "lib.py:missing"'))
    broken = [f for f in run_check(tmp_path, data, inv) if f.code == "model_anchor_broken" and "USES Read" in f.message]
    assert len(broken) == 1 and "missing" in broken[0].message


def test_new_writer_of_modeled_state_is_reported(tmp_path, monkeypatch):
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
    from flowguard.map import discover as discovery
    from flowguard.map.check import run_check
    from flowguard.map.cli import _context

    def write(path, text):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf-8')

    write('pkg/__init__.py', '')
    write('pkg/proxy.py', '''class Proxy:
    def __init__(self):
        self._parts = []
        self._map = {}
        self.label = 'only init'
    def __setitem__(self, key, value):
        self._parts[0] = value
        self._map[key] = 0
    def move_to_end(self, key):
        self._parts.append(key)
        self._map[key] = 1
    def __delitem__(self, key):
        del self._map[key]

class Other:
    def __init__(self):
        self._map = {}
    def clear(self, key):
        del self._map[key]
''')
    write('other.py', 'class Proxy:\n    def __delitem__(self, key):\n        del self._map[key]\n')
    model = ('MODEL_ID="proxy_model"\nCOMPONENTS=["proxy"]\n'
             'IMPLEMENTED_BY={"Set":"pkg/proxy.py:Proxy.__setitem__"}\n'
             'def build_explorer(): pass\n'
             'def conformance():\n    from pkg.proxy import Proxy\n    return Proxy()\n')
    write('.flowguard/models/proxy.py', model)
    data = dict(schema='flowguard.map.v1', components=[
        dict(id='proxy', files=['pkg/*.py'], summary='Proxy ordering', responsibilities=['order parts'],
             tests=[], models=[], depends_on=[], status='draft'),
        dict(id='other', files=['other.py'], summary='Other', responsibilities=['unrelated state'],
             tests=[], models=[], depends_on=[], status='draft')])
    write('.flowguard/map.json', json.dumps(data))
    current, inv = _context(tmp_path)
    raw = discover_inventory(tmp_path, inv)
    assert 'Proxy.__delitem__' in raw['files']['pkg/proxy.py']['state']['Proxy._map']
    original = discovery.discover_inventory
    calls = []

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(discovery, 'discover_inventory', counted)
        warnings = [f for f in run_check(tmp_path, current, inv) if f.code == 'model_writer_unbound']
    assert len(calls) == 1
    assert len(warnings) == 2
    assert all(f.level == 'warn' and f.component == 'proxy' for f in warnings)
    assert all('model proxy_model' in f.message and 'pkg/proxy.py:Proxy.__setitem__' in f.message for f in warnings)
    assert any('pkg/proxy.py:Proxy.move_to_end' in f.message for f in warnings)
    assert any('pkg/proxy.py:Proxy.__delitem__' in f.message for f in warnings)
    assert map_cli(tmp_path, 'check').returncode == 0
    assert len([f for f in run_lint(tmp_path, current, inv) if f.code == 'model_writer_unbound']) == 2

    data['accepted_debts'] = [dict(code='model_writer_unbound', component='proxy', contains=symbol,
                                    reason='An existing ordering path awaits model extension')
                              for symbol in ['Proxy.move_to_end', 'Proxy.__delitem__']]
    write('.flowguard/map.json', json.dumps(data))
    current, inv = _context(tmp_path)
    assert [f.level for f in run_check(tmp_path, current, inv) if f.code == 'model_writer_unbound'] == ['info', 'info']
    lint = run_lint(tmp_path, current, inv)
    assert len([f for f in lint if f.code == 'model_writer_unbound' and f.level == 'info']) == 2
    assert not any(f.code == 'debt_stale' for f in lint)

    # Exclusions come from every registered model, including a separate contract.
    data.pop('accepted_debts')
    separate = '.flowguard/models/proxy_writer.py'
    data['components'][0]['models'] = [separate]
    write(separate, 'MODEL_ID="proxy_writer"\n'
          'IMPLEMENTED_BY={"Delete":"pkg/proxy.py:Proxy.__delitem__"}\n'
          'NOT_MODELED={"pkg/proxy.py:Proxy.move_to_end":"Ordering is covered by its direct test"}\n'
          'def build_explorer(): pass\ndef conformance(): pass\n')
    write('.flowguard/map.json', json.dumps(data))
    current, inv = _context(tmp_path)
    assert not any(f.code == 'model_writer_unbound' for f in run_check(tmp_path, current, inv))


def test_coverage_line_counts_explained_entrypoints(tmp_path, monkeypatch):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_views421_pytest as pytest, map_views421_os as os, map_views421_json as json, map_views421_Path as Path
    from flowguard.map.views import render_show
    from _fg_helpers import view__fg232_count_discovery as _fg232_count_discovery, view__fg232_view_project as _fg232_view_project
    import sys
    import pytest
    from flowguard.map import proof
    from flowguard.map.lint import run_lint

    data, inv, marker = _fg232_view_project(tmp_path)
    before = [(finding.level, finding.code, finding.component, finding.message)
              for finding in run_lint(tmp_path, data, inv)]
    calls = _fg232_count_discovery(monkeypatch)

    def _fg232_forbid_execution(*args, **kwargs):
        raise AssertionError('read must not execute a user model or pytest')

    with monkeypatch.context() as guard:
        for name in ('run_models', 'run_model', 'run_model_in_process', '_load'):
            guard.setattr(proof, name, _fg232_forbid_execution)
        guard.setattr(pytest, 'main', _fg232_forbid_execution)
        focused = render_show(tmp_path, data, inv, component='subject', detail=False, budget=8000)
        assert len(calls) == 1
        line = next(line for line in focused.splitlines()
                    if 'coverage: entrypoints 2 of 4 bound (model 1, test 1), 1 by reason, 0 unlisted; state writers 1 of 2 bound (model 1, test 0), 0 by reason;' in line)
        unexplained = line.partition('; unexplained: ')[2]
        assert 'view232_subject.py:unexplained' in unexplained and 'view232_subject.py:Ledger.purge' in unexplained
        assert 'view232_subject.py:by_model' not in unexplained and 'view232_subject.py:by_scope' not in unexplained
        assert 'view232_subject.py:by_test' not in unexplained and 'Ledger.__init__' not in unexplained
        calls.clear()
        overview = render_show(tmp_path, data, inv, component=None, detail=False, budget=8000)
        assert len(calls) == 1
    assert ('coverage: entrypoints 3 of 5 bound (model 2, test 1), 1 by reason, 0 unlisted; state writers 1 of 2 bound (model 1, test 0), 0 by reason') in overview
    assert 'truncated' not in overview
    after = [(finding.level, finding.code, finding.component, finding.message)
             for finding in run_lint(tmp_path, data, inv)]
    assert after == before
    assert not marker.exists()
    assert not any(name.startswith('view232_') for name in sys.modules)

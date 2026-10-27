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
import pytest, os, json
from _fg_helpers import map_views421_pytest as pytest, map_views421_os as os, map_views421_json as json, map_views421_Path as Path

def test_model_components_come_from_the_model_file(tmp_path):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
    from flowguard.map.impact import compute_impact
    from flowguard.map.tree import build_tree

    data = project(tmp_path)
    path = ".flowguard/models/one.py"
    write(tmp_path, path, CONTRACT)
    assert not {"model_binding_missing", "model_unreferenced"} & {f.code for f in findings(tmp_path)}
    write(tmp_path, "other.py", "def unrelated(): return 0\n")
    data["components"].append({"id": "other", "files": ["other.py"], "models": [path], "status": "draft"})
    save(tmp_path, data)
    current, inv = _context(tmp_path)
    tree = build_tree(tmp_path, current, inv)
    assert tree.nodes["one"].components == {"app"}
    assert [n.id for n in tree.models_for_component("app")] == ["one"]
    assert tree.models_for_component("other") == []
    listed = [f for f in findings(tmp_path) if f.code == "model_listed_unrelated"]
    assert len(listed) == 1 and listed[0].level == "warn" and listed[0].component == "other"
    assert "one" not in compute_impact(tmp_path, current, inv, ["other.py"]).model_ids
    assert "one" in compute_impact(tmp_path, current, inv, ["app.py"]).model_ids


def test_deleted_or_renamed_test_breaks_declared_model_test_link(tmp_path):
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
    path = ".flowguard/models/one.py"
    write(tmp_path, path, CONTRACT + '\nTESTED_BY = {"returns_true": ["tests/test_app.py:test_run"]}\n')
    data["components"][0]["models"] = [path]
    save(tmp_path, data)
    assert "model_test_broken" not in {f.code for f in findings(tmp_path)}
    write(tmp_path, "tests/test_app.py", "def test_renamed():\n    assert True\n")
    assert "model_test_broken" in {f.code for f in findings(tmp_path)}


def test_dangerous_unmodeled_entry_and_invalid_negative_scope_are_visible(tmp_path):
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
    assert "entrypoint_unmodeled" in {f.code for f in findings(tmp_path)}
    write(tmp_path, ".flowguard/models/one.py", CONTRACT + '\nNOT_MODELED = {"app.py:run": "Filesystem integration is tested directly, not a finite business proof."}\n')
    data["components"][0]["models"] = [".flowguard/models/one.py"]
    save(tmp_path, data)
    assert "entrypoint_unmodeled" not in {f.code for f in findings(tmp_path)}
    write(tmp_path, ".flowguard/models/one.py", CONTRACT + '\nNOT_MODELED = []\n')
    assert "model_contract" in {f.code for f in findings(tmp_path)}


def test_flow_relation_is_an_info_hint_for_unrelated_functions(tmp_path):
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
    write(tmp_path, "app.py", "def run():\n    return True\n\ndef finish():\n    return False\n")
    data["flows"] = [{"id": "journey", "steps": ["app:run", "app:finish"]}]
    save(tmp_path, data)
    d, inv = _context(tmp_path)
    assert any(f.code == "flow_step_unreached" and f.level == "info" for f in run_lint(tmp_path, d, inv))
    write(tmp_path, "app.py", "def run():\n    return finish()\n\ndef finish():\n    return False\n")
    d, inv = _context(tmp_path)
    assert not any(f.code == "flow_step_unreached" for f in run_lint(tmp_path, d, inv))


def test_string_literals_are_dependency_evidence_only_for_exact_modules_or_symbols(tmp_path):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
    from flowguard.map.mapfile import dependency_evidence
    write(tmp_path, "pkg/__init__.py", "")
    write(tmp_path, "pkg/b.py", "def func():\n    return 1\n")
    save(tmp_path, {"schema": "flowguard.map.v1", "components": [
        {"id": "a", "summary": "A", "responsibilities": ["a"], "files": ["pkg/a.py"], "entrypoints": [],
         "tests": [], "models": [], "depends_on": [], "status": "draft"},
        {"id": "b", "summary": "B", "responsibilities": ["b"], "files": ["pkg/__init__.py", "pkg/b.py"],
         "entrypoints": [], "tests": [], "models": [], "depends_on": [], "status": "draft"},
    ]})
    write(tmp_path, "pkg/a.py", 'import logging\nSCHEMA = "pkg.b.v1"\nLOG = logging.getLogger("pkg.b.events")\n')
    data, inv = _context(tmp_path)
    assert "b" not in dependency_evidence(data, inv)["a"]
    for condition in ('x != "pkg.b"', 'module != "pkg"'):
        write(tmp_path, "pkg/a.py", f"if {condition}:\n    pass\n")
        data, inv = _context(tmp_path)
        assert "b" not in dependency_evidence(data, inv)["a"], condition
    for literal in ('"pkg.b"', '"pkg.b:func"', '"pkg.b.func"'):
        write(tmp_path, "pkg/a.py", f"import importlib\nTARGET = importlib.import_module({literal})\n")
        data, inv = _context(tmp_path)
        assert "b" in dependency_evidence(data, inv)["a"], literal
    for text in ('_EXPORTS = {"pkg.b": ("func",)}\ndef __getattr__(name):\n    pass\n',
                 'TARGET = __import__("pkg")\n',
                 'TARGET = "pkg.b:func"\n',
                 'TARGET = "pkg.b.func"\n'):
        write(tmp_path, "pkg/a.py", text)
        data, inv = _context(tmp_path)
        assert "b" in dependency_evidence(data, inv)["a"], text


def test_find_miss_names_the_closest_owners(tmp_path, capsys):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_views421_pytest as pytest, map_views421_os as os, map_views421_json as json, map_views421_Path as Path
    import json
    from _fg_helpers import view__component as _component
    import json
    from flowguard.map import cli

    (tmp_path / '.flowguard').mkdir()
    components = [dict(_component('timed', responsibilities=['rejects expired tokens']), files=['timed.py']),
                  dict(_component('signing', responsibilities=['sign payloads']), files=['signing.py'])]
    for cid in ('timed', 'signing'):
        (tmp_path / f'{cid}.py').write_text('def run(): return True\n')
    (tmp_path / '.flowguard/map.json').write_text(json.dumps({'schema': 'flowguard.map.v1', 'project': 'p',
                                                             'components': components}))
    code = cli.main(['--root', str(tmp_path), 'find', 'expiry'])
    output = capsys.readouterr().out
    assert code == 1 and output.startswith('no existing owner found;'), output
    assert 'closest owners (check these before creating a new component):' in output
    assert '  timed: rejects expired tokens' in output and 'signing' not in output

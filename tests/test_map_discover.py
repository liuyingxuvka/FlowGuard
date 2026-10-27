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

@pytest.mark.parametrize('operation', ['self.value = 1', 'self.value[0] = 1', 'self.value[0] += 1',
                                      'self.value += 1', 'del self.value[0]', 'del self.value',
                                      'self.value.append(1)'])
def test_state_writes_include_delete_and_existing_assignment_forms(operation):
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
    source = ('class Proxy:\n    def __init__(self):\n        self.value = []\n        self.label = "only init"\n'
              '    def write(self):\n        ' + operation + '\n')
    facts = file_facts(source, 'proxy', '', 'proxy.py')
    assert facts['functions']['Proxy.write']['writes'] == ['Proxy.value']
    assert facts['state']['Proxy.value'] == ['Proxy.__init__', 'Proxy.write']
    assert 'Proxy.label' not in facts['state']
    assert 'Proxy.label' not in facts['functions']['Proxy.__init__']['writes']


def test_subscript_store_is_key_write():
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
    from flowguard.map.discover import literal_sites
    source='''"""ignored_doc"""
c["status"] = "ready"
read = c["status"]
del c["gone"]
c.get("missing")
x in ("stale", "draft")
label=f"ignored_part:{c['code']}"
match x:
    case "blocked": pass
'''
    sites=literal_sites(source)
    assert ('status',2,'key_write') in sites
    assert ('status',3,'key_read') in sites and ('gone',4,'key_read') in sites
    assert ('missing',5,'key_read') in sites
    assert ('stale',6,'compare') in sites and ('draft',6,'compare') in sites
    assert ('code',7,'key_read') in sites and ('blocked',9,'compare') in sites
    assert not any(value in ('ignored_doc','ignored_part:') for value,line,role in sites)


class DiscoverTests(unittest.TestCase):
    def test_local_variable_named_like_a_library_is_not_an_effect(self) -> None:
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
        facts = file_facts(APP, "notes.app", "notes", "notes/app.py")
        self.assertEqual([], facts["functions"]["tally"]["effects"])
        self.assertEqual("network", facts["functions"]["create_note"]["effects"][0][0])


class DiscoveryBoundaryTests(unittest.TestCase):
    def test_console_scripts_from_all_packaging_formats(self) -> None:
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
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "cli.py").write_text("def main(): pass\n", encoding="utf-8")
            (root / "pyproject.toml").write_text('[project.scripts]\ntoml-cli = "cli:main"\n', encoding="utf-8")
            (root / "setup.cfg").write_text('[options.entry_points]\nconsole_scripts =\n    cfg-cli = cli:main\n', encoding="utf-8")
            (root / "setup.py").write_text('setup(entry_points={"console_scripts": ["py-cli = cli:main"]})', encoding="utf-8")
            self.assertEqual({"toml-cli", "cfg-cli", "py-cli"}, {name for name, _, _ in console_scripts(root)})
            raw = discover_inventory(root, build_inventory(root, DEFAULT_IGNORE))
            scripts = [entry for entry in raw["files"]["cli.py"]["entrypoints"] if entry["kind"] == "console_script"]
            self.assertEqual(3, len(scripts))
            self.assertTrue(all(entry["symbol"] == "main" for entry in scripts))

    def test_local_imports_and_callback_arguments_reach_effects_without_leaking(self) -> None:
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
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sink.py").write_text('def save():\n    open("db", "w").write("x")\n'
                                           'class Store:\n    def save(self):\n        open("class-db", "w")\n', encoding="utf-8")
            (root / "app.py").write_text(
                'def entry():\n    from sink import save as callback\n    register(callback)\n'
                'def unrelated():\n    callback()\n'
                'def class_entry():\n    from sink import Store\n    Store().save()\n', encoding="utf-8")
            raw = discover(root, {"app.py": "app", "sink.py": "sink"}, write_cache=False)
            found = component_summary(raw, ["app.py"])
            self.assertEqual(["sink.py#save"], raw["edges"]["app.py#entry"])
            self.assertNotIn("app.py#unrelated", raw["edges"])
            self.assertIn("sink.py#Store.save", raw["edges"]["app.py#class_entry"])
            from flowguard.map.discover import reachable_effects
            self.assertEqual({"fs_write"}, set(reachable_effects(raw, "app.py#entry")))

    def test_constructors_env_copy_and_initializer_only_state_are_not_effects(self) -> None:
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
        facts = file_facts(
            'import requests\nimport os\nclass Store:\n'
            '    def __init__(self):\n        self.client = requests.Session()\n        self.cache = {}\n'
            'def harmless():\n    client = requests.Session()\n    env = os.environ.copy()\n'
            'def send():\n    client = requests.Session()\n    client.post("https://example.org")\n',
            "app", "", "app.py")
        self.assertEqual({}, facts["state"])
        self.assertEqual([], facts["functions"]["harmless"]["effects"])
        self.assertEqual([], facts["functions"]["Store.__init__"]["effects"])
        self.assertEqual(["network"], [kind for kind, _, _ in facts["functions"]["send"]["effects"]])

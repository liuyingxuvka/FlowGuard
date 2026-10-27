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

def test_read_ignores_retired_words_in_agent_instructions(tmp_path, capsys):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
    project(tmp_path)
    write(tmp_path, "AGENTS.md", "We retired `flowguard self-review` long ago.\n")
    assert main(["read", "--root", str(tmp_path)]) == 0
    assert "app" in capsys.readouterr().out


def test_find_and_check_point_at_the_existing_owner(tmp_path, capsys):
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
    write(tmp_path, "shop/orders.py", "def place():\n    return 1\n")
    data["components"].append({"id": "orders", "summary": "Places orders", "responsibilities": ["place orders"],
                               "files": ["shop/orders.py"], "entrypoints": [], "tests": [], "models": [],
                               "depends_on": [], "state": ["order status"], "status": "draft"})
    save(tmp_path, data)
    assert main(["read", "--root", str(tmp_path), "--find", "order"]) == 0
    out = capsys.readouterr().out
    assert "state: order status" in out and "create a new component only when none does" in out
    write(tmp_path, "shop/refunds.py", "def refund():\n    return 1\n")
    assert [f.message for f in findings(tmp_path) if f.code == "file_unmapped"] == [
        "shop/refunds.py has no owning component; the files next to it belong to orders: "
        "add it there unless it is a new responsibility"]
    write(tmp_path, "shop/billing.py", "def bill():\n    return 1\n")
    data["components"].append({"id": "billing", "summary": "Bills orders", "responsibilities": ["bill orders"],
                               "files": ["shop/billing.py"], "entrypoints": [], "tests": [], "models": [],
                               "depends_on": [], "status": "draft"})
    save(tmp_path, data)
    assert [f.message for f in findings(tmp_path) if f.code == "file_unmapped"] == [
        "shop/refunds.py has no owning component; the files next to it belong to billing, orders: "
        "add it to the one that owns its responsibility"]


def test_uses_is_named_in_component_read(tmp_path, capsys):
    import json
    import subprocess
    from pathlib import Path
    import pytest
    from flowguard.__main__ import main
    from flowguard.map.cli import _context
    from flowguard.map.check import run_check
    from flowguard.map.lint import run_lint
    from _fg_helpers import flowguard_map_contracts421_write as write, flowguard_map_contracts421_project as project, flowguard_map_contracts421_save as save, flowguard_map_contracts421_findings as findings, flowguard_map_contracts421_CONTRACT as CONTRACT, flowguard_map_contracts421__placement_port_source as _placement_port_source, flowguard_map_contracts421__fg233_parent_project as _fg233_parent_project, flowguard_map_contracts421__scope_helpers as _scope_helpers, flowguard_map_contracts421_json as json, flowguard_map_contracts421_subprocess as subprocess, flowguard_map_contracts421_Path as Path, flowguard_map_contracts421_pytest as pytest, flowguard_map_contracts421_main as main, flowguard_map_contracts421__context as _context, flowguard_map_contracts421_run_check as run_check, flowguard_map_contracts421_run_lint as run_lint
    _scope_helpers()["scope_fixture"](tmp_path, "uses")
    assert main(["read", "--component", "lib", "--root", str(tmp_path), "--budget", "16000"]) == 0
    assert "used by: m (USES Read)" in capsys.readouterr().out


def test_locate_check_target_names_target_findings():
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_views421_pytest as pytest, map_views421_os as os, map_views421_json as json, map_views421_Path as Path
    from pathlib import Path
    from contextlib import redirect_stdout
    from io import StringIO
    from flowguard.__main__ import main
    out=StringIO()
    with redirect_stdout(out):code=main(['read','--root',str(Path(__file__).parents[1]),'--find','flowguard/map/target.py:check_target'])
    assert code==0 and out.getvalue().splitlines()[1].startswith('model target_findings')


def test_find_words_ends_with_locate_line(tmp_path):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_views421_pytest as pytest, map_views421_os as os, map_views421_json as json, map_views421_Path as Path
    from _fg_helpers import view_locate_fixture as locate_fixture
    from flowguard.__main__ import main
    from contextlib import redirect_stdout
    from io import StringIO
    helper=locate_fixture();helper['fixture'](tmp_path)
    out=StringIO()
    with redirect_stdout(out):code=main(['read','--root',str(tmp_path),'--find','owned'])
    assert code==0 and out.getvalue().splitlines()[-1].startswith('locate: ')


def test_unknown_field_line_exits_one(tmp_path,capsys):
    import pytest, os, json
    from pathlib import Path
    from _fg_helpers import map_views421_pytest as pytest, map_views421_os as os, map_views421_json as json, map_views421_Path as Path
    from _fg_helpers import view__field_project as _field_project
    from flowguard.__main__ import main
    _field_project(tmp_path)
    assert main(['read','--root',str(tmp_path),'--field','nonexistent'])==1
    assert capsys.readouterr().out=='field nonexistent: no model, rule or code site\n'

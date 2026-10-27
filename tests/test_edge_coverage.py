"""Tests grouped by their model or native component."""
from __future__ import annotations

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

def test_each_static_edge_mistake_has_its_code(tmp_path):
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
    for case, code in (("drops_child_value", "handoff_drops_child_value"),
            ("missing_parent_input", "child_input_unprovided"), ("uncovered_parent_field", "parent_field_uncovered"),
            ("overlapping_receipts", "sibling_outputs_overlap"), ("consumer_receipts", "sibling_outputs_overlap"), ("no_child_output", "child_unconnected")):
        root = tmp_path / case
        data, inv = project(root, case)
        assert errors(root, data, inv) == {code}
    mutations = (
        ("unreadable", "desk", '@dataclass(frozen=True)', '', {"port_unreadable"}),
        ("writes", "desk", '    writes=("request","answer")\n', '', {"parent_writes_undeclared"}),
        ("unhandled", "lending", 'OUTPUTS = {"answer":("lent","refused")}',
         'OUTPUTS = {"answer":("lent","refused"),"request":("lend_request",)}', {"handoff_output_unhandled"}),
        ("unknown_into", "desk", '"answer":"answer"', '"answer":"ghost"', {"handoff_into_unknown", "parent_field_uncovered"}),
    )
    for case, model, old, new, codes in mutations:
        root = tmp_path / case
        data, inv = project(root)
        rewrite(root, model, old, new)
        assert errors(root, data, build_inventory(root, DEFAULT_IGNORE, write_cache=False)) == codes
    root = tmp_path / "kit_parent"
    data, inv = project(root)
    (root / ".flowguard/models/desk.py").write_text('from flowguard.kit import feature_explorer\nMODEL_ID="desk"\nPARENT="cli"\nIMPLEMENTED_BY={"Serve":"shelf/cli.py:main"}\nHANDOFF={"lending":{"answer":"outcome"}}\nKEEPS=("features","codes","plain_outcome","plain_codes")\ndef build_explorer(): return feature_explorer(())\n')
    rewrite(root, "lending", 'READS_PARENT = ("request",)', 'READS_PARENT = ()')
    assert errors(root, data, build_inventory(root, DEFAULT_IGNORE, write_cache=False)) == {"kit_model_parent"}
    root = tmp_path / "output_not_state"
    data, inv = project(root)
    rewrite(root, "lending", 'OUTPUTS = {"answer":("lent","refused")}', 'OUTPUTS = {"answer":("lent","refused"),"ghost":("boo",)}')
    rewrite(root, "desk", '"answer":"answer"', '"answer":"answer","ghost":"extra"')
    rewrite(root, "desk", '    reply: str = ""', '    reply: str = ""\n    extra: str = ""')
    assert errors(root, data, build_inventory(root, DEFAULT_IGNORE, write_cache=False)) == {"outputs_not_state"}
    root = tmp_path / "duplicate"
    data, inv = project(root)
    rewrite(root, "lending", 'PARENT = "desk"', 'PARENT = "loans"')
    rewrite(root, "lending", '"shelf/loans.py:LoanService.borrow"', '"shelf/cli.py:main"')
    rewrite(root, "lending", 'COMPONENTS = ["loans"]', 'COMPONENTS = ["loans","cli"]')
    assert errors(root, data, build_inventory(root, DEFAULT_IGNORE, write_cache=False)) == {"duplicate_child_owner"}
    # Cousins under sibling components and component/descendant placements also collide.
    data["components"] += [dict(id=cid, parent="cli", layer="interface", summary=cid, responsibilities=[], files=[], tests=[], models=[], depends_on=[], status="draft") for cid in ("left","right")]
    (root / ".flowguard/map.json").write_text(json.dumps(data))
    path = root / ".flowguard/models/desk.py"
    path.write_text(path.read_text()+'\nCOMPONENTS=["cli"]\n')
    rewrite(root, "desk", 'PARENT = "cli"', 'PARENT = "left"')
    rewrite(root, "lending", 'PARENT = "loans"', 'PARENT = "right"')
    assert errors(root, data, build_inventory(root, DEFAULT_IGNORE, write_cache=False)) == {"duplicate_child_owner"}
    rewrite(root, "desk", 'PARENT = "left"', 'PARENT = "cli"')
    rewrite(root, "lending", 'PARENT = "right"', 'PARENT = "left"')
    assert errors(root, data, build_inventory(root, DEFAULT_IGNORE, write_cache=False)) == {"duplicate_child_owner"}
    rewrite(root, "lending", 'PARENT = "left"', 'PARENT = "desk"')
    assert not errors(root, data, build_inventory(root, DEFAULT_IGNORE, write_cache=False))
    # A read-only duplicate never acquires ownership.
    rewrite(root, "lending", '"shelf/cli.py:main"', '"shelf/loans.py:LoanService.borrow"')
    path = root / ".flowguard/models/lending.py"
    path.write_text(path.read_text().replace('PARENT = "desk"', 'PARENT = "loans"')+'\nUSES={"Serve":"shelf/cli.py:main"}\n')
    assert not errors(root, data, build_inventory(root, DEFAULT_IGNORE, write_cache=False))

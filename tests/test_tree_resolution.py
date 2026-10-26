"""Tests grouped by their model or native component."""
from __future__ import annotations
import pytest,os,json
from pathlib import Path


def test_change_selects_a_child_that_imports_its_parent_in_a_function(impact_project):
    """The documented split style imports the parent inside a function; editing the parent selects it."""
    from flowguard.map.common import DEFAULT_IGNORE
    from flowguard.map.inventory import build_inventory
    from _fg_helpers import map_write as write, map_impact_of as impact_of, map_git as git
    from flowguard.map.tree import build_tree
    root, data = impact_project
    write(root, ".flowguard/models/parent.py", 'MODEL_ID = "parent"\nCOMPONENTS = ["storage"]\nLIMIT = 1\n'
          'IMPLEMENTED_BY = {"save": "shop/storage.py:save"}\ndef build_explorer(): pass\ndef conformance(): pass\n')
    write(root, ".flowguard/models/child.py", 'MODEL_ID = "child"\nPARENT = "parent"\n'
          'def _starts():\n    import parent\n    return parent.LIMIT\n'
          'def build_explorer(): pass\ndef conformance(): pass\n')
    git(root, "add", "-A")
    git(root, "-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "parent and child")
    path = root / ".flowguard/models/parent.py"
    original = path.read_text(encoding="utf-8")
    path.write_text(original.replace("LIMIT = 1", "LIMIT = 2"), encoding="utf-8")
    impact = impact_of(root, data, [".flowguard/models/parent.py"], base="HEAD")
    assert {"parent", "child"} <= set(impact.model_ids) and not impact.blocked
    path.write_text(original + "# only a comment\n", encoding="utf-8")
    assert impact_of(root, data, [".flowguard/models/parent.py"], base="HEAD").model_ids == []
    tree = build_tree(root, data, build_inventory(root, DEFAULT_IGNORE))
    assert (tree.nodes["child"].parent, tree.nodes["child"].parent_kind) == ("parent", "model")
    assert tree.nodes["child"].local_import_files == {".flowguard/models/parent.py"}
    assert not [f for f in tree.findings if f.code == "parent_import_mismatch"]

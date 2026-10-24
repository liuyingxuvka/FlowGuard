"""Resolve actual model parents and reject independent malformed tree inputs.

The fixture is copied afresh for each singleton/pair.  Every observation comes
from build_tree over actual files, with explicit expected parent relations for
the three clean models; this is not a second implementation of tree resolution.
"""
import json
from pathlib import Path
import shutil
import tempfile

from flowguard.kit import Feature, feature_conformance, feature_explorer, feature_variants
from flowguard.map.inventory import build_inventory
from flowguard.map.tree import build_tree

MODEL_ID = "tree_resolution"
PARENT = "map-file"
IMPLEMENTED_BY = {"BuildTree": "flowguard/map/tree.py:build_tree"}
TESTED_BY = {
    "clean_input_accepted": [
        "tests/test_flowguard_map_contracts.py:test_model_tree_anchor_components_and_root_defaults",
    ],
    "each_defect_rejected": [
        "tests/test_flowguard_map_contracts.py:test_model_tree_parent_defaults_and_nesting_warnings",
        "tests/test_flowguard_map_contracts.py:test_old_mesh_mistakes_are_tree_errors",
    ],
    "every_defect_reported": [
        "tests/test_flowguard_map_contracts.py:test_model_tree_parent_defaults_and_nesting_warnings",
    ],
    "benign_features_neutral": [
        "tests/test_flowguard_map_contracts.py:test_child_import_of_its_explicit_parent_preserves_tree_and_impact",
    ],
}

MAP = {
    "schema": "flowguard.map.v1", "components": [
        {"id": "app", "summary": "Application operations", "responsibilities": ["perform application operations"],
         "files": ["app.py"], "entrypoints": ["app.py:root"], "state": [], "side_effects": [],
         "tests": [], "models": [], "depends_on": [], "status": "draft"},
    ],
}


def _model(mid, symbol, parent=None, imports=()):
    source = (f"MODEL_ID = {mid!r}\nCOMPONENTS = ['app']\n"
              f"IMPLEMENTED_BY = {{'Operation': {symbol!r}}}\n"
              "def build_explorer():\n"
              "    from flowguard.explorer import Explorer\n"
              "    from flowguard.workflow import Workflow\n"
              "    return Explorer(Workflow(()), (0,), (1,), progress_steps=0)\n")
    if parent is not None:
        source += f"PARENT = {parent!r}\n"
    return source + "".join(f"import {name}\n" for name in imports)


def _base_files():
    return {
        "app.py": "\n".join(f"def {name}(): return True" for name in
                            ("root", "explicit", "inferred", "mismatch", "cycle_a", "cycle_b")) + "\n",
        "outside.py": "def outside(): return True\n",
        ".flowguard/models/parent.py": _model("parent", "app.py:root", imports=("inferred_child",)),
        ".flowguard/models/explicit_child.py": _model("explicit_child", "app.py:explicit", "parent"),
        ".flowguard/models/inferred_child.py": _model("inferred_child", "app.py:inferred"),
    }


def _mismatch(files):
    changed = {**files, ".flowguard/models/m_mismatch.py": _model("m_mismatch", "app.py:mismatch", "app")}
    changed[".flowguard/models/parent.py"] += "import m_mismatch\n"
    return changed


def _unknown(files):
    return {**files, ".flowguard/models/u_unknown.py": _model("u_unknown", "app.py:inferred", "absent")}


def _cycle(files):
    return {**files, ".flowguard/models/cycle_a.py": _model("cycle_a", "app.py:cycle_a", "cycle_b"),
            ".flowguard/models/cycle_b.py": _model("cycle_b", "app.py:cycle_b", "cycle_a")}


def _outside(files):
    return {**files, ".flowguard/models/o_outside.py": _model("o_outside", "outside.py:outside", "parent")}


def _duplicate(files):
    return {**files, ".flowguard/models/d_duplicate.py": _model("d_duplicate", "app.py:explicit", "parent")}


def _explicit_inferred_parent(files):
    changed = dict(files)
    changed[".flowguard/models/inferred_child.py"] += "PARENT = 'parent'\n"
    return changed


# Independent fault fixtures preserve all actual native finding codes.
# The tree does not promise a priority order among its reported defects.
FEATURES = (
    Feature("import_parent_mismatch", True, ("parent_import_mismatch",), _mismatch),
    Feature("unknown_parent", True, ("parent_unknown",), _unknown),
    Feature("cyclic_parent", True, ("parent_cycle",), _cycle),
    Feature("outside_parent_code", True, ("child_outside_parent",), _outside),
    Feature("duplicate_child_anchor", True, ("duplicate_child_owner",), _duplicate),
    Feature("explicit_inferred_parent", False, (), _explicit_inferred_parent),
)


def build_explorer():
    return feature_explorer(FEATURES)


def broken_variants():
    return feature_variants(FEATURES)


def _write(root, relative, source):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _review(template, files):
    with tempfile.TemporaryDirectory(prefix="flowguard-tree-case-") as directory:
        root = Path(directory) / "project"
        shutil.copytree(template, root)
        for relative, source in files.items():
            _write(root, relative, source)
        inventory = build_inventory(root, [], with_bodies=False, write_cache=False)
        actual = build_tree(root, MAP, inventory)
        expected = {"parent": ("app", "component"), "explicit_child": ("parent", "model"),
                    "inferred_child": ("parent", "model")}
        observed = {mid: (actual.nodes[mid].parent, actual.nodes[mid].parent_kind)
                    for mid in expected if mid in actual.nodes}
        if observed != expected:
            raise RuntimeError(f"native parent relations changed: {observed!r}")
        for finding in actual.findings:
            if finding.level != "error":
                raise RuntimeError(f"unexpected native tree warning: {finding.code}: {finding.message}")
        return not actual.findings, tuple(finding.code for finding in actual.findings)


def conformance():
    with tempfile.TemporaryDirectory(prefix="flowguard-tree-template-") as directory:
        template = Path(directory)
        for relative, source in _base_files().items():
            _write(template, relative, source)
        _write(template, ".flowguard/map.json", json.dumps(MAP))
        return feature_conformance(FEATURES, _base_files, lambda files: _review(template, files))

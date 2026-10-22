"""Contract-model template built from the existing review kit."""

MODEL_MESH_MODEL_TEMPLATE = '''"""Review a parent model's split using its real child declarations.
Only real cross-child handoffs require MeshClosureModel; add that boundary when present.
Fill PARENT, CHILD_FILES and code/test anchors before running map models model_mesh.
To rerun this review with its parent, import the parent module at top level and set PARENT
to its MODEL_ID. Never import the child models; their declarations are read statically.
"""
from dataclasses import replace
from pathlib import Path
from flowguard import (HierarchyCoverageItem, HierarchyPartitionMap, ModelTargetSplitDerivation,
                       review_hierarchical_mesh)
from flowguard.hierarchy import child_evidence_from_model
from flowguard.kit import plan_explorer
from flowguard.map.facts import CodeFacts
from flowguard.map.mapfile import model_registry

MODEL_ID = "model_mesh"
PARENT = "REPLACE_ME"
CHILD_FILES = [".flowguard/models/REPLACE_ME.py", ".flowguard/models/REPLACE_ME_other.py"]
IMPLEMENTED_BY = {"Child": "REPLACE_ME/module.py:Owner"}
TESTED_BY = {"mesh_review_accepts": ["REPLACE_ME/test_x.py:test_name"]}
ROOT = Path(__file__).resolve().parents[2]


def plan():
    # Validate current code before reading the user-supplied child paths.
    facts = CodeFacts(ROOT)
    facts.anchors_exist(IMPLEMENTED_BY)
    if not facts.report().ok:
        raise ValueError(facts.report().format_text())
    children = tuple(child_evidence_from_model(path, root=ROOT) for path in CHILD_FILES)
    coverage = tuple(HierarchyCoverageItem(anchor, owner_model_id=child.model_id)
                     for child in children for anchor in child.functions_owned)
    parent_file = next((entry.path for entry in model_registry(ROOT).entries
                        if entry.kind == "contract" and entry.id == PARENT), "")
    return HierarchyPartitionMap(PARENT, child_models=children, coverage_items=coverage,
        target_split_derivation=ModelTargetSplitDerivation(PARENT,
            source_model_path=parent_file, target_child_model_ids=tuple(child.model_id for child in children),
            covered_partition_item_ids=tuple(item.item_id for item in coverage),
            state_owner_fields=tuple(sorted({field for child in children for field in child.state_owned})),
            side_effect_owner_fields=tuple(sorted({effect for child in children for effect in child.side_effects_owned})),
            rationale="Partition the parent's anchored code into the declared child owners."))


def duplicate_owner(value):
    return replace(value, coverage_items=value.coverage_items +
        (replace(value.coverage_items[0], owner_model_id=value.child_models[1].model_id),))


def misspelled_child(value):
    return replace(value, child_models=(replace(value.child_models[0], model_id=value.child_models[0].model_id + "x"),)
                   + value.child_models[1:])


EDITS = {"keep_declared_partition": lambda value: value, "duplicate_owner": duplicate_owner,
         "misspelled_child": misspelled_child}


def build_explorer():
    return plan_explorer(plan, EDITS, lambda value: review_hierarchical_mesh(value, root=ROOT),
                         explore=["keep_declared_partition"], invariant_name="mesh_review_accepts")


def broken_variants():
    return {name: plan_explorer(plan, EDITS, lambda value: review_hierarchical_mesh(value, root=ROOT),
                               explore=[name], invariant_name="mesh_review_accepts")
            for name in ("duplicate_owner", "misspelled_child")}


def conformance():
    facts = CodeFacts(ROOT)
    facts.anchors_exist(IMPLEMENTED_BY)
    for path in CHILD_FILES:
        facts.check(f"child file {path} exists", (ROOT / path).is_file(), "child model file does not exist")
        child = child_evidence_from_model(path, root=ROOT)
        facts.check(f"{child.model_id}: parent is {PARENT}", child.parent_model_id == PARENT, "tree parent differs")
        facts.anchors_exist(child.functions_owned)
    return facts.report()
'''

__all__ = ["MODEL_MESH_MODEL_TEMPLATE"]

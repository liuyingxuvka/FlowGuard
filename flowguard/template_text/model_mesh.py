"""Public target scaffold for the ModelMesh route."""

from __future__ import annotations

MODEL_MESH_MODEL_TEMPLATE = '''"""FlowGuard model

Purpose: Review parent/child topology and evidence reattachment with one owner per child.
Guards against: missing partitions, overlapping siblings, stale child evidence, and parent receipts impersonating children.
Use before editing: Update this ModelMesh when models are split, reattached, retried, or partially activated.
Run: python -m flowguard map models model_mesh
This scaffold is a target-owned topology declaration.  Model count alone is
not a mesh: fill parent/child ownership, reattachment, and current receipts.
"""

from __future__ import annotations

from dataclasses import replace
from flowguard import (ChildModelEvidence, HierarchyCoverageItem, HierarchyPartitionMap,
                       ModelTargetSplitDerivation, review_hierarchical_mesh)


def target_mesh() -> HierarchyPartitionMap:
    # Abstract sample evidence, not a current target execution receipt.
    return HierarchyPartitionMap(
        "target-parent-model",
        coverage_items=(HierarchyCoverageItem("parse-request", owner_model_id="request-child"),),
        child_models=(ChildModelEvidence("request-child", parent_model_id="target-parent-model",
                                        owner_id="request-owner", functions_owned=("parse-request",),
                                        functional_areas=("request",)),),
        target_split_derivation=ModelTargetSplitDerivation(
            "target-parent-model", target_child_model_ids=("request-child",),
            covered_partition_item_ids=("parse-request",),
            rationale="The existing parent function boundary determines this child."),
    )


def run_checks():
    mesh = target_mesh()
    good = review_hierarchical_mesh(mesh)
    bad = review_hierarchical_mesh(replace(mesh, coverage_items=(
        HierarchyCoverageItem("parse-request", owner_model_id="missing-child"),)))
    return good, bad
'''

MODEL_MESH_RUN_CHECKS_TEMPLATE = '''"""Run the ModelMesh scaffold checks."""

from model import run_checks


def main() -> int:
    good, bad = run_checks()
    print(good.format_text())
    print()
    print(bad.format_text(max_findings=5))
    print()
    return 0 if good.ok and not bad.ok else 1


# The real code this review is about: the placeholder fails until you name it ('path:Symbol').
# Add TESTED_BY = {"<check>": ["tests/test_x.py:test_name"]} for the tests that guard it.
IMPLEMENTED_BY = {"Owner": "REPLACE_ME/module.py:Owner"}


def bound_main() -> int:
    """Run the review, then check that IMPLEMENTED_BY names real code."""
    from pathlib import Path

    from flowguard.map.facts import CodeFacts

    code = main() or 0
    facts = CodeFacts(Path(__file__).resolve().parents[4])
    facts.anchors_exist(IMPLEMENTED_BY)
    print(facts.report().format_text())
    return code if facts.report().ok else 1


if __name__ == "__main__":
    from flowguard.map.runner import run_owner
    raise SystemExit(run_owner(bound_main))
'''

MODEL_MESH_NOTES_TEMPLATE = """# FlowGuard ModelMesh Notes

Use this route when a model is oversized, partitioned, reattached, or has
parent/child evidence that needs independent ownership.  Fill the target
parent partition, one owner per child, structural versus shared-kernel
relations, changed-child boundary, input/output/state/effect/guarantee
reattachment, joins, terminals, loops, retries, partial activation, and
stale/not-run child evidence.  Three models by itself is not a trigger and a
parent receipt never proves a child.

The generated model is a scaffold only.  The target author must replace the
example IDs with current target identities and run the existing hierarchy
review. Add ChildReattachmentContract and a closure model when the child has
outputs/state/effects consumed by the parent; consume the current child evidence
ID and explicitly compare the expected boundary after a change. This template
does not copy or replace the ModelMesh engine.
"""

__all__ = [
    "MODEL_MESH_MODEL_TEMPLATE",
    "MODEL_MESH_RUN_CHECKS_TEMPLATE",
    "MODEL_MESH_NOTES_TEMPLATE",
]

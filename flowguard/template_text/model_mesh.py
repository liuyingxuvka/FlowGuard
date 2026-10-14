"""Public target scaffold for the ModelMesh route."""

from __future__ import annotations

MODEL_MESH_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Review parent/child topology and evidence reattachment with one owner per child.
Guards against: missing partitions, overlapping siblings, stale child evidence, and parent receipts impersonating children.
Use before editing: Update this ModelMesh when models are split, reattached, retried, or partially activated.
Run: python .flowguard/verification/owners/model_mesh/run_checks.py
This scaffold is a target-owned topology declaration.  Model count alone is
not a mesh: fill parent/child ownership, reattachment, and current receipts.
"""

from __future__ import annotations

from flowguard import (
    ChildModelEvidence,
    MeshClosureJoin,
    MeshClosureModel,
    MeshClosureTerminal,
    MeshClosureTransition,
    review_mesh_closure_model,
)


REQUIRED_NEGATIVE_CASES = (
    ("missing_partition", "mesh_missing_parent_partition"),
    ("overlapping_siblings", "mesh_overlapping_siblings"),
    ("two_structural_parents", "mesh_multiple_structural_parents"),
    ("changed_child_without_reattachment", "mesh_changed_child_unreattached"),
    ("stale_child_receipt", "mesh_stale_child_evidence"),
    ("parent_receipt_as_child", "mesh_parent_receipt_used_for_child"),
    ("partial_activation", "mesh_partial_activation_unclosed"),
    ("count_only_false_friend", "mesh_count_only_not_topology"),
)


def negative_case_matrix() -> tuple[tuple[str, str], ...]:
    """Target-owned negative cases that must be replaced with live fixtures."""

    return REQUIRED_NEGATIVE_CASES


def target_mesh() -> MeshClosureModel:
    return MeshClosureModel(
        "target-parent-model",
        root_entries=("parent:start",),
        transitions=(
            MeshClosureTransition(
                "parent-to-child",
                consumes=("parent:start",),
                emits=("child:result",),
                consumer_model_id="target-child-model",
                progress_rule="child emits a terminal result or an explicit blocker",
            ),
        ),
        joins=(
            MeshClosureJoin(
                "parent-join",
                required_inputs=("child:result",),
                emits=("parent:joined",),
            ),
        ),
        terminals=(MeshClosureTerminal("normal-exit", consumes=("parent:joined",)),),
        required_outputs=("child:result",),
        rationale="The target author owns the partition and every reattachment decision.",
    )


def child_models() -> tuple[ChildModelEvidence, ...]:
    return (
        ChildModelEvidence(
            "target-child-model",
            evidence_id="receipt:target-child-current",
            outputs_emitted=("child:result",),
            evidence_current=True,
            functions_owned=("target_child_entry",),
            validation_evidence=("test:target-child-positive", "test:target-child-known-bad"),
        ),
    )


def run_checks():
    good = review_mesh_closure_model(target_mesh(), child_models())
    bad = review_mesh_closure_model(MeshClosureModel("missing-partition"), ())
    case_ids = tuple(case_id for case_id, _error in negative_case_matrix())
    case_review = len(case_ids) == len(set(case_ids)) and all(error for _case, error in negative_case_matrix())
    return good, bad, case_review
'''

MODEL_MESH_RUN_CHECKS_TEMPLATE = '''"""Run the ModelMesh scaffold checks."""

from model import run_checks


def main() -> int:
    good, bad, case_review = run_checks()
    print(good.format_text())
    print()
    print(bad.format_text(max_findings=5))
    print()
    print("model-mesh negative-case matrix: " + ("PASS" if case_review else "BLOCKED"))
    return 0 if good.ok and not bad.ok and case_review else 1


if __name__ == "__main__":
    from flowguard.map.runner import run_owner
    raise SystemExit(run_owner(main))
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
review; this template does not copy or replace the ModelMesh engine.
"""

__all__ = [
    "MODEL_MESH_MODEL_TEMPLATE",
    "MODEL_MESH_RUN_CHECKS_TEMPLATE",
    "MODEL_MESH_NOTES_TEMPLATE",
    "REQUIRED_NEGATIVE_CASES",
    "negative_case_matrix",
]

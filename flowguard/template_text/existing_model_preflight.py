"""Template text for FlowGuard existing model preflight route."""

from __future__ import annotations

EXISTING_MODEL_PREFLIGHT_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Review whether an agent grounded an existing-system change in the FlowGuard models that already exist.
Guards against: proposing new modules, rules, workflows, or ownership boundaries before checking existing FunctionBlocks, state owners, side-effect owners, public entrypoints, and model responsibilities.
Use before editing: Run this before implementation, OpenSpec proposals, major architecture changes, or risky behavior changes in an existing modeled system.
Run: python .flowguard/existing_model_preflight/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    DuplicateBoundaryRisk,
    ExistingModelPreflight,
    ExistingOwnershipSnapshot,
    ModelContextHit,
    REUSE_DECISION_ADD_CHILD_MODEL,
    REUSE_DECISION_EXTEND_EXISTING,
    review_existing_model_preflight,
)


def correct_preflight():
    return ExistingModelPreflight(
        "router-existing-model-preflight",
        "Extend router scheduling behavior",
        mode="full",
        model_search_performed=True,
        search_paths=(".flowguard/router", "docs"),
        relevant_models=(
            ModelContextHit(
                "router-flow",
                model_path=".flowguard/router/model.py",
                evidence_id="router:v1",
                evidence_tier="abstract_green",
                responsibilities=("route scheduling",),
                function_blocks=("RouteTask",),
                state_owned=("pending_tasks",),
                side_effects_owned=("dispatch_task",),
                public_entrypoints=("router.dispatch",),
                validation_evidence=("router scenario replay",),
            ),
        ),
        ownership_snapshot=ExistingOwnershipSnapshot(
            function_block_owners=(("RouteTask", "router-flow"),),
            state_owners=(("pending_tasks", "router-flow"),),
            side_effect_owners=(("dispatch_task", "router-flow"),),
            public_entrypoint_owners=(("router.dispatch", "router-flow"),),
        ),
        reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
        downstream_routes=("development_process_flow",),
        rationale="The existing router model owns task dispatch, so extend that boundary instead of creating a parallel scheduler.",
    )


def broken_duplicate_preflight():
    return ExistingModelPreflight(
        "broken-parallel-scheduler",
        "Create a parallel scheduler",
        mode="full",
        model_search_performed=True,
        search_paths=(".flowguard/router",),
        relevant_models=(correct_preflight().relevant_models[0],),
        ownership_snapshot=ExistingOwnershipSnapshot(
            state_owners=(("pending_tasks", "router-flow"),),
        ),
        reuse_decision=REUSE_DECISION_ADD_CHILD_MODEL,
        downstream_routes=("model_mesh_maintenance",),
        proposed_new_boundaries=("parallel-scheduler",),
        rationale="A new child was proposed, but the duplicate state risk is unresolved.",
        duplicate_risks=(
            DuplicateBoundaryRisk(
                "state",
                "pending_tasks",
                "router-flow",
                proposed_owner_id="parallel-scheduler",
            ),
        ),
    )


def run_checks():
    return (
        review_existing_model_preflight(correct_preflight()),
        review_existing_model_preflight(broken_duplicate_preflight()),
    )
'''

EXISTING_MODEL_PREFLIGHT_RUN_CHECKS_TEMPLATE = '''"""Run the existing-model preflight template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    correct, broken = run_checks()
    print(correct.format_text())
    print()
    print(broken.format_text(max_findings=5))
    return 0 if correct.ok and not broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

EXISTING_MODEL_PREFLIGHT_NOTES_TEMPLATE = """# FlowGuard Existing Model Preflight Notes

Use this scaffold before discussing, proposing, or implementing a non-trivial
change in an existing modeled system.

## What Existing Model Preflight Reviews

- which existing FlowGuard models were searched;
- which model responsibilities, FunctionBlocks, state fields, side effects,
  and public entrypoints already own the requested behavior;
- whether the change should reuse an existing boundary, extend an existing
  model, add a child model, or create a new boundary;
- whether duplicate model, state, side-effect, entrypoint, or responsibility
  ownership is resolved before downstream work starts;
- which downstream FlowGuard route should handle the concrete work.

Use a light grounding note for discussion and early analysis. Use a full
structured preflight before implementation, OpenSpec proposals, major
architecture changes, or risky behavior changes.

Use `existing_model_preflight_from_project(...)` when an agent needs a quick
project inventory from `.flowguard`, docs, and OpenSpec before filling or
reviewing the same `ExistingModelPreflight` shape. The inventory helper is not
the validator; pass its output to `review_existing_model_preflight(...)`.
"""

__all__ = [
    'EXISTING_MODEL_PREFLIGHT_MODEL_TEMPLATE',
    'EXISTING_MODEL_PREFLIGHT_RUN_CHECKS_TEMPLATE',
    'EXISTING_MODEL_PREFLIGHT_NOTES_TEMPLATE',
]

"""Template text for FlowGuard code structure recommendation route."""

from __future__ import annotations

CODE_STRUCTURE_RECOMMENDATION_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Recommend an implementation structure from a FlowGuard functional model before production code is written.
Guards against: monolithic implementation plans, unclear state ownership, mixed side effects, missing facades, and test boundaries that do not map back to the model.
Architecture direction: compare only authenticated related contexts, retain hard semantic differences and partial remainders, and point to required goals not satisfied by actual observed behavior.
Use before editing: Ask for this recommendation when a model-first feature needs a code architecture plan before implementation.
Run: python .flowguard/verification/owners/code_structure_recommendation/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    CodeStructureRecommendation,
    TargetModuleRecommendation,
    review_code_structure_recommendation,
)


def recommendation() -> CodeStructureRecommendation:
    return CodeStructureRecommendation(
        "checkout-target-structure",
        source_model_id="checkout-functional-model",
        source_model_path=".flowguard/models/owners/checkout/model.py",
        parent_module_id="checkout",
        target_modules=(
            TargetModuleRecommendation(
                "orchestrator",
                path="checkout/orchestrator.py",
                owns_function_blocks=("RouteCheckout",),
                reads_fields=("field:checkout_mode",),
                validation_boundaries=("route scenario test",),
                rationale="The orchestrator owns ordering only and does not own durable state.",
            ),
            TargetModuleRecommendation(
                "state",
                path="checkout/state.py",
                owns_state=("orders", "attempts"),
                owns_fields=("field:checkout_mode", "field:old_mode"),
                validation_boundaries=("state shape test",),
                rationale="State and type definitions stay separate from transition logic.",
            ),
            TargetModuleRecommendation(
                "effects",
                path="checkout/effects.py",
                owns_function_blocks=("PersistOrder",),
                owns_side_effects=("write_order",),
                writes_fields=("field:checkout_mode",),
                validation_boundaries=("effect idempotency replay",),
                rationale="Durable writes are isolated behind an adapter boundary.",
            ),
        ),
        function_block_map=(
            ("RouteCheckout", "orchestrator"),
            ("PersistOrder", "effects"),
        ),
        state_owner_map=(("orders", "state"), ("attempts", "state")),
        field_owner_map=(("field:checkout_mode", "state"), ("field:old_mode", "state")),
        field_reader_map=(("field:checkout_mode", "orchestrator"),),
        field_writer_map=(("field:checkout_mode", "effects"),),
        side_effect_owner_map=(("write_order", "effects"),),
        validation_boundaries=("route scenario test", "state shape test", "effect idempotency replay"),
        rationale="The functional model separates ordering, abstract state, and durable side effects.",
    )


def broken_recommendation() -> CodeStructureRecommendation:
    return CodeStructureRecommendation(
        "checkout-broken-structure",
        source_model_id="",
        parent_module_id="checkout",
        target_modules=(TargetModuleRecommendation("checkout"),),
        function_block_map=(),
    )


def run_checks():
    return (
        review_code_structure_recommendation(recommendation()),
        review_code_structure_recommendation(broken_recommendation()),
    )
'''

CODE_STRUCTURE_RECOMMENDATION_RUN_CHECKS_TEMPLATE = '''"""Run the Code Structure Recommendation template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    recommendation, broken = run_checks()
    print(recommendation.format_text())
    print()
    print(broken.format_text(max_findings=5))
    return 0 if recommendation.ok and not broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

CODE_STRUCTURE_RECOMMENDATION_NOTES_TEMPLATE = """# FlowGuard Code Structure Recommendation Notes

Use this scaffold when a user or agent wants a recommended code architecture
before writing production code.

## What This Route Produces

- the FlowGuard functional model used as source evidence;
- recommended target modules and paths;
- FunctionBlock-to-module ownership;
- state, config, and side-effect owner maps;
- field owner/reader/writer maps from FieldLifecycleMesh projections;
- public entrypoint or facade plans when relevant;
- validation boundaries that keep the recommendation tied to executable model
  evidence.

This route recommends structure. It does not write production code and does not
replace StructureMesh. StructureMesh uses model-derived target structure when an
existing large script or module is being split.

By default the result is recommendation-only. Set
`implementation_ready_requested=True` only when attaching the exact current
`ImplementationAdmissionReport`; every target module id or path must remain
inside that admission's allowed scope.

First bind complete declared affected structure, honest graph scope and
independent semantic/context evidence. Traces supply coverage only; scoped
declarations do not establish whole-software confidence. Read goals from exact
verified normative source bytes and admitted target ids; no goal creates no
default centralization requirement. Preserve actual observed owners, rare
not_run branches, disjoint legitimate variants and hard-semantic differences.

Consume ModelMaturation's authenticated finite directions rather than
performing another optimization. A shared target requires one real canonical
primary plus exact current consumer delegation, not equal hashes on copies.
Record observed identity, goal/element ids, candidate lane, hard differences,
retained obligations, rewrites and exact native contract/binding/result/receipt
refs. Consume matching accepted architecture.improvement_pointers; never infer
native selectors or oracles from names. Partial context overlap permits only
that overlap's candidate; retain each variant's remaining contexts. A temporary
compromise requires current source, reason, context, impact and revisit trigger.
It cannot waive a required goal; only current source supersession/refinement
can change the requirement. Missing proof returns an exact input/next-owner ref.

No ordinary task creates a default cost goal. Explicit cost_bound without
independent measurement admission stays cost_measurement_missing; a scalar,
semantic review or self-declared PathCostVector cannot satisfy it. Existing
explicit finite path comparison is separate. Accepted observation never closes
an unmet required improvement objective. No unrestricted optimum, implemented
improvement or speed gain is implied.

Return the requested function, accepted head/revision/as-of, actual dependency
and required-goal scope, finding/pointer refs and first missing input/owner.
Default to compact output with addressable details; preserve every required
ref rather than hiding evidence to save bytes. Structure recommendations are
not completion proof: only current verified maturation plus all required
outcome/native evidence permits MODEL_MATURATION_DECISION_CLOSED_FOR_TASK
(model_maturation_closed_for_task) in both decision and terminal reason.
Missing external input, scope_excluded and iteration_limit remain non-success.
Public read without typed task context reports only its accepted map.

Three task-neutral examples:
- Export-format change: map format, actual callers and compatibility contracts
  only; unrelated modules are not implied obligations.
- Shared-cache change: include all actual writers, invalidation and retry
  boundaries before recommending shared ownership.
- Explicit whole-architecture review: consume independently complete inventory
  and reverse bindings; selected declarations are not whole-source proof.

For field-heavy changes, every reader and writer should point to exactly one
field owner. Old or replacement fields should stay visible here until
FieldLifecycleMesh and Architecture Reduction have closed their disposition.
"""

__all__ = [
    'CODE_STRUCTURE_RECOMMENDATION_MODEL_TEMPLATE',
    'CODE_STRUCTURE_RECOMMENDATION_RUN_CHECKS_TEMPLATE',
    'CODE_STRUCTURE_RECOMMENDATION_NOTES_TEMPLATE',
]

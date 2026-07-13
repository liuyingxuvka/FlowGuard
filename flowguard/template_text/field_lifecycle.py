"""Template text for FlowGuard FieldLifecycleMesh route."""

from __future__ import annotations

FIELD_LIFECYCLE_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Review field lifecycle coverage, behavior-bearing field projections, and old-field disposition before model-code-test or closure claims.
Guards against: behavior-changing fields omitted from models, display fields mistaken for behavior proof, old fields surviving replacement work by accident, and field rows that do not project into owner model/code/test routes.
Use before editing: Run this when a change adds, removes, renames, migrates, externalizes, or replaces fields, schema keys, config flags, prompts, or public payload columns.
Run: python .flowguard/field_lifecycle/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    FIELD_DISPOSITION_BLOCKED,
    FIELD_IMPACT_ROUTING,
    FIELD_LIFECYCLE_REPLACED,
    FIELD_ROLE_METADATA,
    FIELD_ROLE_PRESENTATION,
    FIELD_ROLE_ROUTING,
    TEST_KIND_FAILURE_PATH,
    TEST_KIND_HAPPY_PATH,
    TEST_KIND_NEGATIVE_PATH,
    TEST_KIND_REPLAY,
    FieldLifecycleGroup,
    FieldLifecyclePlan,
    FieldLifecycleRow,
    FieldProjection,
    field_lifecycle_to_code_contracts,
    field_lifecycle_to_model_obligations,
    review_field_lifecycle,
)


def route_projection(field_id: str, obligation_id: str, contract_id: str) -> FieldProjection:
    return FieldProjection(
        f"projection:{field_id}",
        field_id,
        model_obligation_id=obligation_id,
        code_contract_id=contract_id,
        external_inputs=("checkout_mode",),
        external_outputs=("route selected",),
        state_reads=("checkout_mode",),
        state_writes=("checkout_mode",),
        required_test_kinds=(
            TEST_KIND_HAPPY_PATH,
            TEST_KIND_FAILURE_PATH,
            TEST_KIND_NEGATIVE_PATH,
            TEST_KIND_REPLAY,
        ),
        evidence_refs=(
            "gate:checkout-mode-boundary",
            "test:missing-checkout-mode-rejected",
            "replay:checkout-mode-runtime-path",
        ),
        rationale="checkout_mode controls routing, so broad claims need a model obligation, owner code contract, gate ref, negative test ref, and replay ref",
    )


def complete_field_lifecycle() -> FieldLifecyclePlan:
    return FieldLifecyclePlan(
        "checkout-field-lifecycle",
        discovered_field_ids=("field:checkout_mode", "field:label", "field:old_mode"),
        claim_scope="full",
        groups=(
            FieldLifecycleGroup(
                "checkout-payload",
                boundary_kind="api_payload",
                field_ids=("field:checkout_mode", "field:label", "field:old_mode"),
                child_group_ids=("checkout-payload:leaf",),
                owner_route="field_lifecycle_mesh",
                rationale="Parent group keeps the payload readable while the leaf row accounts every field.",
            ),
            FieldLifecycleGroup(
                "checkout-payload:leaf",
                boundary_kind="leaf_fields",
                parent_group_id="checkout-payload",
                field_ids=("field:checkout_mode", "field:label", "field:old_mode"),
                owner_route="field_lifecycle_mesh",
            ),
        ),
        fields=(
            FieldLifecycleRow(
                "field:checkout_mode",
                role=FIELD_ROLE_ROUTING,
                lifecycle="active",
                group_id="checkout-payload:leaf",
                behavior_impacts=(FIELD_IMPACT_ROUTING,),
                reader_ids=("checkout.router",),
                writer_ids=("checkout.api",),
                projection=route_projection(
                    "field:checkout_mode",
                    "obligation:checkout_mode_routes_order",
                    "contract:checkout_mode_router",
                ),
            ),
            FieldLifecycleRow(
                "field:label",
                role=FIELD_ROLE_PRESENTATION,
                lifecycle="active",
                group_id="checkout-payload:leaf",
                scoped_out_reason="display-only label, no routing/state/side-effect branch",
            ),
            FieldLifecycleRow(
                "field:old_mode",
                role=FIELD_ROLE_ROUTING,
                lifecycle=FIELD_LIFECYCLE_REPLACED,
                group_id="checkout-payload:leaf",
                behavior_impacts=(FIELD_IMPACT_ROUTING,),
                replacement_field_id="field:checkout_mode",
                disposition=FIELD_DISPOSITION_BLOCKED,
                disposition_evidence_refs=("test_old_mode_is_rejected",),
                projection=route_projection(
                    "field:old_mode",
                    "obligation:old_mode_is_rejected",
                    "contract:old_mode_rejection",
                ),
            ),
        ),
        notes="Default replacement policy: old skill/runtime fields are deleted, blocked, delegated, repaired, or directly replaced. Historical readers exist only for explicit ordinary-software requirements with one bounded owner.",
    )


def broken_field_lifecycle() -> FieldLifecyclePlan:
    return FieldLifecyclePlan(
        "checkout-field-lifecycle-broken",
        discovered_field_ids=("field:checkout_mode", "field:label", "field:old_mode"),
        claim_scope="full",
        groups=(
            FieldLifecycleGroup(
                "checkout-payload",
                boundary_kind="api_payload",
                field_ids=("field:checkout_mode", "field:old_mode"),
            ),
        ),
        fields=(
            FieldLifecycleRow(
                "field:checkout_mode",
                role=FIELD_ROLE_ROUTING,
                behavior_impacts=(FIELD_IMPACT_ROUTING,),
                reader_ids=("checkout.router",),
                writer_ids=("checkout.api",),
            ),
            FieldLifecycleRow(
                "field:old_mode",
                role=FIELD_ROLE_METADATA,
                lifecycle=FIELD_LIFECYCLE_REPLACED,
                replacement_field_id="field:checkout_mode",
            ),
        ),
        notes="Broken on purpose: label is missing, checkout_mode has no projection, and old_mode has no closing disposition.",
    )


def run_checks():
    correct = review_field_lifecycle(complete_field_lifecycle())
    broken = review_field_lifecycle(broken_field_lifecycle())
    return (
        correct,
        broken,
        field_lifecycle_to_model_obligations(correct),
        field_lifecycle_to_code_contracts(correct),
    )
'''

FIELD_LIFECYCLE_RUN_CHECKS_TEMPLATE = '''"""Run the FieldLifecycleMesh template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    correct, broken, obligations, code_contracts = run_checks()
    print(correct.format_text())
    print(f"projected_model_obligations: {len(obligations)}")
    print(f"projected_code_contracts: {len(code_contracts)}")
    print()
    print(broken.format_text())
    return 0 if correct.ok and not broken.ok and obligations and code_contracts else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

FIELD_LIFECYCLE_NOTES_TEMPLATE = """# FlowGuard FieldLifecycleMesh Notes

Use this scaffold when a change touches fields, schema keys, config flags,
prompt/config fields, payload columns, persisted attributes, or replacement keys.

## What This Route Owns

- Parent groups keep the field model readable, such as entity, payload, schema,
  config, public entrypoint, prompt/config surface, or persisted record.
- Leaf rows account every discovered field in scope.
- Behavior-bearing fields project into model obligations and owner code
  contracts so Model-Test Alignment can demand real test evidence.
- Broad behavior-bearing field claims keep a minimal route trail in
  `FieldProjection.evidence_refs`: use `gate:` for the runtime or boundary
  gate, `test:` for the negative or failure-path proof, and `replay:` for
  representative runtime or conformance replay evidence.
- Non-behavior fields stay accounted with a scoped-out reason instead of
  silently disappearing.
- Old, replaced, deprecated, alias, fallback, or compatibility fields need a
  closing disposition.

## Default Replacement Policy

For skill/runtime work, the default is one current path. Old fields are
deleted, blocked, delegated to the current field, repaired, or directly
replaced; they are not read by a migration or compatibility path. For ordinary
software only, a historical reader is allowed when an explicit requirement
names the historical input and one bounded reader owner, with current evidence.

## Handoffs

FieldLifecycleMesh does not replace the routes that prove behavior. Send field
projections to Model-Test Alignment, field reader/writer/owner maps to Code
Structure Recommendation, old-field disposition to Legacy Path Disposition and
Architecture Reduction, bug root-cause fields to Model-Miss Review, and changed
field artifacts to DevelopmentProcessFlow and Closure Contract.

Field route refs are handoff labels, not proof by themselves. Model-Test
Alignment, Runtime Gateway Adoption, replay, and Closure Contract still own the
current passing evidence.
"""

__all__ = [
    'FIELD_LIFECYCLE_MODEL_TEMPLATE',
    'FIELD_LIFECYCLE_RUN_CHECKS_TEMPLATE',
    'FIELD_LIFECYCLE_NOTES_TEMPLATE',
]

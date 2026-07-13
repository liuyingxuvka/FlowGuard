"""Template text for FlowGuard model similarity consolidation route."""

from __future__ import annotations

MODEL_SIMILARITY_CONSOLIDATION_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Compare FlowGuard model signatures before creating parallel model or code boundaries.
Guards against: duplicate model ownership, forgotten sibling workflows, unsafe shared-kernel extraction, false-friend consolidation, adapter-only duplication, missing shared/variant tests, and similarity advice without current evidence.
Also compares business path ids, business intents, and path terminals so one useful business path is not accidentally modeled twice.
Use before editing: Run this before adding a model boundary, changing one member of a similar A/B/C workflow family, recommending code structure, or turning similar workflows into shared code.
Run: python .flowguard/model_similarity_consolidation/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    ModelSignature,
    ModelSimilarityEvidence,
    ModelSimilarityPlan,
    model_signature_maintenance,
    model_similarity_plan_for_changed_member,
    review_model_similarity_consolidation,
)


def correct_plan() -> ModelSimilarityPlan:
    signatures = (
        model_signature_maintenance(
            "checkout-simple",
            workflow_family="checkout",
            behavior_plane="product_runtime",
            variant_id="simple",
            function_blocks=("ValidateOrder", "PersistOrder"),
            state_owned=("orders",),
            side_effects_owned=("write_order",),
            code_paths=("flowguard/checkout/simple.py",),
            test_paths=("tests/test_checkout_simple.py",),
            owned_public_behaviors=("submit_order",),
            business_path_ids=("submit_order",),
            business_intents=("submit order",),
            business_intent_ids=("intent:submit-order",),
            behavior_commitment_ids=("commitment:submit-order",),
            primary_path_ids=("path:submit-order",),
            public_surface_ids=("surface:checkout-simple",),
            path_terminals=("accepted",),
            shared_kernel_id="checkout_core",
            adapter_ids=("simple_adapter",),
            maintenance_tags=("checkout", "order-write"),
            evidence_ids=("sim:checkout-family",),
        ),
        model_signature_maintenance(
            "checkout-retry",
            workflow_family="checkout",
            behavior_plane="product_runtime",
            variant_id="retry",
            function_blocks=("ValidateOrder", "PersistOrder"),
            state_owned=("orders",),
            side_effects_owned=("write_order",),
            code_paths=("flowguard/checkout/retry.py",),
            test_paths=("tests/test_checkout_retry.py",),
            owned_public_behaviors=("submit_order", "retry_order"),
            business_path_ids=("submit_order", "retry_order"),
            business_intents=("submit order", "retry order"),
            business_intent_ids=("intent:submit-order", "intent:retry-order"),
            behavior_commitment_ids=("commitment:submit-order", "commitment:retry-order"),
            primary_path_ids=("path:submit-order", "path:retry-order"),
            public_surface_ids=("surface:checkout-retry",),
            path_terminals=("accepted", "retry_scheduled"),
            shared_kernel_id="checkout_core",
            adapter_ids=("retry_adapter",),
            maintenance_tags=("checkout", "order-write"),
            evidence_ids=("sim:checkout-family",),
        ),
        model_signature_maintenance(
            "checkout-cancel",
            workflow_family="checkout",
            behavior_plane="product_runtime",
            variant_id="cancel",
            function_blocks=("ValidateOrder", "PersistOrder"),
            state_owned=("orders",),
            side_effects_owned=("write_order",),
            code_paths=("flowguard/checkout/cancel.py",),
            test_paths=("tests/test_checkout_cancel.py",),
            owned_public_behaviors=("cancel_order",),
            business_path_ids=("cancel_order",),
            business_intents=("cancel order",),
            business_intent_ids=("intent:cancel-order",),
            behavior_commitment_ids=("commitment:cancel-order",),
            primary_path_ids=("path:cancel-order",),
            public_surface_ids=("surface:checkout-cancel",),
            path_terminals=("cancelled",),
            shared_kernel_id="checkout_core",
            adapter_ids=("cancel_adapter",),
            maintenance_tags=("checkout", "order-write"),
            evidence_ids=("sim:checkout-family",),
        ),
    )
    return model_similarity_plan_for_changed_member(
        "checkout-model-similarity",
        signatures,
        changed_model_id="checkout-simple",
        evidence=(
            ModelSimilarityEvidence(
                "sim:checkout-family",
                summary="family review confirmed shared checkout kernel with retry and cancel adapters",
                compared_behavior_planes=("product_runtime",),
            ),
        ),
        expected_surface_ids=(
            "surface:checkout-simple",
            "surface:checkout-retry",
            "surface:checkout-cancel",
        ),
        surface_inventory_revision="checkout-surfaces:v1",
        require_complete_surface_inventory=True,
        require_stable_authority_identity=True,
        require_behavior_plane_identity=True,
        require_current_evidence=True,
        rationale="Use similarity review before changing one checkout variant or creating a parallel checkout workflow.",
    )


def broken_missing_evidence_plan() -> ModelSimilarityPlan:
    return ModelSimilarityPlan(
        "missing-evidence-similarity",
        signatures=(
            ModelSignature(
                "billing-simple",
                workflow_family="billing",
                variant_id="simple",
                function_blocks=("ValidateInvoice", "PersistInvoice"),
                state_owned=("invoices",),
                failure_modes=("duplicate_invoice",),
            ),
            ModelSignature(
                "billing-retry",
                workflow_family="billing",
                variant_id="retry",
                function_blocks=("ValidateInvoice", "PersistInvoice"),
                state_owned=("invoices",),
                failure_modes=("duplicate_invoice",),
            ),
        ),
        comparison_pairs=(("billing-simple", "billing-retry"),),
        require_current_evidence=True,
        rationale="This intentionally broken plan lacks current evidence for a consolidation recommendation.",
    )


def false_friend_plan() -> ModelSimilarityPlan:
    return ModelSimilarityPlan(
        "false-friend-similarity",
        signatures=(
            ModelSignature(
                "cache-refresh",
                function_blocks=("RefreshCache",),
                state_owned=("cache_entries",),
                side_effects_owned=("write_cache",),
                business_intents=("refresh cache",),
                path_terminals=("cache_fresh",),
                failure_modes=("stale_cache",),
                false_friend_model_ids=("cache-report",),
            ),
            ModelSignature(
                "cache-report",
                function_blocks=("RenderReport",),
                state_owned=("report_rows",),
                side_effects_owned=("write_report",),
                business_intents=("refresh cache",),
                path_terminals=("report_rendered",),
                failure_modes=("missing_report_row",),
            ),
        ),
        comparison_pairs=(("cache-refresh", "cache-report"),),
        rationale="Name overlap should not collapse distinct state and side-effect ownership.",
    )


def run_checks():
    return (
        review_model_similarity_consolidation(correct_plan()),
        review_model_similarity_consolidation(broken_missing_evidence_plan()),
        review_model_similarity_consolidation(false_friend_plan()),
    )
'''

MODEL_SIMILARITY_CONSOLIDATION_RUN_CHECKS_TEMPLATE = '''"""Run the model similarity consolidation template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    correct, missing_evidence, false_friend = run_checks()
    print(correct.format_text())
    print()
    print(missing_evidence.format_text(max_findings=5))
    print()
    print(false_friend.format_text(max_findings=5))
    return 0 if correct.ok and not missing_evidence.ok and false_friend.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

MODEL_SIMILARITY_CONSOLIDATION_NOTES_TEMPLATE = """# FlowGuard Model Similarity Consolidation Notes

Use this scaffold before adding a new model boundary, extracting shared code,
or treating several model-backed features as one workflow family.

## Basic Path

Use `model_signature_maintenance()` and
`model_similarity_plan_for_changed_member()` for ordinary A/B/C maintenance.
Then pass the `SimilarityHandoff` from `report.to_handoff()` to downstream
routes instead of copying relation ids, group ids, test obligation ids, and code
obligation ids into separate fields.

## Full Schema Path

Use `ModelSignature` and `ModelSimilarityPlan` directly when you need explicit
comparison pairs, false-friend declarations, current evidence rows, or custom
metadata.

## What Model Similarity Reviews

- stable model signatures, including FunctionBlocks, inputs, outputs, state,
  side effects, invariants, failure modes, contracts, entrypoints, and evidence;
- stable business-intent, behavior-commitment, and primary-path identities,
  plus an explicit expected-member inventory and its revision/provenance;
- typed relations such as same workflow, family variant, symmetric flow, shared
  kernel, duplicate boundary, ownership overlap, adapter-only difference,
  evidence duplicate, false friend, and unrelated;
- route handoffs to Existing Model Preflight, ModelMesh, Architecture
  Reduction, Code Structure Recommendation, StructureMesh, Model-Test
  Alignment, or manual review;
- maintenance groups that identify A/B/C workflows that must be checked
  together;
- change impacts that list sibling models, code paths, and test paths when one
  member changes;
- shared and variant test obligations so family behavior and variant behavior
  are both covered;
- code obligations for shared kernels, adapters, duplicate boundaries,
  ownership overlap, and false-friend quarantine;
- materialized affected surfaces, test obligations, and code obligations in
  the handoff instead of opaque relation ids that downstream routes cannot
  verify;
- evidence gaps that keep similarity advice scoped rather than full confidence.

Similarity remains advisory: it may detect resemblance and produce explicit
obligations, but it never chooses the behavior commitment or runtime authority.
Use the downstream route it
names before merging models, extracting shared code, pruning adapters, or
claiming broad test and code confidence.
"""

__all__ = [
    'MODEL_SIMILARITY_CONSOLIDATION_MODEL_TEMPLATE',
    'MODEL_SIMILARITY_CONSOLIDATION_RUN_CHECKS_TEMPLATE',
    'MODEL_SIMILARITY_CONSOLIDATION_NOTES_TEMPLATE',
]

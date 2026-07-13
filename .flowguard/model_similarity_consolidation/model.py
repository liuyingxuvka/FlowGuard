"""FlowGuard Risk Purpose Header.

Purpose:
Models the model-similarity consolidation review route before exposing it as a
public FlowGuard helper.

Guards against:
- similarity advice without current evidence;
- changes to one model in a similar family failing to review siblings;
- shared behavior missing shared tests and variant behavior missing variant tests;
- shared-kernel metadata failing to produce code maintenance obligations;
- false friends being treated as merge candidates;
- family variants bypassing ModelMesh or Model-Test Alignment handoff;
- duplicate boundaries bypassing Architecture Reduction;
- unrelated models receiving consolidation routes.

Use before editing:
model_similarity.py, route integration fields, templates, docs, or public API
exports for model comparison.

Run:
python .flowguard/model_similarity_consolidation/run_checks.py
"""

from __future__ import annotations

from dataclasses import dataclass

from flowguard import (
    ModelSignature,
    ModelSimilarityEvidence,
    ModelSimilarityPlan,
    review_model_similarity_consolidation,
)


@dataclass(frozen=True)
class Case:
    name: str
    plan: ModelSimilarityPlan
    expected_ok: bool
    expected_relation_type: str
    expected_routes: tuple[str, ...] = ()
    expected_findings: tuple[str, ...] = ()
    expect_maintenance_group: bool = False
    expect_change_impact: bool = False
    expected_test_obligations: tuple[str, ...] = ()
    expected_code_obligations: tuple[str, ...] = ()
    expected_handoff_surface_ids: tuple[str, ...] = ()
    expected_handoff_behavior_planes: tuple[str, ...] = ()
    expected_typed_relation_refs: tuple[str, ...] = ()
    expect_cross_plane_relation: bool = False
    expect_materialized_handoff: bool = False


def family_variant_case() -> Case:
    return Case(
        "family_variant",
        ModelSimilarityPlan(
            "family-variant",
            signatures=(
                ModelSignature(
                    "checkout-simple",
                    workflow_family="checkout",
                    variant_id="simple",
                    function_blocks=("ValidateOrder", "PersistOrder"),
                    state_owned=("orders",),
                    failure_modes=("duplicate_submit",),
                    code_paths=("flowguard/checkout/simple.py",),
                    test_paths=("tests/test_checkout_simple.py",),
                    owned_public_behaviors=("submit_order",),
                    shared_kernel_id="checkout_core",
                    adapter_ids=("simple_adapter",),
                    maintenance_tags=("checkout",),
                    evidence_ids=("sim:checkout-family",),
                ),
                ModelSignature(
                    "checkout-retry",
                    workflow_family="checkout",
                    variant_id="retry",
                    function_blocks=("ValidateOrder", "PersistOrder"),
                    state_owned=("orders",),
                    failure_modes=("duplicate_submit",),
                    code_paths=("flowguard/checkout/retry.py",),
                    test_paths=("tests/test_checkout_retry.py",),
                    owned_public_behaviors=("submit_order", "retry_order"),
                    shared_kernel_id="checkout_core",
                    adapter_ids=("retry_adapter",),
                    maintenance_tags=("checkout",),
                    evidence_ids=("sim:checkout-family",),
                ),
                ModelSignature(
                    "checkout-cancel",
                    workflow_family="checkout",
                    variant_id="cancel",
                    function_blocks=("ValidateOrder", "PersistOrder"),
                    state_owned=("orders",),
                    failure_modes=("duplicate_submit", "cancel_after_auth"),
                    code_paths=("flowguard/checkout/cancel.py",),
                    test_paths=("tests/test_checkout_cancel.py",),
                    owned_public_behaviors=("cancel_order",),
                    shared_kernel_id="checkout_core",
                    adapter_ids=("cancel_adapter",),
                    maintenance_tags=("checkout",),
                    evidence_ids=("sim:checkout-family",),
                ),
            ),
            changed_model_ids=("checkout-simple",),
            evidence=(ModelSimilarityEvidence("sim:checkout-family"),),
            require_current_evidence=True,
        ),
        True,
        "same_family_variant",
        ("model_mesh", "model_test_alignment"),
        expect_maintenance_group=True,
        expect_change_impact=True,
        expected_test_obligations=("shared_behavior_tests", "variant_behavior_tests"),
        expected_code_obligations=("shared_kernel_or_adapter",),
    )


def missing_evidence_case() -> Case:
    return Case(
        "missing_evidence",
        ModelSimilarityPlan(
            "missing-evidence",
            signatures=(
                ModelSignature(
                    "billing-simple",
                    workflow_family="billing",
                    variant_id="simple",
                    function_blocks=("ValidateInvoice",),
                    failure_modes=("duplicate_invoice",),
                ),
                ModelSignature(
                    "billing-retry",
                    workflow_family="billing",
                    variant_id="retry",
                    function_blocks=("ValidateInvoice",),
                    failure_modes=("duplicate_invoice",),
                ),
            ),
            comparison_pairs=(("billing-simple", "billing-retry"),),
            require_current_evidence=True,
        ),
        False,
        "same_family_variant",
        ("model_mesh", "model_test_alignment"),
        ("missing_current_similarity_evidence",),
    )


def false_friend_case() -> Case:
    return Case(
        "false_friend",
        ModelSimilarityPlan(
            "false-friend",
            signatures=(
                ModelSignature(
                    "cache-refresh",
                    function_blocks=("RefreshCache",),
                    state_owned=("cache_entries",),
                    side_effects_owned=("write_cache",),
                    failure_modes=("stale_cache",),
                    false_friend_model_ids=("cache-report",),
                ),
                ModelSignature(
                    "cache-report",
                    function_blocks=("RenderReport",),
                    state_owned=("report_rows",),
                    side_effects_owned=("write_report",),
                    failure_modes=("missing_report_row",),
                ),
            ),
            comparison_pairs=(("cache-refresh", "cache-report"),),
        ),
        True,
        "false_friend",
        expected_code_obligations=("false_friend_quarantine",),
    )


def duplicate_boundary_case() -> Case:
    return Case(
        "duplicate_boundary",
        ModelSimilarityPlan(
            "duplicate-boundary",
            signatures=(
                ModelSignature(
                    "writer-a",
                    function_blocks=("WriteRecord",),
                    state_owned=("records",),
                    side_effects_owned=("write_record",),
                    failure_modes=("duplicate_write",),
                ),
                ModelSignature(
                    "writer-b",
                    function_blocks=("WriteRecord",),
                    state_owned=("records",),
                    side_effects_owned=("write_record",),
                    failure_modes=("duplicate_write",),
                ),
            ),
            comparison_pairs=(("writer-a", "writer-b"),),
        ),
        True,
        "duplicate_boundary",
        ("architecture_reduction",),
        expect_maintenance_group=True,
        expected_code_obligations=("duplicate_boundary_contraction",),
    )


def missing_maintenance_tests_case() -> Case:
    return Case(
        "missing_maintenance_tests",
        ModelSimilarityPlan(
            "missing-maintenance-tests",
            signatures=(
                ModelSignature(
                    "checkout-simple",
                    workflow_family="checkout",
                    variant_id="simple",
                    function_blocks=("ValidateOrder",),
                    test_paths=("tests/test_checkout_simple.py",),
                ),
                ModelSignature(
                    "checkout-retry",
                    workflow_family="checkout",
                    variant_id="retry",
                    function_blocks=("ValidateOrder",),
                    test_paths=(),
                ),
            ),
            require_maintenance_test_paths=True,
        ),
        False,
        "same_family_variant",
        ("model_mesh", "model_test_alignment"),
        ("missing_maintenance_test_path",),
        expect_maintenance_group=True,
        expected_test_obligations=("shared_behavior_tests", "variant_behavior_tests"),
    )


def unrelated_case() -> Case:
    return Case(
        "unrelated",
        ModelSimilarityPlan(
            "unrelated",
            signatures=(
                ModelSignature("search", function_blocks=("SearchIndex",)),
                ModelSignature("mailer", function_blocks=("SendEmail",)),
            ),
            comparison_pairs=(("search", "mailer"),),
        ),
        True,
        "unrelated",
    )


def exact_intent_reuse_case() -> Case:
    return Case(
        "exact_intent_reuse",
        ModelSimilarityPlan(
            "exact-intent-reuse",
            signatures=(
                ModelSignature(
                    "submit-ui",
                    function_blocks=("SubmitOrder",),
                    state_owned=("orders",),
                    side_effects_owned=("write_order",),
                    code_paths=("flowguard/orders/ui.py",),
                    test_paths=("tests/test_orders_ui.py",),
                    business_intent_ids=("intent:submit-order",),
                    behavior_commitment_ids=("commitment:submit-order",),
                    primary_path_ids=("path:submit-order",),
                    business_path_ids=("path:submit-order",),
                    path_terminals=("accepted_or_visible_error",),
                    public_surface_ids=("surface:ui-submit",),
                    behavior_plane="product_runtime",
                    evidence_ids=("sim:submit-order",),
                ),
                ModelSignature(
                    "submit-api",
                    function_blocks=("SubmitOrder",),
                    state_owned=("orders",),
                    side_effects_owned=("write_order",),
                    code_paths=("flowguard/orders/api.py",),
                    test_paths=("tests/test_orders_api.py",),
                    business_intent_ids=("intent:submit-order",),
                    behavior_commitment_ids=("commitment:submit-order",),
                    primary_path_ids=("path:submit-order",),
                    business_path_ids=("path:submit-order",),
                    path_terminals=("accepted_or_visible_error",),
                    public_surface_ids=("surface:api-submit",),
                    behavior_plane="product_runtime",
                    evidence_ids=("sim:submit-order",),
                ),
            ),
            evidence=(
                ModelSimilarityEvidence(
                    "sim:submit-order",
                    compared_behavior_planes=("product_runtime",),
                ),
            ),
            expected_surface_ids=("surface:ui-submit", "surface:api-submit"),
            surface_inventory_revision="submit-order-surfaces:v1",
            require_complete_surface_inventory=True,
            require_stable_authority_identity=True,
            require_behavior_plane_identity=True,
            require_current_evidence=True,
        ),
        True,
        "duplicate_boundary",
        ("architecture_reduction",),
        expected_code_obligations=("duplicate_boundary_contraction",),
        expected_handoff_surface_ids=("surface:ui-submit", "surface:api-submit"),
        expected_handoff_behavior_planes=("product_runtime",),
        expect_materialized_handoff=True,
    )


def omitted_surface_case() -> Case:
    plan = exact_intent_reuse_case().plan
    return Case(
        "omitted_surface",
        ModelSimilarityPlan(
            "omitted-surface",
            signatures=(plan.signatures[0],),
            expected_surface_ids=plan.expected_surface_ids,
            surface_inventory_revision=plan.surface_inventory_revision,
            require_complete_surface_inventory=True,
            require_stable_authority_identity=True,
        ),
        False,
        "",
        expected_findings=("missing_expected_similarity_surface",),
    )


def cross_plane_false_friend_case() -> Case:
    typed_ref = "commitment:agent-download|invokes|commitment:product-download"
    return Case(
        "cross_plane_false_friend",
        ModelSimilarityPlan(
            "cross-plane-false-friend",
            signatures=(
                ModelSignature(
                    "product-download",
                    function_blocks=("Download",),
                    owned_public_behaviors=("download",),
                    behavior_plane="product_runtime",
                    typed_commitment_relation_refs=(typed_ref,),
                ),
                ModelSignature(
                    "agent-download",
                    function_blocks=("Download",),
                    owned_public_behaviors=("download",),
                    behavior_plane="agent_operation",
                    typed_commitment_relation_refs=(typed_ref,),
                ),
            ),
            comparison_pairs=(("product-download", "agent-download"),),
            evidence=(
                ModelSimilarityEvidence(
                    "sim:cross-plane-download",
                    relation_id="product-download:agent-download:false_friend",
                    compared_behavior_planes=("product_runtime", "agent_operation"),
                    typed_commitment_relation_refs=(typed_ref,),
                ),
            ),
            require_behavior_plane_identity=True,
        ),
        True,
        "false_friend",
        expected_findings=("behavior_plane_conflict",),
        expected_handoff_behavior_planes=("product_runtime", "agent_operation"),
        expected_typed_relation_refs=(typed_ref,),
        expect_cross_plane_relation=True,
    )


CASES = (
    family_variant_case(),
    missing_evidence_case(),
    false_friend_case(),
    duplicate_boundary_case(),
    missing_maintenance_tests_case(),
    unrelated_case(),
    exact_intent_reuse_case(),
    omitted_surface_case(),
    cross_plane_false_friend_case(),
)


def run_case(case: Case) -> tuple[bool, str]:
    report = review_model_similarity_consolidation(case.plan)
    if report.ok != case.expected_ok:
        return False, f"{case.name}: expected ok={case.expected_ok}, got {report.ok}"
    relation_type = report.relations[0].relation_type if report.relations else ""
    if relation_type != case.expected_relation_type:
        return False, f"{case.name}: expected relation {case.expected_relation_type}, got {relation_type}"
    routes = set(report.recommended_next_routes)
    for route in case.expected_routes:
        if route not in routes:
            return False, f"{case.name}: missing route {route}"
    finding_codes = {finding.code for finding in report.findings}
    for code in case.expected_findings:
        if code not in finding_codes:
            return False, f"{case.name}: missing finding {code}"
    if case.expect_maintenance_group and not report.maintenance_groups:
        return False, f"{case.name}: missing maintenance group"
    if case.expect_change_impact and not report.change_impacts:
        return False, f"{case.name}: missing change impact"
    test_obligation_types = {obligation.obligation_type for obligation in report.test_obligations}
    for obligation_type in case.expected_test_obligations:
        if obligation_type not in test_obligation_types:
            return False, f"{case.name}: missing test obligation {obligation_type}"
    code_obligation_types = {obligation.obligation_type for obligation in report.code_obligations}
    for obligation_type in case.expected_code_obligations:
        if obligation_type not in code_obligation_types:
            return False, f"{case.name}: missing code obligation {obligation_type}"
    handoff = report.to_handoff()
    for surface_id in case.expected_handoff_surface_ids:
        if surface_id not in handoff.affected_surface_ids:
            return False, f"{case.name}: handoff missing affected surface {surface_id}"
    for plane in case.expected_handoff_behavior_planes:
        if plane not in handoff.behavior_planes:
            return False, f"{case.name}: handoff missing behavior plane {plane}"
    for relation_ref in case.expected_typed_relation_refs:
        if relation_ref not in handoff.typed_commitment_relation_refs:
            return False, f"{case.name}: handoff missing typed relation {relation_ref}"
    if case.expect_cross_plane_relation and not handoff.cross_plane_relation_ids:
        return False, f"{case.name}: handoff missing cross-plane relation id"
    if case.expect_materialized_handoff and not (handoff.test_obligations or handoff.code_obligations):
        return False, f"{case.name}: handoff preserved only opaque obligation ids"
    return True, report.summary


def run_review() -> tuple[tuple[str, bool, str], ...]:
    rows = []
    for case in CASES:
        ok, summary = run_case(case)
        rows.append((case.name, ok, summary))
    return tuple(rows)

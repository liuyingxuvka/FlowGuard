"""FlowGuard model

Purpose: Prove that path-sensitive work has one primary runtime authority and that primary failure is exposed instead of silently routed to alternate success.
Guards against: automatic fallback success after primary failure, compatibility facades becoming second authorities, old fields or backup caches masking broken primary paths, manual recovery paths being auto-invoked, and broad confidence claims without full Cartesian coverage evidence.
Use before editing: Run this before path-sensitive feature work, bug fixes, refactors, API compatibility decisions, or release claims where alternate execution paths may hide the real broken path.

Run: python -m flowguard map models primary_path_authority
"""

from flowguard import (
    FallbackPathCandidate,
    PrimaryPathAuthorityPlan,
    PrimaryPathContract,
    PPA_AUTHORITY_EXTERNAL_FACADE,
    PPA_AUTHORITY_MANUAL_RECOVERY,
    PPA_BEHAVIOR_DELEGATE_TO_PRIMARY,
    PPA_BEHAVIOR_READ_STATE,
    PPA_BEHAVIOR_RETURN_SUCCESS,
    PPA_CANDIDATE_COMPATIBILITY_FACADE,
    PPA_CANDIDATE_LEGACY_PATH,
    PPA_CANDIDATE_MANUAL_RECOVERY,
    PPA_CANDIDATE_OLD_FIELD,
    PPA_CLAIM_SCOPE_FULL,
    PPA_DISPOSITION_BLOCK,
    PPA_DISPOSITION_MANUAL_ONLY,
    PPA_DISPOSITION_PRESERVE_FACADE,
    PPA_DISPOSITION_UNKNOWN,
    PPA_TRIGGER_MISSING_FIELD,
    PPA_TRIGGER_PRIMARY_FAILURE,
)


INTENT_ID = "intent:submit-order"
COMMITMENT_ID = "commitment:submit-order"
PRIMARY_PATH_ID = "submit_order"


def primary_path():
    return PrimaryPathContract(
        PRIMARY_PATH_ID,
        business_intent="submit order",
        business_intent_id=INTENT_ID,
        behavior_commitment_id=COMMITMENT_ID,
        primary_entrypoint_id="orders.submit.primary",
        owner_model_id="orders.submit.model",
        owner_code_contract_id="orders.submit.contract",
        expected_terminal="accepted_or_visible_error",
        evidence_ids=("runtime:submit-order:no-fallback",),
        runtime_evidence_state="current_pass",
        runtime_observation_ids=("runtime:submit-order:no-fallback",),
        required_obligation_ids=("obligation:submit-order-primary",),
        source_surface_ids=("surface:orders-primary",),
    )


def complete_plan():
    return PrimaryPathAuthorityPlan(
        "complete-primary-path-authority",
        primary_paths=(primary_path(),),
        fallback_candidates=(
            FallbackPathCandidate(
                "orders.submit.v1",
                fallback_for_path_id="submit_order",
                business_intent="submit order",
                business_intent_id=INTENT_ID,
                behavior_commitment_id=COMMITMENT_ID,
                source_surface_id="surface:orders-v1",
                delegates_to_path_id=PRIMARY_PATH_ID,
                candidate_surface=PPA_CANDIDATE_COMPATIBILITY_FACADE,
                candidate_behavior=PPA_BEHAVIOR_DELEGATE_TO_PRIMARY,
                classification=PPA_AUTHORITY_EXTERNAL_FACADE,
                disposition=PPA_DISPOSITION_PRESERVE_FACADE,
                evidence_refs=("test:legacy-api-delegates-to-primary",),
                compatibility_intent="external API keeps old entrypoint while delegating to primary path",
            ),
        ),
        claim_scope=PPA_CLAIM_SCOPE_FULL,
        require_cartesian_coverage=True,
        coverage_case_ids=("ppa.core_no_fallback.submit_order.exception.legacy.primary_failure.return_success",),
        coverage_shard_ids=("contract_shard:primary_path_authority:core_no_fallback",),
        risk_gate_ids=("risk_gate:primary_path_authority", "risk_gate:primary_path_authority_cartesian_coverage"),
        expected_business_intent_ids=(INTENT_ID,),
        expected_candidate_ids=("orders.submit.v1",),
        expected_surface_ids=("surface:orders-primary", "surface:orders-v1"),
        inventory_revision="orders-surface-inventory:v1",
        inventory_evidence_ids=("inventory:orders-surfaces:v1",),
        preflight_id="preflight:submit-order",
        behavior_commitment_ledger_id="ledger:orders",
        existing_current_path_ids=(PRIMARY_PATH_ID,),
    )


# FlowGuard contract (feature kit): each former broken plan is a feature that changes the complete plan
# above; the kit explores every feature alone and every pair, and conformance reviews each combination
# with the real primary-path authority review.
from dataclasses import replace  # noqa: E402

from flowguard import review_primary_path_authority  # noqa: E402
from flowguard.kit import Feature, feature_conformance, feature_explorer, feature_variants  # noqa: E402

MODEL_ID = "primary_path_authority"
PARENT = "behavior-commitment"
COMPONENTS = ["behavior-commitment"]
IMPLEMENTED_BY = {"Review": "flowguard/primary_path_authority.py:review_primary_path_authority"}
TESTED_BY = {"each_defect_rejected": [
    "tests/test_primary_path_authority.py:test_good_plan_with_thin_facade_and_coverage_passes",
    "tests/test_primary_path_authority.py:test_duplicate_primary_authority_blocks"]}


def _candidate(candidate_id: str, surface_id: str, **values):
    """Adds a fallback candidate for the primary path that names its intent, commitment and surface."""
    candidate = FallbackPathCandidate(candidate_id, fallback_for_path_id=PRIMARY_PATH_ID, business_intent="submit order",
                                      business_intent_id=INTENT_ID, behavior_commitment_id=COMMITMENT_ID,
                                      source_surface_id=surface_id, **values)
    return lambda plan: replace(plan, fallback_candidates=plan.fallback_candidates + (candidate,))


def _drop_facade(plan):
    return replace(plan, fallback_candidates=tuple(c for c in plan.fallback_candidates
                                                   if c.candidate_path_id != "orders.submit.v1"))


def _second_primary(plan):
    parallel = replace(primary_path(), business_path_id="submit_order_parallel",
                       primary_entrypoint_id="orders.submit.parallel", owner_model_id="orders.submit.parallel.model",
                       owner_code_contract_id="orders.submit.parallel.contract")
    return replace(plan, primary_paths=plan.primary_paths + (parallel,))


def _stale_evidence(plan):
    return replace(plan, primary_paths=tuple(
        replace(path, runtime_evidence_state="stale", runtime_observation_ids=("runtime:submit-order:stale",),
                evidence_ids=())
        if path.business_path_id == PRIMARY_PATH_ID else path for path in plan.primary_paths))


MASKED = ("primary_failure_masked_by_fallback_success", "parallel_same_intent_success_path")
FEATURES = (
    Feature("missing_candidate_inventory", True,
            ("expected_primary_path_candidate_missing", "expected_primary_path_surface_missing"), _drop_facade),
    Feature("fallback_success_after_primary_failure", True, MASKED,
            _candidate("orders.submit.legacy-fallback", "surface:orders-legacy", candidate_surface=PPA_CANDIDATE_LEGACY_PATH,
                       candidate_trigger=PPA_TRIGGER_PRIMARY_FAILURE, candidate_behavior=PPA_BEHAVIOR_RETURN_SUCCESS,
                       invokes_on_primary_failure=True, returns_success_after_primary_failure=True,
                       disposition=PPA_DISPOSITION_BLOCK)),
    Feature("old_field_fallback", True,
            ("fallback_candidate_unknown_disposition", "old_field_or_backup_cache_masks_primary_failure") + MASKED,
            _candidate("orders.old_status", "surface:orders-old-status", candidate_surface=PPA_CANDIDATE_OLD_FIELD,
                       candidate_trigger=PPA_TRIGGER_MISSING_FIELD, candidate_behavior=PPA_BEHAVIOR_READ_STATE,
                       returns_success_after_primary_failure=True, disposition=PPA_DISPOSITION_UNKNOWN)),
    Feature("manual_recovery_auto_invoked", True, ("manual_recovery_auto_invoked",),
            _candidate("orders.operator-repair", "surface:orders-repair", candidate_surface=PPA_CANDIDATE_MANUAL_RECOVERY,
                       candidate_trigger=PPA_TRIGGER_PRIMARY_FAILURE, classification=PPA_AUTHORITY_MANUAL_RECOVERY,
                       disposition=PPA_DISPOSITION_MANUAL_ONLY, invokes_on_primary_failure=True,
                       evidence_refs=("manual:repair-doc",))),
    Feature("second_primary_for_same_intent", True,
            ("duplicate_primary_runtime_authority", "existing_primary_path_not_reused"), _second_primary),
    Feature("stale_runtime_evidence", True, ("primary_path_runtime_evidence_not_current",), _stale_evidence),
    Feature("facade_with_more_evidence", False, (),
            lambda plan: replace(plan, fallback_candidates=tuple(
                replace(c, evidence_refs=c.evidence_refs + ("test:legacy-api-error-passthrough",))
                for c in plan.fallback_candidates))),
)


def build_explorer():
    return feature_explorer(FEATURES)


def broken_variants():
    return feature_variants(FEATURES)


def _review(plan):
    report = review_primary_path_authority(plan)
    return report.ok, tuple(finding.code for finding in report.findings)


def conformance():
    return feature_conformance(FEATURES, complete_plan, _review)

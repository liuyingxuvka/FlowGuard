"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Prove that path-sensitive work has one primary runtime authority and that primary failure is exposed instead of silently routed to alternate success.
Guards against: automatic fallback success after primary failure, compatibility facades becoming second authorities, old fields or backup caches masking broken primary paths, manual recovery paths being auto-invoked, and broad confidence claims without full Cartesian coverage evidence.
Use before editing: Run this before path-sensitive feature work, bug fixes, refactors, API compatibility decisions, or release claims where alternate execution paths may hide the real broken path.

Run: python .flowguard/primary_path_authority/run_checks.py
"""

from flowguard import (
    FallbackPathCandidate,
    PrimaryPathAuthorityPlan,
    PrimaryPathContract,
    ProofArtifactRef,
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


def current_proof():
    return ProofArtifactRef(
        "proof:submit-order-primary",
        producer_route="runtime_path_evidence",
        command="python -m pytest tests/test_primary_path_authority.py -q",
        result_path=".flowguard/evidence/submit-order-primary.json",
        result_status="passed",
        exit_code=0,
        artifact_fingerprints={"orders.submit.contract": "sha256:current"},
        covered_obligation_ids=("obligation:submit-order-primary",),
        metadata={
            "business_intent_id": INTENT_ID,
            "behavior_commitment_id": COMMITMENT_ID,
            "primary_path_id": PRIMARY_PATH_ID,
            "expected_terminal": "accepted_or_visible_error",
        },
    )


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
        proof_artifact=current_proof(),
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
        coverage_receipt_ids=("contract_coverage:primary_path_authority",),
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


def broken_a_failed_b_success():
    return PrimaryPathAuthorityPlan(
        "broken-a-failed-b-success",
        primary_paths=(primary_path(),),
        fallback_candidates=(
            FallbackPathCandidate(
                "orders.submit.legacy-fallback",
                fallback_for_path_id="submit_order",
                business_intent="submit order",
                candidate_surface=PPA_CANDIDATE_LEGACY_PATH,
                candidate_trigger=PPA_TRIGGER_PRIMARY_FAILURE,
                candidate_behavior=PPA_BEHAVIOR_RETURN_SUCCESS,
                invokes_on_primary_failure=True,
                returns_success_after_primary_failure=True,
                disposition=PPA_DISPOSITION_BLOCK,
            ),
        ),
    )


def broken_old_field_fallback():
    return PrimaryPathAuthorityPlan(
        "broken-old-field-fallback",
        primary_paths=(primary_path(),),
        fallback_candidates=(
            FallbackPathCandidate(
                "orders.old_status",
                fallback_for_path_id="submit_order",
                business_intent="submit order",
                candidate_surface=PPA_CANDIDATE_OLD_FIELD,
                candidate_trigger=PPA_TRIGGER_MISSING_FIELD,
                candidate_behavior=PPA_BEHAVIOR_READ_STATE,
                returns_success_after_primary_failure=True,
                disposition=PPA_DISPOSITION_UNKNOWN,
            ),
        ),
    )


def broken_manual_recovery_auto_invoked():
    return PrimaryPathAuthorityPlan(
        "broken-manual-recovery-auto-invoked",
        primary_paths=(primary_path(),),
        fallback_candidates=(
            FallbackPathCandidate(
                "orders.operator-repair",
                fallback_for_path_id="submit_order",
                business_intent="submit order",
                candidate_surface=PPA_CANDIDATE_MANUAL_RECOVERY,
                candidate_trigger=PPA_TRIGGER_PRIMARY_FAILURE,
                classification=PPA_AUTHORITY_MANUAL_RECOVERY,
                disposition=PPA_DISPOSITION_MANUAL_ONLY,
                invokes_on_primary_failure=True,
                evidence_refs=("manual:repair-doc",),
            ),
        ),
    )


def broken_two_paths_same_exact_intent():
    return PrimaryPathAuthorityPlan(
        "broken-two-paths-same-exact-intent",
        primary_paths=(
            primary_path(),
            PrimaryPathContract(
                "submit_order_parallel",
                business_intent="submit order",
                business_intent_id=INTENT_ID,
                behavior_commitment_id=COMMITMENT_ID,
                primary_entrypoint_id="orders.submit.parallel",
                owner_model_id="orders.submit.parallel.model",
                owner_code_contract_id="orders.submit.parallel.contract",
                expected_terminal="accepted_or_visible_error",
            ),
        ),
    )


def broken_missing_candidate_inventory():
    plan = complete_plan()
    return PrimaryPathAuthorityPlan(
        "broken-missing-candidate-inventory",
        primary_paths=plan.primary_paths,
        fallback_candidates=(),
        claim_scope=plan.claim_scope,
        coverage_case_ids=plan.coverage_case_ids,
        coverage_shard_ids=plan.coverage_shard_ids,
        coverage_receipt_ids=plan.coverage_receipt_ids,
        risk_gate_ids=plan.risk_gate_ids,
        expected_business_intent_ids=plan.expected_business_intent_ids,
        expected_candidate_ids=plan.expected_candidate_ids,
        expected_surface_ids=plan.expected_surface_ids,
        inventory_revision=plan.inventory_revision,
        inventory_evidence_ids=plan.inventory_evidence_ids,
        preflight_id=plan.preflight_id,
        behavior_commitment_ledger_id=plan.behavior_commitment_ledger_id,
        existing_current_path_ids=plan.existing_current_path_ids,
    )


def broken_stale_material_evidence():
    stale = PrimaryPathContract(
        PRIMARY_PATH_ID,
        business_intent="submit order",
        business_intent_id=INTENT_ID,
        behavior_commitment_id=COMMITMENT_ID,
        primary_entrypoint_id="orders.submit.primary",
        owner_model_id="orders.submit.model",
        owner_code_contract_id="orders.submit.contract",
        expected_terminal="accepted_or_visible_error",
        runtime_evidence_state="stale",
        runtime_observation_ids=("runtime:submit-order:stale",),
        required_obligation_ids=("obligation:submit-order-primary",),
        proof_artifact=ProofArtifactRef(
            "proof:submit-order-stale",
            result_path=".flowguard/evidence/submit-order-stale.json",
            result_status="stale",
            current=False,
        ),
    )
    plan = complete_plan()
    return PrimaryPathAuthorityPlan(
        "broken-stale-material-evidence",
        primary_paths=(stale,),
        claim_scope=plan.claim_scope,
        coverage_case_ids=plan.coverage_case_ids,
        coverage_shard_ids=plan.coverage_shard_ids,
        coverage_receipt_ids=plan.coverage_receipt_ids,
        risk_gate_ids=plan.risk_gate_ids,
        expected_business_intent_ids=plan.expected_business_intent_ids,
        inventory_revision=plan.inventory_revision,
        inventory_evidence_ids=plan.inventory_evidence_ids,
        preflight_id=plan.preflight_id,
        behavior_commitment_ledger_id=plan.behavior_commitment_ledger_id,
        existing_current_path_ids=plan.existing_current_path_ids,
    )

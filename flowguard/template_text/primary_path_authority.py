"""Template text for FlowGuard Primary Path Authority."""

PRIMARY_PATH_AUTHORITY_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Prove that one business intent has one primary runtime authority and that primary failure is exposed instead of silently routed to alternate success.
Guards against: automatic fallback success after primary failure, compatibility facades becoming second authorities, old fields or backup caches masking broken primary paths, manual recovery paths being auto-invoked, and broad confidence claims without full Cartesian coverage evidence.
Use before editing: Run this before path-sensitive feature work, bug fixes, refactors, API compatibility decisions, or release claims where alternate execution paths may hide the real broken path.

Run: python .flowguard/primary_path_authority/run_checks.py
"""

from flowguard import (
    FallbackPathCandidate,
    PrimaryPathAuthorityPlan,
    PrimaryPathContract,
    PPA_AUTHORITY_EXTERNAL_FACADE,
    PPA_AUTHORITY_MANUAL_RECOVERY,
    PPA_CANDIDATE_COMPATIBILITY_FACADE,
    PPA_CANDIDATE_LEGACY_PATH,
    PPA_CANDIDATE_MANUAL_RECOVERY,
    PPA_CANDIDATE_OLD_FIELD,
    PPA_BEHAVIOR_DELEGATE_TO_PRIMARY,
    PPA_BEHAVIOR_READ_STATE,
    PPA_BEHAVIOR_RETURN_SUCCESS,
    PPA_CLAIM_SCOPE_FULL,
    PPA_DISPOSITION_BLOCK,
    PPA_DISPOSITION_PRESERVE_FACADE,
    PPA_DISPOSITION_UNKNOWN,
    PPA_TRIGGER_MISSING_FIELD,
    PPA_TRIGGER_PRIMARY_FAILURE,
    review_primary_path_authority,
)


def good_plan():
    return PrimaryPathAuthorityPlan(
        "good-primary-path-authority",
        primary_paths=(
            PrimaryPathContract(
                "submit_order",
                business_intent="submit order",
                primary_entrypoint_id="orders.submit.primary",
                owner_model_id="orders.submit.model",
                owner_code_contract_id="orders.submit.contract",
                expected_terminal="accepted_or_visible_error",
                evidence_ids=("runtime:submit-order:no-fallback",),
            ),
        ),
        fallback_candidates=(
            FallbackPathCandidate(
                "orders.submit.legacy-api",
                fallback_for_path_id="submit_order",
                business_intent="submit order",
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
    )


def broken_a_failed_b_success():
    return PrimaryPathAuthorityPlan(
        "broken-a-failed-b-success",
        primary_paths=good_plan().primary_paths,
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
        primary_paths=good_plan().primary_paths,
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
        "broken-manual-recovery-auto",
        primary_paths=good_plan().primary_paths,
        fallback_candidates=(
            FallbackPathCandidate(
                "orders.operator-repair",
                fallback_for_path_id="submit_order",
                business_intent="submit order",
                candidate_surface=PPA_CANDIDATE_MANUAL_RECOVERY,
                candidate_trigger=PPA_TRIGGER_PRIMARY_FAILURE,
                classification=PPA_AUTHORITY_MANUAL_RECOVERY,
                disposition="manual_only",
                invokes_on_primary_failure=True,
                evidence_refs=("manual:repair-doc",),
            ),
        ),
    )
'''


PRIMARY_PATH_AUTHORITY_RUN_CHECKS_TEMPLATE = '''"""Run Primary Path Authority checks."""

from model import (
    broken_a_failed_b_success,
    broken_manual_recovery_auto_invoked,
    broken_old_field_fallback,
    good_plan,
)
from flowguard import review_primary_path_authority


def assert_codes(report, *codes):
    actual = {finding.code for finding in report.findings}
    missing = set(codes) - actual
    if missing:
        raise AssertionError(f"missing findings {sorted(missing)} in {actual}\\n{report.format_text()}")


def main():
    good = review_primary_path_authority(good_plan())
    print(good.format_text())
    if not good.ok:
        raise SystemExit("good Primary Path Authority plan failed")

    bad = review_primary_path_authority(broken_a_failed_b_success())
    assert_codes(bad, "primary_failure_masked_by_fallback_success")

    bad_field = review_primary_path_authority(broken_old_field_fallback())
    assert_codes(bad_field, "fallback_candidate_unknown_disposition", "old_field_or_backup_cache_masks_primary_failure")

    bad_manual = review_primary_path_authority(broken_manual_recovery_auto_invoked())
    assert_codes(bad_manual, "manual_recovery_auto_invoked")

    print("Primary Path Authority checks passed")


if __name__ == "__main__":
    main()
'''


PRIMARY_PATH_AUTHORITY_NOTES_TEMPLATE = """# FlowGuard Primary Path Authority Notes

Use this route before implementing path-sensitive behavior, bug repairs,
compatibility cleanup, field replacement, route/helper cleanup, install sync,
or release confidence.

Core rule: one business intent has one primary runtime authority. If that
primary path fails, expose the failure and repair the primary path. Do not
automatically run an alternate implementation and return success.

Required evidence:

- primary path contract for each business intent;
- disposition for every old path, alias, wrapper, helper route, compatibility
  facade, old field, backup cache, migration path, and manual recovery surface;
- runtime evidence that no fallback was invoked to mask primary failure;
- ContractExhaustionMesh axes, interaction groups, cases, shards, and coverage
  receipts for broad claims;
- TestMesh child shard evidence when the matrix is split;
- Risk Evidence Ledger gates before done/release/full confidence.
"""

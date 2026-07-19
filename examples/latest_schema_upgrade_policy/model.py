"""Executable model for FlowGuard's latest-schema upgrade policy."""

from __future__ import annotations

from dataclasses import dataclass

from flowguard import (
    FunctionResult,
    Invariant,
    InvariantResult,
    Scenario,
    ScenarioExpectation,
    Workflow,
    review_scenarios,
)


@dataclass(frozen=True)
class UpgradePolicyCase:
    name: str


@dataclass(frozen=True)
class UpgradePolicyState:
    case_name: str = ""
    artifact_shape: str = "unknown"
    artifact_ownership: str = "unknown"
    project_version_state: str = "current"
    upgrade_action: str = "not_run"
    json_write_performed: bool = False
    json_write_owner: str = "none"
    target_owned_json_modified: bool = False
    target_owned_json_bytes_preserved: bool = True
    runtime_accepts_old_shape: bool = False
    validation_status: str = "not_run"
    safety_classifier_preserved: bool = True
    blocked_unknowns_visible: bool = True
    records_only_scope_declared: bool = False


CURRENT_ARTIFACT = UpgradePolicyCase("current_artifact_passes")
LEGACY_BCL_ARTIFACT_UPGRADED = UpgradePolicyCase(
    "legacy_behavior_ledger_artifact_upgraded"
)
UNSUPPORTED_REGISTERED_ENVELOPE_BLOCKED = UpgradePolicyCase(
    "unsupported_registered_envelope_blocked"
)
TARGET_OWNED_JSON_PRESERVED = UpgradePolicyCase("target_owned_json_preserved")
OLDER_PROJECT_TRIGGERS_SCAN = UpgradePolicyCase("older_project_triggers_upgrade_scan")
UNKNOWN_SCRIPT_BLOCKED = UpgradePolicyCase("unknown_script_blocks")
RECORDS_ONLY_SCOPED = UpgradePolicyCase("records_only_scope_declared")
BROKEN_RUNTIME_COMPAT = UpgradePolicyCase("broken_runtime_accepts_old_shape")
BROKEN_SILENT_SKIP = UpgradePolicyCase("broken_older_project_skips_scan")
BROKEN_UNKNOWN_REWRITE = UpgradePolicyCase("broken_unknown_script_rewritten")
BROKEN_CLASSIFIER_DELETED = UpgradePolicyCase("broken_safety_classifier_deleted")
BROKEN_NUMERIC_TARGET_JSON_REWRITE = UpgradePolicyCase(
    "broken_numeric_target_json_rewrite"
)
BROKEN_PARTIAL_LEDGER_REWRITE = UpgradePolicyCase("broken_partial_ledger_rewrite")
BROKEN_UNSUPPORTED_REGISTERED_ENVELOPE_REWRITE = UpgradePolicyCase(
    "broken_unsupported_registered_envelope_rewrite"
)


class ApplyUpgradePolicyCase:
    name = "ApplyUpgradePolicyCase"
    reads = ("case_name",)
    writes = (
        "case_name",
        "artifact_shape",
        "artifact_ownership",
        "project_version_state",
        "upgrade_action",
        "json_write_performed",
        "json_write_owner",
        "target_owned_json_modified",
        "target_owned_json_bytes_preserved",
        "runtime_accepts_old_shape",
        "validation_status",
        "safety_classifier_preserved",
        "blocked_unknowns_visible",
        "records_only_scope_declared",
    )

    def apply(self, input_obj: UpgradePolicyCase, state: UpgradePolicyState):
        del state
        return (
            FunctionResult(
                output=input_obj,
                new_state=_state_for_case(input_obj),
                label=input_obj.name,
            ),
        )


def _state_for_case(case: UpgradePolicyCase) -> UpgradePolicyState:
    if case == CURRENT_ARTIFACT:
        return UpgradePolicyState(
            case_name=case.name,
            artifact_shape="current",
            artifact_ownership="exact-current-flowguard-envelope",
            project_version_state="current",
            upgrade_action="unchanged",
            validation_status="route_evidence_required",
        )
    if case == LEGACY_BCL_ARTIFACT_UPGRADED:
        return UpgradePolicyState(
            case_name=case.name,
            artifact_shape="current",
            artifact_ownership="exact-legacy-56083c1e-bcl",
            project_version_state="older",
            upgrade_action="deterministic_upgrade",
            json_write_performed=True,
            json_write_owner="exact-legacy-56083c1e-bcl",
            validation_status="route_evidence_required",
        )
    if case == UNSUPPORTED_REGISTERED_ENVELOPE_BLOCKED:
        return UpgradePolicyState(
            case_name=case.name,
            artifact_shape="unsupported-registered-envelope-version",
            artifact_ownership="registered-flowguard",
            project_version_state="older",
            upgrade_action="blocked",
            validation_status="blocked",
        )
    if case == TARGET_OWNED_JSON_PRESERVED:
        return UpgradePolicyState(
            case_name=case.name,
            artifact_shape="numeric-schema-json",
            artifact_ownership="target-owned",
            project_version_state="older",
            upgrade_action="outside_authority",
            validation_status="route_evidence_required",
            target_owned_json_modified=False,
            target_owned_json_bytes_preserved=True,
        )
    if case == OLDER_PROJECT_TRIGGERS_SCAN:
        return UpgradePolicyState(
            case_name=case.name,
            artifact_shape="current",
            project_version_state="older",
            upgrade_action="scan_and_upgrade",
            validation_status="route_evidence_required",
        )
    if case == UNKNOWN_SCRIPT_BLOCKED:
        return UpgradePolicyState(
            case_name=case.name,
            artifact_shape="unknown_script",
            project_version_state="older",
            upgrade_action="blocked",
            validation_status="blocked",
            blocked_unknowns_visible=True,
        )
    if case == RECORDS_ONLY_SCOPED:
        return UpgradePolicyState(
            case_name=case.name,
            artifact_shape="old",
            project_version_state="older",
            upgrade_action="records_only",
            validation_status="scoped",
            records_only_scope_declared=True,
        )
    if case == BROKEN_RUNTIME_COMPAT:
        return UpgradePolicyState(
            case_name=case.name,
            artifact_shape="old",
            project_version_state="current",
            upgrade_action="not_run",
            runtime_accepts_old_shape=True,
            validation_status="pass",
        )
    if case == BROKEN_SILENT_SKIP:
        return UpgradePolicyState(
            case_name=case.name,
            artifact_shape="old",
            project_version_state="older",
            upgrade_action="not_run",
            validation_status="pass",
        )
    if case == BROKEN_UNKNOWN_REWRITE:
        return UpgradePolicyState(
            case_name=case.name,
            artifact_shape="unknown_script",
            project_version_state="older",
            upgrade_action="deterministic_upgrade",
            validation_status="pass",
            blocked_unknowns_visible=False,
        )
    if case == BROKEN_CLASSIFIER_DELETED:
        return UpgradePolicyState(
            case_name=case.name,
            artifact_shape="old",
            project_version_state="older",
            upgrade_action="deterministic_upgrade",
            validation_status="pass",
            safety_classifier_preserved=False,
        )
    if case == BROKEN_NUMERIC_TARGET_JSON_REWRITE:
        return UpgradePolicyState(
            case_name=case.name,
            artifact_shape="numeric-schema-json",
            artifact_ownership="target-owned",
            project_version_state="older",
            upgrade_action="deterministic_upgrade",
            json_write_performed=True,
            json_write_owner="target-owned",
            target_owned_json_modified=True,
            target_owned_json_bytes_preserved=False,
            validation_status="pass",
        )
    if case == BROKEN_PARTIAL_LEDGER_REWRITE:
        return UpgradePolicyState(
            case_name=case.name,
            artifact_shape="full-legacy-fields-plus-target-extra",
            artifact_ownership="target-owned",
            project_version_state="older",
            upgrade_action="deterministic_upgrade",
            json_write_performed=True,
            json_write_owner="target-owned",
            target_owned_json_modified=True,
            target_owned_json_bytes_preserved=False,
            validation_status="pass",
        )
    if case == BROKEN_UNSUPPORTED_REGISTERED_ENVELOPE_REWRITE:
        return UpgradePolicyState(
            case_name=case.name,
            artifact_shape="unsupported-registered-envelope-version",
            artifact_ownership="registered-flowguard",
            project_version_state="older",
            upgrade_action="deterministic_upgrade",
            json_write_performed=True,
            json_write_owner="unsupported-current-only-envelope",
            validation_status="pass",
        )
    raise ValueError(f"unknown upgrade policy case: {case!r}")


def _fail(name: str, message: str) -> InvariantResult:
    return InvariantResult.fail(message, {"violation": name})


def runtime_is_current_only(state: UpgradePolicyState, trace) -> InvariantResult:
    del trace
    if state.runtime_accepts_old_shape:
        return _fail(
            "runtime_is_current_only",
            "runtime accepted an old shape instead of requiring boundary upgrade",
        )
    return InvariantResult.pass_()


def older_project_runs_upgrade_scan(state: UpgradePolicyState, trace) -> InvariantResult:
    del trace
    if (
        state.project_version_state == "older"
        and state.upgrade_action == "not_run"
        and not state.records_only_scope_declared
    ):
        return _fail(
            "older_project_runs_upgrade_scan",
            "older project version skipped artifact/model/test upgrade scan",
        )
    return InvariantResult.pass_()


def unknown_script_blocks(state: UpgradePolicyState, trace) -> InvariantResult:
    del trace
    if state.artifact_shape == "unknown_script" and state.upgrade_action != "blocked":
        return _fail(
            "unknown_script_blocks",
            "unknown behavior-bearing script was upgraded instead of blocked",
        )
    if state.artifact_shape == "unknown_script" and not state.blocked_unknowns_visible:
        return _fail(
            "unknown_script_blocks",
            "unknown script block was not visible in the report",
        )
    return InvariantResult.pass_()


def safety_classifier_survives_cleanup(state: UpgradePolicyState, trace) -> InvariantResult:
    del trace
    if not state.safety_classifier_preserved:
        return _fail(
            "safety_classifier_survives_cleanup",
            "safety classifier was deleted as compatibility bloat",
        )
    return InvariantResult.pass_()


def artifact_write_requires_exact_bounded_owner(
    state: UpgradePolicyState, trace
) -> InvariantResult:
    del trace
    if (
        state.json_write_performed
        and state.json_write_owner != "exact-legacy-56083c1e-bcl"
    ):
        return _fail(
            "artifact_write_requires_exact_bounded_owner",
            "a JSON write occurred without the exact historical 56083c1e BCL owner",
        )
    return InvariantResult.pass_()


def target_owned_json_is_byte_identical(
    state: UpgradePolicyState, trace
) -> InvariantResult:
    del trace
    if (
        state.artifact_ownership == "target-owned"
        and not state.target_owned_json_bytes_preserved
    ):
        return _fail(
            "target_owned_json_is_byte_identical",
            "target-owned JSON bytes changed during FlowGuard artifact upgrade",
        )
    return InvariantResult.pass_()


def registered_envelopes_are_current_only(
    state: UpgradePolicyState, trace
) -> InvariantResult:
    del trace
    if (
        state.artifact_shape == "unsupported-registered-envelope-version"
        and state.upgrade_action != "blocked"
    ):
        return _fail(
            "registered_envelopes_are_current_only",
            "unsupported registered envelope version was rewritten without an evidence-bound migrator",
        )
    return InvariantResult.pass_()


def upgrade_does_not_replace_validation(state: UpgradePolicyState, trace) -> InvariantResult:
    del trace
    if state.upgrade_action in {"deterministic_upgrade", "scan_and_upgrade"} and state.validation_status == "pass":
        return _fail(
            "upgrade_does_not_replace_validation",
            "upgrade report was treated as route validation evidence",
        )
    return InvariantResult.pass_()


def invariants() -> tuple[Invariant, ...]:
    return (
        Invariant("runtime_is_current_only", "Runtime accepts only current shapes", runtime_is_current_only),
        Invariant(
            "older_project_runs_upgrade_scan",
            "Older adopted projects run upgrade scanning by default",
            older_project_runs_upgrade_scan,
        ),
        Invariant("unknown_script_blocks", "Unknown behavior-bearing scripts block", unknown_script_blocks),
        Invariant(
            "safety_classifier_survives_cleanup",
            "Safety classifiers are not cleanup targets",
            safety_classifier_survives_cleanup,
        ),
        Invariant(
            "artifact_write_requires_exact_bounded_owner",
            "JSON writes require an exact bounded FlowGuard owner",
            artifact_write_requires_exact_bounded_owner,
        ),
        Invariant(
            "target_owned_json_is_byte_identical",
            "Target-owned JSON remains byte-identical",
            target_owned_json_is_byte_identical,
        ),
        Invariant(
            "registered_envelopes_are_current_only",
            "Registered report and trace envelopes are current-only",
            registered_envelopes_are_current_only,
        ),
        Invariant(
            "upgrade_does_not_replace_validation",
            "Upgrade reports do not replace route evidence",
            upgrade_does_not_replace_validation,
        ),
    )


def build_workflow() -> Workflow:
    return Workflow((ApplyUpgradePolicyCase(),), name="latest_schema_upgrade_policy")


def all_cases() -> tuple[UpgradePolicyCase, ...]:
    return (
        CURRENT_ARTIFACT,
        LEGACY_BCL_ARTIFACT_UPGRADED,
        UNSUPPORTED_REGISTERED_ENVELOPE_BLOCKED,
        TARGET_OWNED_JSON_PRESERVED,
        OLDER_PROJECT_TRIGGERS_SCAN,
        UNKNOWN_SCRIPT_BLOCKED,
        RECORDS_ONLY_SCOPED,
        BROKEN_RUNTIME_COMPAT,
        BROKEN_SILENT_SKIP,
        BROKEN_UNKNOWN_REWRITE,
        BROKEN_CLASSIFIER_DELETED,
        BROKEN_NUMERIC_TARGET_JSON_REWRITE,
        BROKEN_PARTIAL_LEDGER_REWRITE,
        BROKEN_UNSUPPORTED_REGISTERED_ENVELOPE_REWRITE,
    )


def scenarios() -> tuple[Scenario, ...]:
    expected_violations = {
        BROKEN_RUNTIME_COMPAT.name: ("runtime_is_current_only",),
        BROKEN_SILENT_SKIP.name: ("older_project_runs_upgrade_scan",),
        BROKEN_UNKNOWN_REWRITE.name: ("unknown_script_blocks",),
        BROKEN_CLASSIFIER_DELETED.name: ("safety_classifier_survives_cleanup",),
        BROKEN_NUMERIC_TARGET_JSON_REWRITE.name: (
            "artifact_write_requires_exact_bounded_owner",
            "target_owned_json_is_byte_identical",
        ),
        BROKEN_PARTIAL_LEDGER_REWRITE.name: (
            "artifact_write_requires_exact_bounded_owner",
            "target_owned_json_is_byte_identical",
        ),
        BROKEN_UNSUPPORTED_REGISTERED_ENVELOPE_REWRITE.name: (
            "artifact_write_requires_exact_bounded_owner",
            "registered_envelopes_are_current_only",
        ),
    }
    workflow = build_workflow()
    checks = invariants()
    result = []
    for case in all_cases():
        if case.name in expected_violations:
            expectation = ScenarioExpectation(
                expected_status="violation",
                expected_violation_names=expected_violations[case.name],
                summary=f"VIOLATION; {expected_violations[case.name][0]}",
            )
        else:
            expectation = ScenarioExpectation(
                expected_status="ok",
                summary="OK; latest-schema upgrade policy boundary is preserved",
            )
        result.append(
            Scenario(
                name=case.name,
                description=f"Review latest-schema upgrade policy case {case.name}",
                initial_state=UpgradePolicyState(),
                external_input_sequence=(case,),
                expected=expectation,
                workflow=workflow,
                invariants=checks,
                tags=("latest_schema_upgrade_policy",),
            )
        )
    return tuple(result)


def run_latest_schema_upgrade_policy_review():
    return review_scenarios(scenarios())


__all__ = [
    "BROKEN_CLASSIFIER_DELETED",
    "BROKEN_NUMERIC_TARGET_JSON_REWRITE",
    "BROKEN_PARTIAL_LEDGER_REWRITE",
    "BROKEN_UNSUPPORTED_REGISTERED_ENVELOPE_REWRITE",
    "BROKEN_RUNTIME_COMPAT",
    "BROKEN_SILENT_SKIP",
    "BROKEN_UNKNOWN_REWRITE",
    "CURRENT_ARTIFACT",
    "LEGACY_BCL_ARTIFACT_UPGRADED",
    "OLDER_PROJECT_TRIGGERS_SCAN",
    "RECORDS_ONLY_SCOPED",
    "TARGET_OWNED_JSON_PRESERVED",
    "UNSUPPORTED_REGISTERED_ENVELOPE_BLOCKED",
    "UNKNOWN_SCRIPT_BLOCKED",
    "UpgradePolicyCase",
    "UpgradePolicyState",
    "all_cases",
    "build_workflow",
    "invariants",
    "run_latest_schema_upgrade_policy_review",
    "scenarios",
]

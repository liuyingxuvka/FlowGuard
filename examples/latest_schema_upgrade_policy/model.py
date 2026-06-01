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
    project_version_state: str = "current"
    upgrade_action: str = "not_run"
    runtime_accepts_old_shape: bool = False
    validation_status: str = "not_run"
    safety_classifier_preserved: bool = True
    blocked_unknowns_visible: bool = True
    records_only_scope_declared: bool = False


CURRENT_ARTIFACT = UpgradePolicyCase("current_artifact_passes")
KNOWN_OLD_ARTIFACT_UPGRADED = UpgradePolicyCase("known_old_artifact_upgraded")
OLDER_PROJECT_TRIGGERS_SCAN = UpgradePolicyCase("older_project_triggers_upgrade_scan")
UNKNOWN_SCRIPT_BLOCKED = UpgradePolicyCase("unknown_script_blocks")
RECORDS_ONLY_SCOPED = UpgradePolicyCase("records_only_scope_declared")
BROKEN_RUNTIME_COMPAT = UpgradePolicyCase("broken_runtime_accepts_old_shape")
BROKEN_SILENT_SKIP = UpgradePolicyCase("broken_older_project_skips_scan")
BROKEN_UNKNOWN_REWRITE = UpgradePolicyCase("broken_unknown_script_rewritten")
BROKEN_CLASSIFIER_DELETED = UpgradePolicyCase("broken_safety_classifier_deleted")


class ApplyUpgradePolicyCase:
    name = "ApplyUpgradePolicyCase"
    reads = ("case_name",)
    writes = (
        "case_name",
        "artifact_shape",
        "project_version_state",
        "upgrade_action",
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
            project_version_state="current",
            upgrade_action="unchanged",
            validation_status="route_evidence_required",
        )
    if case == KNOWN_OLD_ARTIFACT_UPGRADED:
        return UpgradePolicyState(
            case_name=case.name,
            artifact_shape="current",
            project_version_state="older",
            upgrade_action="deterministic_upgrade",
            validation_status="route_evidence_required",
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
        KNOWN_OLD_ARTIFACT_UPGRADED,
        OLDER_PROJECT_TRIGGERS_SCAN,
        UNKNOWN_SCRIPT_BLOCKED,
        RECORDS_ONLY_SCOPED,
        BROKEN_RUNTIME_COMPAT,
        BROKEN_SILENT_SKIP,
        BROKEN_UNKNOWN_REWRITE,
        BROKEN_CLASSIFIER_DELETED,
    )


def scenarios() -> tuple[Scenario, ...]:
    expected_violations = {
        BROKEN_RUNTIME_COMPAT.name: ("runtime_is_current_only",),
        BROKEN_SILENT_SKIP.name: ("older_project_runs_upgrade_scan",),
        BROKEN_UNKNOWN_REWRITE.name: ("unknown_script_blocks",),
        BROKEN_CLASSIFIER_DELETED.name: ("safety_classifier_survives_cleanup",),
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
    "BROKEN_RUNTIME_COMPAT",
    "BROKEN_SILENT_SKIP",
    "BROKEN_UNKNOWN_REWRITE",
    "CURRENT_ARTIFACT",
    "KNOWN_OLD_ARTIFACT_UPGRADED",
    "OLDER_PROJECT_TRIGGERS_SCAN",
    "RECORDS_ONLY_SCOPED",
    "UNKNOWN_SCRIPT_BLOCKED",
    "UpgradePolicyCase",
    "UpgradePolicyState",
    "all_cases",
    "build_workflow",
    "invariants",
    "run_latest_schema_upgrade_policy_review",
    "scenarios",
]

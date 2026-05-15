"""FlowGuard model for the pre-implementation model-hardening gate rollout.

Risk Purpose Header
-------------------
FlowGuard source: https://github.com/liuyingxuvka/FlowGuard

This model reviews the workflow for updating the `model-first-function-flow`
Skill so complex optimizations must prepare a change inventory, risk catalog,
risk-to-model coverage matrix, known-bad hazards, tiered heavy-check evidence,
peer-change preservation, and incremental validation before production edits.

It guards against these concrete bugs:
- An agent edits production code before the model can see the target risks.
- A model is trusted after only a happy-path run, without known-bad coverage.
- A generic skill hard-codes project-specific heavy model names as skippable.
- Peer/user changes are overwritten or stale evidence is reused after the
  workspace changed.
- A release is published before validation, sync, version, and changelog
  evidence exists.

Run with: `python examples/model_hardening_gate/run_checks.py`
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.review import review_scenario, review_scenarios
from flowguard.scenario import Scenario, ScenarioExpectation


@dataclass(frozen=True)
class State:
    change_inventory: bool = False
    risk_catalog: bool = False
    coverage_matrix: bool = False
    model_updated: bool = False
    known_bad_failures_observed: bool = False
    plan_replayed: bool = False
    focused_checks_passed: bool = False
    heavy_cost_policy_documented: bool = False
    hard_coded_project_model_names: bool = False
    heavy_check_touches_boundary: bool = False
    touched_heavy_evidence_present: bool = False
    deferred_heavy_boundary_recorded: bool = False
    background_artifacts_recorded: bool = False
    peer_changes_present: bool = False
    peer_changes_checked: bool = False
    peer_changes_preserved: bool = False
    stale_evidence_reused: bool = False
    production_edited: bool = False
    slice_validated: bool = False
    full_regression_passed: bool = False
    installed_skill_synced: bool = False
    shadow_workspace_synced: bool = False
    version_bumped: bool = False
    changelog_updated: bool = False
    release_published: bool = False


@dataclass(frozen=True)
class Event:
    name: str


WRITE_CHANGE_INVENTORY = Event("write_change_inventory")
WRITE_RISK_CATALOG = Event("write_risk_catalog")
WRITE_COVERAGE_MATRIX = Event("write_coverage_matrix")
UPDATE_MODEL = Event("update_model")
OBSERVE_KNOWN_BAD_FAILURES = Event("observe_known_bad_failures")
REPLAY_PLAN = Event("replay_plan")
RUN_FOCUSED_CHECKS = Event("run_focused_checks")
DOCUMENT_HEAVY_COST_POLICY = Event("document_heavy_cost_policy")
MARK_HEAVY_TOUCHES_BOUNDARY = Event("mark_heavy_touches_boundary")
RUN_TOUCHED_HEAVY_BACKGROUND = Event("run_touched_heavy_background")
DEFER_UNTOUCHED_HEAVY_WITH_NOTE = Event("defer_untouched_heavy_with_note")
RECORD_BACKGROUND_ARTIFACTS = Event("record_background_artifacts")
DETECT_PEER_CHANGES = Event("detect_peer_changes")
CHECK_AND_PRESERVE_PEER_CHANGES = Event("check_and_preserve_peer_changes")
EDIT_PRODUCTION = Event("edit_production")
VALIDATE_SLICE = Event("validate_slice")
RUN_FULL_REGRESSION = Event("run_full_regression")
SYNC_INSTALLED_SKILL = Event("sync_installed_skill")
SYNC_SHADOW_WORKSPACE = Event("sync_shadow_workspace")
BUMP_VERSION = Event("bump_version")
UPDATE_CHANGELOG = Event("update_changelog")
PUBLISH_RELEASE = Event("publish_release")


class ModelHardeningGateStep:
    name = "ModelHardeningGateStep"
    reads = tuple(State.__dataclass_fields__.keys())
    writes = reads
    accepted_input_type = Event
    input_description = "model-hardening rollout event"
    output_description = "updated rollout evidence state"
    idempotency = "repeated documentation and validation events keep evidence true without duplicating release effects"

    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "write_change_inventory":
            yield FunctionResult("change_inventory_written", replace(state, change_inventory=True), label="change_inventory")
            return
        if input_obj.name == "write_risk_catalog":
            yield FunctionResult("risk_catalog_written", replace(state, risk_catalog=True), label="risk_catalog")
            return
        if input_obj.name == "write_coverage_matrix":
            if not (state.change_inventory and state.risk_catalog):
                yield FunctionResult("coverage_waiting_for_inventory_and_risks", state, label="blocked")
                return
            yield FunctionResult("coverage_matrix_written", replace(state, coverage_matrix=True), label="coverage_matrix")
            return
        if input_obj.name == "update_model":
            if not state.coverage_matrix:
                yield FunctionResult("model_update_waiting_for_coverage_matrix", state, label="blocked")
                return
            yield FunctionResult("model_updated", replace(state, model_updated=True), label="model_updated")
            return
        if input_obj.name == "observe_known_bad_failures":
            if not state.model_updated:
                yield FunctionResult("known_bad_waiting_for_model", state, label="blocked")
                return
            yield FunctionResult(
                "known_bad_failures_observed",
                replace(state, known_bad_failures_observed=True),
                label="known_bad_failures",
            )
            return
        if input_obj.name == "replay_plan":
            if not state.known_bad_failures_observed:
                yield FunctionResult("plan_replay_waiting_for_known_bad_coverage", state, label="blocked")
                return
            yield FunctionResult("plan_replayed", replace(state, plan_replayed=True), label="plan_replayed")
            return
        if input_obj.name == "run_focused_checks":
            if not state.plan_replayed:
                yield FunctionResult("focused_checks_waiting_for_plan_replay", state, label="blocked")
                return
            yield FunctionResult("focused_checks_passed", replace(state, focused_checks_passed=True), label="focused_checks")
            return
        if input_obj.name == "document_heavy_cost_policy":
            yield FunctionResult(
                "heavy_cost_policy_documented",
                replace(state, heavy_cost_policy_documented=True),
                label="heavy_cost_policy",
            )
            return
        if input_obj.name == "mark_heavy_touches_boundary":
            yield FunctionResult(
                "heavy_boundary_marked",
                replace(state, heavy_check_touches_boundary=True),
                label="heavy_touches_boundary",
            )
            return
        if input_obj.name == "run_touched_heavy_background":
            if not state.heavy_check_touches_boundary:
                yield FunctionResult("heavy_run_not_required_for_untouched_boundary", state, label="blocked")
                return
            yield FunctionResult(
                "touched_heavy_evidence_present",
                replace(state, touched_heavy_evidence_present=True),
                label="touched_heavy_evidence",
            )
            return
        if input_obj.name == "defer_untouched_heavy_with_note":
            if state.heavy_check_touches_boundary:
                yield FunctionResult("cannot_defer_touched_heavy_without_evidence", state, label="blocked")
                return
            yield FunctionResult(
                "deferred_heavy_boundary_recorded",
                replace(state, deferred_heavy_boundary_recorded=True),
                label="deferred_heavy_boundary",
            )
            return
        if input_obj.name == "record_background_artifacts":
            yield FunctionResult(
                "background_artifacts_recorded",
                replace(state, background_artifacts_recorded=True),
                label="background_artifacts",
            )
            return
        if input_obj.name == "detect_peer_changes":
            yield FunctionResult("peer_changes_detected", replace(state, peer_changes_present=True), label="peer_changes_present")
            return
        if input_obj.name == "check_and_preserve_peer_changes":
            yield FunctionResult(
                "peer_changes_preserved",
                replace(state, peer_changes_checked=True, peer_changes_preserved=True),
                label="peer_changes_preserved",
            )
            return
        if input_obj.name == "edit_production":
            yield FunctionResult("production_edited", replace(state, production_edited=True), label="production_edited")
            return
        if input_obj.name == "validate_slice":
            if not state.production_edited:
                yield FunctionResult("slice_validation_waiting_for_edit", state, label="blocked")
                return
            yield FunctionResult("slice_validated", replace(state, slice_validated=True), label="slice_validated")
            return
        if input_obj.name == "run_full_regression":
            if not state.slice_validated:
                yield FunctionResult("full_regression_waiting_for_slice_validation", state, label="blocked")
                return
            yield FunctionResult("full_regression_passed", replace(state, full_regression_passed=True), label="full_regression")
            return
        if input_obj.name == "sync_installed_skill":
            if not state.full_regression_passed:
                yield FunctionResult("installed_sync_waiting_for_regression", state, label="blocked")
                return
            yield FunctionResult(
                "installed_skill_synced",
                replace(state, installed_skill_synced=True),
                label="installed_skill_synced",
            )
            return
        if input_obj.name == "sync_shadow_workspace":
            if not state.full_regression_passed:
                yield FunctionResult("shadow_sync_waiting_for_regression", state, label="blocked")
                return
            yield FunctionResult(
                "shadow_workspace_synced",
                replace(state, shadow_workspace_synced=True),
                label="shadow_workspace_synced",
            )
            return
        if input_obj.name == "bump_version":
            yield FunctionResult("version_bumped", replace(state, version_bumped=True), label="version_bumped")
            return
        if input_obj.name == "update_changelog":
            yield FunctionResult("changelog_updated", replace(state, changelog_updated=True), label="changelog_updated")
            return
        if input_obj.name == "publish_release":
            yield FunctionResult("release_published", replace(state, release_published=True), label="release_published")
            return
        yield FunctionResult("unknown_event", state, label="blocked")


class BrokenHappyPathOnlyStep(ModelHardeningGateStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "observe_known_bad_failures":
            yield FunctionResult("happy_path_only_claimed", state, label="broken_happy_path_only")
            return
        if input_obj.name == "replay_plan":
            yield FunctionResult("plan_replayed_without_known_bad", replace(state, plan_replayed=True), label="broken_plan_replayed")
            return
        yield from super().apply(input_obj, state)


class BrokenHardCodedHeavyStep(ModelHardeningGateStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "document_heavy_cost_policy":
            yield FunctionResult(
                "project_model_names_hard_coded",
                replace(state, heavy_cost_policy_documented=True, hard_coded_project_model_names=True),
                label="broken_hard_coded_heavy_models",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenTouchedHeavySkipStep(ModelHardeningGateStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "defer_untouched_heavy_with_note":
            yield FunctionResult(
                "touched_heavy_silently_deferred",
                replace(state, deferred_heavy_boundary_recorded=True),
                label="broken_touched_heavy_deferred",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenPeerOverwriteStep(ModelHardeningGateStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "check_and_preserve_peer_changes":
            yield FunctionResult(
                "stale_evidence_reused",
                replace(state, peer_changes_checked=True, stale_evidence_reused=True),
                label="broken_stale_evidence_reused",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenPrematureReleaseStep(ModelHardeningGateStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "publish_release":
            yield FunctionResult(
                "release_published_without_sync",
                replace(state, release_published=True),
                label="broken_release_published",
            )
            return
        yield from super().apply(input_obj, state)


def gate_ready(state: State) -> bool:
    return (
        state.change_inventory
        and state.risk_catalog
        and state.coverage_matrix
        and state.model_updated
        and state.known_bad_failures_observed
        and state.plan_replayed
        and state.focused_checks_passed
        and state.heavy_cost_policy_documented
        and (state.deferred_heavy_boundary_recorded or state.touched_heavy_evidence_present)
        and not state.hard_coded_project_model_names
    )


def release_ready(state: State) -> bool:
    return (
        state.full_regression_passed
        and state.installed_skill_synced
        and state.shadow_workspace_synced
        and state.version_bumped
        and state.changelog_updated
    )


def invariants() -> tuple[Invariant, ...]:
    def production_waits_for_gate(state: State, _trace: object) -> InvariantResult:
        if state.production_edited and not gate_ready(state):
            return InvariantResult.fail("production edit happened before inventory, risk, coverage, model, known-bad, focused, and heavy-check evidence")
        return InvariantResult.pass_()

    def known_bad_required(state: State, _trace: object) -> InvariantResult:
        if state.plan_replayed and not state.known_bad_failures_observed:
            return InvariantResult.fail("plan replay or model trust happened without known-bad hazard failures")
        return InvariantResult.pass_()

    def no_hard_coded_heavy_names(state: State, _trace: object) -> InvariantResult:
        if state.hard_coded_project_model_names:
            return InvariantResult.fail("generic skill hard-coded project-specific heavy model names")
        return InvariantResult.pass_()

    def touched_heavy_requires_evidence(state: State, _trace: object) -> InvariantResult:
        if state.heavy_check_touches_boundary and state.deferred_heavy_boundary_recorded and not state.touched_heavy_evidence_present:
            return InvariantResult.fail("heavy model that owns the touched boundary was skipped without evidence or blocker")
        return InvariantResult.pass_()

    def peer_changes_preserved(state: State, _trace: object) -> InvariantResult:
        if state.production_edited and state.peer_changes_present and not (
            state.peer_changes_checked and state.peer_changes_preserved
        ):
            return InvariantResult.fail("production edit proceeded without preserving peer/user changes")
        if state.stale_evidence_reused:
            return InvariantResult.fail("stale model or test evidence was reused after workspace changes")
        return InvariantResult.pass_()

    def release_waits_for_sync_and_version(state: State, _trace: object) -> InvariantResult:
        if state.release_published and not release_ready(state):
            return InvariantResult.fail("release published before regression, install sync, shadow sync, version, and changelog evidence")
        return InvariantResult.pass_()

    return (
        Invariant("production_waits_for_gate", "Production edits wait for full model-hardening evidence.", production_waits_for_gate),
        Invariant("known_bad_required", "Models cannot be trusted from happy-path checks alone.", known_bad_required),
        Invariant("no_hard_coded_heavy_names", "The generic Skill must not hard-code project-specific heavy model names.", no_hard_coded_heavy_names),
        Invariant("touched_heavy_requires_evidence", "Touched heavy boundaries need evidence, sharding, or an explicit blocker.", touched_heavy_requires_evidence),
        Invariant("peer_changes_preserved", "Peer or user edits must be preserved and stale evidence rejected.", peer_changes_preserved),
        Invariant("release_waits_for_sync_and_version", "Publication waits for validation, sync, version, and changelog evidence.", release_waits_for_sync_and_version),
    )


def workflow(block: object | None = None) -> Workflow:
    return Workflow((block or ModelHardeningGateStep(),), name="model_hardening_gate_rollout")


def scenario(
    *,
    name: str,
    description: str,
    events: tuple[Event, ...],
    expected: ScenarioExpectation,
    block: object | None = None,
) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        initial_state=State(),
        external_input_sequence=events,
        expected=expected,
        workflow=workflow(block),
        invariants=invariants(),
    )


CORRECT_UNTOUCHED_HEAVY_EVENTS = (
    WRITE_CHANGE_INVENTORY,
    WRITE_RISK_CATALOG,
    WRITE_COVERAGE_MATRIX,
    UPDATE_MODEL,
    OBSERVE_KNOWN_BAD_FAILURES,
    REPLAY_PLAN,
    RUN_FOCUSED_CHECKS,
    DOCUMENT_HEAVY_COST_POLICY,
    DEFER_UNTOUCHED_HEAVY_WITH_NOTE,
    RECORD_BACKGROUND_ARTIFACTS,
    DETECT_PEER_CHANGES,
    CHECK_AND_PRESERVE_PEER_CHANGES,
    EDIT_PRODUCTION,
    VALIDATE_SLICE,
    RUN_FULL_REGRESSION,
    SYNC_INSTALLED_SKILL,
    SYNC_SHADOW_WORKSPACE,
    BUMP_VERSION,
    UPDATE_CHANGELOG,
    PUBLISH_RELEASE,
)

CORRECT_TOUCHED_HEAVY_EVENTS = (
    WRITE_CHANGE_INVENTORY,
    WRITE_RISK_CATALOG,
    WRITE_COVERAGE_MATRIX,
    UPDATE_MODEL,
    OBSERVE_KNOWN_BAD_FAILURES,
    REPLAY_PLAN,
    RUN_FOCUSED_CHECKS,
    DOCUMENT_HEAVY_COST_POLICY,
    MARK_HEAVY_TOUCHES_BOUNDARY,
    RUN_TOUCHED_HEAVY_BACKGROUND,
    RECORD_BACKGROUND_ARTIFACTS,
    EDIT_PRODUCTION,
    VALIDATE_SLICE,
    RUN_FULL_REGRESSION,
    SYNC_INSTALLED_SKILL,
    SYNC_SHADOW_WORKSPACE,
    BUMP_VERSION,
    UPDATE_CHANGELOG,
    PUBLISH_RELEASE,
)


def correct_rollout_report():
    return review_scenarios(
        (
            scenario(
                name="correct_gate_with_untouched_heavy_checks",
                description="Complex work records risks, proves known-bad coverage, defers an untouched heavy model with a boundary note, preserves peer changes, and releases after sync.",
                events=CORRECT_UNTOUCHED_HEAVY_EVENTS,
                expected=ScenarioExpectation(
                    expected_status="ok",
                    required_trace_labels=("release_published",),
                    summary="model-hardening gate completes with deferred untouched heavy checks",
                ),
            ),
            scenario(
                name="correct_gate_with_touched_heavy_checks",
                description="Complex work runs touched heavy checks in the background before editing and publishing.",
                events=CORRECT_TOUCHED_HEAVY_EVENTS,
                expected=ScenarioExpectation(
                    expected_status="ok",
                    required_trace_labels=("release_published",),
                    summary="model-hardening gate completes with touched heavy evidence",
                ),
            ),
        )
    )


def broken_rollout_report():
    return review_scenarios(
        (
            scenario(
                name="code_first_change",
                description="An agent edits production code before inventory, risk, model, and known-bad evidence exist.",
                events=(EDIT_PRODUCTION,),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("production_waits_for_gate",),
                    summary="code-first changes are rejected",
                ),
            ),
            scenario(
                name="happy_path_only_model_trust",
                description="The model replay is trusted without a known-bad hazard failure.",
                events=(
                    WRITE_CHANGE_INVENTORY,
                    WRITE_RISK_CATALOG,
                    WRITE_COVERAGE_MATRIX,
                    UPDATE_MODEL,
                    OBSERVE_KNOWN_BAD_FAILURES,
                    REPLAY_PLAN,
                ),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("known_bad_required",),
                    summary="happy-path-only model checks are rejected",
                ),
                block=BrokenHappyPathOnlyStep(),
            ),
            scenario(
                name="hard_coded_heavy_model_names",
                description="The generic Skill hard-codes current-project heavy model names as skippable.",
                events=(DOCUMENT_HEAVY_COST_POLICY,),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("no_hard_coded_heavy_names",),
                    summary="project-specific heavy model names stay out of the generic Skill",
                ),
                block=BrokenHardCodedHeavyStep(),
            ),
            scenario(
                name="touched_heavy_model_skipped",
                description="A heavy model owns the touched boundary but is deferred as though it were unrelated.",
                events=(MARK_HEAVY_TOUCHES_BOUNDARY, DEFER_UNTOUCHED_HEAVY_WITH_NOTE),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("touched_heavy_requires_evidence",),
                    summary="touched heavy boundaries need evidence or a blocker",
                ),
                block=BrokenTouchedHeavySkipStep(),
            ),
            scenario(
                name="peer_changes_overwritten",
                description="Peer changes are detected, stale evidence is reused, and production edits continue.",
                events=(
                    WRITE_CHANGE_INVENTORY,
                    WRITE_RISK_CATALOG,
                    WRITE_COVERAGE_MATRIX,
                    UPDATE_MODEL,
                    OBSERVE_KNOWN_BAD_FAILURES,
                    REPLAY_PLAN,
                    RUN_FOCUSED_CHECKS,
                    DOCUMENT_HEAVY_COST_POLICY,
                    DEFER_UNTOUCHED_HEAVY_WITH_NOTE,
                    DETECT_PEER_CHANGES,
                    CHECK_AND_PRESERVE_PEER_CHANGES,
                    EDIT_PRODUCTION,
                ),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("peer_changes_preserved",),
                    summary="peer/user changes must be preserved and stale evidence rejected",
                ),
                block=BrokenPeerOverwriteStep(),
            ),
            scenario(
                name="premature_release",
                description="The release is published before regression, sync, version, and changelog evidence.",
                events=(PUBLISH_RELEASE,),
                expected=ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("release_waits_for_sync_and_version",),
                    summary="release waits for validation and sync evidence",
                ),
                block=BrokenPrematureReleaseStep(),
            ),
        )
    )


def main() -> int:
    correct = correct_rollout_report()
    broken = broken_rollout_report()
    print(correct.format_text(max_counterexamples=1))
    print()
    print(broken.format_text(max_counterexamples=2))
    return 0 if correct.ok and broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

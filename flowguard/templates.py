"""Reusable project template content for model-first flowguard adoption."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .project_adoption import build_flowguard_agents_block, current_project_manifest_text


@dataclass(frozen=True)
class TemplateFile:
    path: str
    content: str


MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Models a sample validate-and-store workflow before related production changes.

Guards against:
- duplicate item storage when the same input is repeated;
- invalid inputs being stored as accepted records;
- stored outputs that cannot be traced to an Accepted output.

Use before editing:
validation, deduplication, storage, retry, or state-transition logic.

Run:
python run_checks.py

Replace this sample domain with the workflow under review.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class Input:
    item_id: str
    valid: bool


@dataclass(frozen=True)
class Accepted:
    item_id: str


@dataclass(frozen=True)
class Rejected:
    item_id: str
    reason: str


@dataclass(frozen=True)
class Stored:
    item_id: str


@dataclass(frozen=True)
class State:
    seen_ids: tuple[str, ...] = ()
    stored_ids: tuple[str, ...] = ()


class ValidateInput:
    name = "ValidateInput"
    reads = ("seen_ids",)
    writes = ("seen_ids",)
    accepted_input_type = Input
    input_description = "external abstract input"
    output_description = "Accepted or Rejected"
    idempotency = "Repeated item_id returns Rejected('duplicate') without changing state."

    def apply(self, input_obj: Input, state: State) -> Iterable[FunctionResult]:
        if not input_obj.valid:
            yield FunctionResult(
                output=Rejected(input_obj.item_id, "invalid"),
                new_state=state,
                label="rejected_invalid",
            )
            return
        if input_obj.item_id in state.seen_ids:
            yield FunctionResult(
                output=Rejected(input_obj.item_id, "duplicate"),
                new_state=state,
                label="rejected_duplicate",
            )
            return
        yield FunctionResult(
            output=Accepted(input_obj.item_id),
            new_state=replace(state, seen_ids=state.seen_ids + (input_obj.item_id,)),
            label="accepted",
        )


class StoreAccepted:
    name = "StoreAccepted"
    reads = ("stored_ids",)
    writes = ("stored_ids",)
    accepted_input_type = Accepted
    input_description = "Accepted"
    output_description = "Stored"
    idempotency = "Stores each accepted item once."

    def apply(self, input_obj: Accepted, state: State) -> Iterable[FunctionResult]:
        if input_obj.item_id in state.stored_ids:
            yield FunctionResult(
                output=Stored(input_obj.item_id),
                new_state=state,
                label="already_stored",
            )
            return
        yield FunctionResult(
            output=Stored(input_obj.item_id),
            new_state=replace(state, stored_ids=state.stored_ids + (input_obj.item_id,)),
            label="stored",
        )


def terminal_predicate(current_output, state, trace) -> bool:
    del state, trace
    return isinstance(current_output, Rejected)


def no_duplicate_stores(state: State, trace) -> InvariantResult:
    del trace
    if len(state.stored_ids) != len(set(state.stored_ids)):
        return InvariantResult.fail("stored_ids contains duplicates")
    return InvariantResult.pass_()


def every_store_was_accepted(state: State, trace) -> InvariantResult:
    del state
    accepted = {
        step.function_output.item_id
        for step in trace.steps
        if step.label == "accepted" and isinstance(step.function_output, Accepted)
    }
    stored = {
        step.function_output.item_id
        for step in trace.steps
        if step.label == "stored" and isinstance(step.function_output, Stored)
    }
    missing = tuple(sorted(stored - accepted))
    if missing:
        return InvariantResult.fail(f"stored without accepted source: {missing!r}")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        name="no_duplicate_stores",
        description="stored_ids contains each item at most once",
        predicate=no_duplicate_stores,
    ),
    Invariant(
        name="every_store_was_accepted",
        description="Stored outputs must be traceable to Accepted outputs",
        predicate=every_store_was_accepted,
    ),
)


EXTERNAL_INPUTS = (
    Input("item_a", True),
    Input("item_bad", False),
)

MAX_SEQUENCE_LENGTH = 2


def initial_state() -> State:
    return State()


def build_workflow() -> Workflow:
    return Workflow((ValidateInput(), StoreAccepted()), name="model_template")


__all__ = [
    "EXTERNAL_INPUTS",
    "INVARIANTS",
    "MAX_SEQUENCE_LENGTH",
    "Accepted",
    "Input",
    "Rejected",
    "State",
    "Stored",
    "build_workflow",
    "initial_state",
    "terminal_predicate",
]
'''


RUN_CHECKS_TEMPLATE = '''"""Run the minimal model_template checks."""

from __future__ import annotations

from flowguard import Explorer
import model


def main() -> int:
    report = Explorer(
        workflow=model.build_workflow(),
        initial_states=(model.initial_state(),),
        external_inputs=model.EXTERNAL_INPUTS,
        invariants=model.INVARIANTS,
        max_sequence_length=model.MAX_SEQUENCE_LENGTH,
        terminal_predicate=model.terminal_predicate,
        required_labels=("stored", "rejected_duplicate"),
    ).explore()
    print(report.format_text())
    labels = sorted({label for trace in report.traces for label in trace.labels})
    print("labels: " + ",".join(labels))
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


MAINTENANCE_WORKFLOW_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Models a recurring multi-role maintenance workflow for agent systems before
changing automation or publication behavior.

Guards against:
- duplicate maintenance actions when the same input is repeated;
- completion without required reports or executable evidence;
- publishing before install/runtime sync or treating skipped steps as pass.

Use before editing:
Sleep/Dream/Architect/Installer/Reviewer-style maintenance, automation,
publication, adoption-log, or sync workflows.

Run:
python .flowguard/maintenance_workflow/run_checks.py

Rename the roles and state fields to match the project under review.
"""

from dataclasses import dataclass

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class MaintenanceInput:
    change_id: str
    action_id: str
    version: str = "v1"
    has_report: bool = True
    install_synced: bool = True


@dataclass(frozen=True)
class MaintenanceState:
    actions: tuple[str, ...] = ()
    observations: tuple[str, ...] = ()
    reports: tuple[str, ...] = ()
    installed_changes: tuple[str, ...] = ()
    published_changes: tuple[str, ...] = ()
    adoption_statuses: tuple[tuple[str, str], ...] = ()
    skipped_steps: tuple[tuple[str, str], ...] = ()


def _action_key(input_obj):
    return f"{input_obj.change_id}:{input_obj.action_id}"


def _report_id(input_obj):
    return f"{input_obj.change_id}:report"


def _observation_id(input_obj):
    return f"{input_obj.change_id}:observation"


def _append_once(values, value):
    return values if value in values else values + (value,)


def _upsert_status(statuses, change_id, status):
    return tuple(item for item in statuses if item[0] != change_id) + ((change_id, status),)


def _status_for(state, change_id):
    for existing_change_id, status in reversed(state.adoption_statuses):
        if existing_change_id == change_id:
            return status
    return ""


class SleepRole:
    name = "SleepRole"
    reads = ("actions",)
    writes = ("actions",)
    input_description = "MaintenanceInput"
    output_description = "MaintenanceInput"
    idempotency = "same action_id is applied at most once per change"
    accepted_input_type = MaintenanceInput

    def apply(self, input_obj, state):
        action_key = _action_key(input_obj)
        if action_key in state.actions:
            return (FunctionResult(input_obj, state, label="sleep_action_already_done"),)
        return (
            FunctionResult(
                input_obj,
                MaintenanceState(**{**state.__dict__, "actions": state.actions + (action_key,)}),
                label="sleep_action_done",
            ),
        )


class BrokenSleepRole:
    name = "BrokenSleepRole"
    reads = ("actions",)
    writes = ("actions",)
    accepted_input_type = MaintenanceInput

    def apply(self, input_obj, state):
        return (
            FunctionResult(
                input_obj,
                MaintenanceState(**{**state.__dict__, "actions": state.actions + (_action_key(input_obj),)}),
                label="broken_sleep_duplicate_action",
            ),
        )


class DreamRole:
    name = "DreamRole"
    reads = ("actions", "observations")
    writes = ("observations",)
    input_description = "MaintenanceInput"
    output_description = "MaintenanceInput"
    idempotency = "same observation is recorded at most once"
    accepted_input_type = MaintenanceInput

    def apply(self, input_obj, state):
        observation_id = _observation_id(input_obj)
        return (
            FunctionResult(
                input_obj,
                MaintenanceState(
                    **{**state.__dict__, "observations": _append_once(state.observations, observation_id)}
                ),
                label="dream_observation_recorded",
            ),
        )


class ArchitectRole:
    name = "ArchitectRole"
    reads = ("observations", "reports")
    writes = ("reports",)
    input_description = "MaintenanceInput"
    output_description = "MaintenanceInput"
    idempotency = "same report is recorded at most once"
    accepted_input_type = MaintenanceInput

    def apply(self, input_obj, state):
        if not input_obj.has_report:
            return (FunctionResult(input_obj, state, label="architect_missing_report"),)
        report_id = _report_id(input_obj)
        return (
            FunctionResult(
                input_obj,
                MaintenanceState(**{**state.__dict__, "reports": _append_once(state.reports, report_id)}),
                label="architect_report_recorded",
            ),
        )


class InstallerRole:
    name = "InstallerRole"
    reads = ("reports", "installed_changes")
    writes = ("installed_changes",)
    input_description = "MaintenanceInput"
    output_description = "MaintenanceInput"
    idempotency = "same change is installed at most once"
    accepted_input_type = MaintenanceInput

    def apply(self, input_obj, state):
        if _report_id(input_obj) not in state.reports:
            return (FunctionResult(input_obj, state, label="install_waiting_for_report"),)
        if not input_obj.install_synced:
            return (FunctionResult(input_obj, state, label="install_not_synced"),)
        return (
            FunctionResult(
                input_obj,
                MaintenanceState(
                    **{**state.__dict__, "installed_changes": _append_once(state.installed_changes, input_obj.change_id)}
                ),
                label="install_synced",
            ),
        )


class ReviewerRole:
    name = "ReviewerRole"
    reads = ("reports", "installed_changes", "adoption_statuses")
    writes = ("adoption_statuses",)
    input_description = "MaintenanceInput"
    output_description = "MaintenanceInput"
    idempotency = "same change has one final adoption status"
    accepted_input_type = MaintenanceInput

    def apply(self, input_obj, state):
        status = (
            "completed"
            if _report_id(input_obj) in state.reports and input_obj.change_id in state.installed_changes
            else "blocked"
        )
        return (
            FunctionResult(
                input_obj,
                MaintenanceState(
                    **{**state.__dict__, "adoption_statuses": _upsert_status(state.adoption_statuses, input_obj.change_id, status)}
                ),
                label=f"review_{status}",
            ),
        )


class BrokenReviewerRole:
    name = "BrokenReviewerRole"
    reads = ("adoption_statuses",)
    writes = ("adoption_statuses",)
    accepted_input_type = MaintenanceInput

    def apply(self, input_obj, state):
        return (
            FunctionResult(
                input_obj,
                MaintenanceState(
                    **{**state.__dict__, "adoption_statuses": _upsert_status(state.adoption_statuses, input_obj.change_id, "completed")}
                ),
                label="broken_review_completed_without_evidence",
            ),
        )


class PublisherRole:
    name = "PublisherRole"
    reads = ("installed_changes", "adoption_statuses", "published_changes")
    writes = ("published_changes",)
    input_description = "MaintenanceInput"
    output_description = "MaintenanceInput"
    idempotency = "same change is published at most once after install"
    accepted_input_type = MaintenanceInput

    def apply(self, input_obj, state):
        if _status_for(state, input_obj.change_id) != "completed":
            return (FunctionResult(input_obj, state, label="publish_blocked"),)
        if input_obj.change_id not in state.installed_changes:
            return (FunctionResult(input_obj, state, label="publish_waiting_for_install"),)
        return (
            FunctionResult(
                input_obj,
                MaintenanceState(
                    **{**state.__dict__, "published_changes": _append_once(state.published_changes, input_obj.change_id)}
                ),
                label="publish_allowed",
            ),
        )


class BrokenPublisherRole:
    name = "BrokenPublisherRole"
    reads = ("published_changes",)
    writes = ("published_changes",)
    accepted_input_type = MaintenanceInput

    def apply(self, input_obj, state):
        return (
            FunctionResult(
                input_obj,
                MaintenanceState(
                    **{**state.__dict__, "published_changes": _append_once(state.published_changes, input_obj.change_id)}
                ),
                label="broken_publish_without_install_sync",
            ),
        )


def _duplicates(values):
    seen = set()
    duplicates = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return tuple(duplicates)


def no_duplicate_maintenance_actions():
    def predicate(state, _trace):
        duplicates = _duplicates(state.actions)
        if duplicates:
            return InvariantResult.fail(
                f"duplicate maintenance actions: {duplicates!r}",
                {"duplicate_actions": duplicates},
            )
        return InvariantResult.pass_()

    return Invariant(
        "no_duplicate_maintenance_actions",
        "Repeated maintenance runs should not duplicate side effects.",
        predicate,
        metadata={"property_classes": ("idempotency", "side_effect", "at_most_once")},
    )


def completed_requires_report():
    def predicate(state, _trace):
        bad = tuple(
            change_id
            for change_id, status in state.adoption_statuses
            if status == "completed" and f"{change_id}:report" not in state.reports
        )
        if bad:
            return InvariantResult.fail(
                f"completed maintenance changes without report: {bad!r}",
                {"changes_without_report": bad},
            )
        return InvariantResult.pass_()

    return Invariant(
        "completed_requires_report",
        "Architect/Reviewer cannot mark completion without report evidence.",
        predicate,
        metadata={"property_classes": ("reporting", "module_boundary")},
    )


def completed_requires_install_sync():
    def predicate(state, _trace):
        bad = tuple(
            change_id
            for change_id, status in state.adoption_statuses
            if status == "completed" and change_id not in state.installed_changes
        )
        if bad:
            return InvariantResult.fail(
                f"completed maintenance changes without install sync: {bad!r}",
                {"changes_without_install": bad},
            )
        return InvariantResult.pass_()

    return Invariant(
        "completed_requires_install_sync",
        "Completion requires installed/runtime copy to be synchronized.",
        predicate,
        metadata={"property_classes": ("conformance", "module_boundary")},
    )


def published_requires_install_sync():
    def predicate(state, _trace):
        bad = tuple(change_id for change_id in state.published_changes if change_id not in state.installed_changes)
        if bad:
            return InvariantResult.fail(
                f"published changes without install sync: {bad!r}",
                {"published_without_install": bad},
            )
        return InvariantResult.pass_()

    return Invariant(
        "published_requires_install_sync",
        "Publishing requires the installed/runtime copy to be synchronized first.",
        predicate,
        metadata={"property_classes": ("conformance", "module_boundary")},
    )


def maintenance_invariants():
    return (
        no_duplicate_maintenance_actions(),
        completed_requires_report(),
        completed_requires_install_sync(),
        published_requires_install_sync(),
    )


def build_workflow(
    *,
    sleep_block=None,
    dream_block=None,
    architect_block=None,
    installer_block=None,
    reviewer_block=None,
    publisher_block=None,
):
    return Workflow(
        (
            sleep_block or SleepRole(),
            dream_block or DreamRole(),
            architect_block or ArchitectRole(),
            installer_block or InstallerRole(),
            reviewer_block or ReviewerRole(),
            publisher_block or PublisherRole(),
        ),
        name="maintenance_workflow",
    )
'''


MAINTENANCE_WORKFLOW_RUN_CHECKS_TEMPLATE = '''"""Run the maintenance workflow template checks."""

from flowguard import Explorer

from model import (
    BrokenPublisherRole,
    BrokenReviewerRole,
    BrokenSleepRole,
    MaintenanceInput,
    MaintenanceState,
    build_workflow,
    maintenance_invariants,
)


def run_case(name, workflow, inputs, expected_ok, max_sequence_length=1):
    report = Explorer(
        workflow=workflow,
        initial_states=(MaintenanceState(),),
        external_inputs=inputs,
        invariants=maintenance_invariants(),
        max_sequence_length=max_sequence_length,
    ).explore()
    observed = "OK" if report.ok else "VIOLATION"
    print(f"{name}: {observed}")
    if report.ok != expected_ok:
        print(report.format_text(max_counterexamples=1))
        return False
    return True


def main():
    normal = MaintenanceInput("change-1", "translate-card", "skill-v2")
    missing_report = MaintenanceInput("change-2", "architect-review", "skill-v2", has_report=False)
    unsynced_install = MaintenanceInput("change-3", "install-sync", "skill-v2", install_synced=False)

    cases = (
        ("correct_maintenance_workflow", build_workflow(), (normal,), True, 2),
        (
            "broken_duplicate_sleep_action",
            build_workflow(sleep_block=BrokenSleepRole()),
            (normal,),
            False,
            2,
        ),
        (
            "broken_completed_without_report",
            build_workflow(reviewer_block=BrokenReviewerRole()),
            (missing_report,),
            False,
            1,
        ),
        (
            "broken_publish_without_install_sync",
            build_workflow(publisher_block=BrokenPublisherRole()),
            (unsynced_install,),
            False,
            1,
        ),
    )
    ok = all(run_case(*case) for case in cases)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


MAINTENANCE_WORKFLOW_NOTES_TEMPLATE = """# FlowGuard Maintenance Workflow Notes

Use this scaffold for recurring multi-role maintenance systems, such as
Sleep/Dream/Architect/Installer/Reviewer flows.

## Boundary

Describe the maintenance loop and the artifact being changed.

## Roles

- Sleep or maintenance executor
- Dream or observation/proposal generator
- Architect or report/decision maker
- Installer or runtime synchronization step
- Reviewer or final evidence checker
- Publisher or release/activation step

## Default Risks

- duplicate maintenance actions on repeated runs;
- completion without a report;
- publishing before install/runtime sync;
- skipped steps being treated as pass;
- adoption logs replacing executable checks.

## Calibration

Rename the state fields and roles to match the project. Keep skipped checks
visible and record whether confidence is model-level or production-facing.
"""


ADOPTION_LOG_TEMPLATE = """# flowguard Adoption Log

Use this file to keep a human-readable record of model-first work in this
project. Keep machine-readable entries in `.flowguard/adoption_log.jsonl` when
automation is available.

Each entry should record:

- task id;
- task summary;
- trigger reason;
- status: `in_progress`, `completed`, `blocked`, `skipped_with_reason`, or `failed`;
- model files touched;
- checks run;
- elapsed time;
- findings and counterexamples;
- skipped steps and reasons;
- risk evidence ledger summary for final confidence claims;
- friction points;
- next actions.

Do not use this log as a substitute for executable flowguard checks.
Do not treat `in_progress`, `blocked`, `skipped_with_reason`, or `failed` as
successful completion.
"""


MODEL_NOTES_TEMPLATE = """# flowguard Model Notes

## Scope

Describe the workflow boundary being modeled.

## Function Blocks

List each function block as `Input x State -> Set(Output x State)`.

## Invariants

List hard invariants that must not be weakened to pass checks.

## Scenario Review

Record expected-vs-observed scenario outcomes and counterexamples.

## Conformance Replay

Record production adapters, projection decisions, and replay outcomes.

## Known Limits

Record `needs_human_review` and known limitations honestly.
"""


RISK_INTENT_CHECK_PLAN_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Models a sample item-acceptance workflow with an explicit Risk Intent before
related production changes.

Guards against:
- duplicate acceptance after retries;
- invalid item requests being accepted;
- skipped conformance gaps being hidden as full production confidence.

Use before editing:
acceptance, deduplication, idempotency, side-effect, or confidence-reporting
logic.

Run:
python .flowguard/risk_intent_check_plan/run_checks.py

Replace this sample item workflow with the current behavior under review.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import (
    FlowGuardCheckPlan,
    FunctionResult,
    Invariant,
    InvariantResult,
    RiskIntent,
    RiskProfile,
    SkippedCheck,
    Workflow,
    run_model_first_checks,
)


@dataclass(frozen=True)
class ItemInput:
    item_id: str
    should_accept: bool = True


@dataclass(frozen=True)
class Accepted:
    item_id: str


@dataclass(frozen=True)
class Rejected:
    item_id: str
    reason: str


@dataclass(frozen=True)
class State:
    accepted_ids: tuple[str, ...] = ()


class AcceptItem:
    name = "AcceptItem"
    reads = ("accepted_ids",)
    writes = ("accepted_ids",)
    accepted_input_type = ItemInput
    input_description = "item request"
    output_description = "Accepted or Rejected"
    idempotency = "Repeated item_id is rejected as a duplicate."

    def apply(self, input_obj: ItemInput, state: State) -> Iterable[FunctionResult]:
        if not input_obj.should_accept:
            yield FunctionResult(Rejected(input_obj.item_id, "not_allowed"), state, label="rejected")
            return
        if input_obj.item_id in state.accepted_ids:
            yield FunctionResult(Rejected(input_obj.item_id, "duplicate"), state, label="rejected_duplicate")
            return
        yield FunctionResult(
            Accepted(input_obj.item_id),
            replace(state, accepted_ids=state.accepted_ids + (input_obj.item_id,)),
            label="accepted",
        )


def no_duplicate_accepts(state: State, _trace) -> InvariantResult:
    if len(state.accepted_ids) != len(set(state.accepted_ids)):
        return InvariantResult.fail("accepted_ids contains duplicates")
    return InvariantResult.pass_()


def risk_profile() -> RiskProfile:
    return RiskProfile(
        modeled_boundary="sample item acceptance",
        risk_classes=("deduplication", "idempotency", "side_effect"),
        risk_intent=RiskIntent(
            failure_modes=("duplicate acceptance after retry", "invalid item accepted"),
            protected_harms=("downstream workflow acts on the same item twice",),
            must_model_state=("accepted_ids",),
            adversarial_inputs=("same item repeated", "invalid item request"),
            hard_invariants=("one acceptance per item",),
            blindspots=("real storage isolation requires a conformance replay adapter"),
        ),
        confidence_goal="model_level",
        skipped_checks=(
            SkippedCheck("conformance_replay", "no production adapter exists in this starter template"),
        ),
    )


def build_workflow() -> Workflow:
    return Workflow((AcceptItem(),), name="risk_intent_template")


def build_check_plan() -> FlowGuardCheckPlan:
    return FlowGuardCheckPlan(
        workflow=build_workflow(),
        initial_states=(State(),),
        external_inputs=(ItemInput("item-1"), ItemInput("item-1"), ItemInput("item-bad", False)),
        invariants=(
            Invariant(
                "no_duplicate_accepts",
                "accepted_ids contains each item at most once",
                no_duplicate_accepts,
                metadata={"property_classes": ("deduplication", "idempotency")},
            ),
        ),
        max_sequence_length=2,
        risk_profile=risk_profile(),
    )


def run_checks():
    return run_model_first_checks(build_check_plan())
'''


RISK_INTENT_CHECK_PLAN_RUN_CHECKS_TEMPLATE = '''"""Run the Risk Intent + CheckPlan template."""

from model import risk_profile, run_checks


def main() -> int:
    print(f"risk_intent: {risk_profile().modeled_boundary}")
    report = run_checks()
    print(report.format_text())
    return 0 if report.overall_status in {"pass", "pass_with_gaps"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


RISK_INTENT_CHECK_PLAN_NOTES_TEMPLATE = """# FlowGuard Risk Intent CheckPlan Notes

Use this scaffold when the main risk should be named before modeling.

## Risk Intent

Record:

- failure modes;
- protected harms;
- state and side effects that must be visible;
- adversarial inputs or retries;
- hard invariants;
- blindspots.

## Calibration

This template reports model-level confidence only. Add conformance replay or
equivalent real-code evidence before claiming production confidence.
"""


MODEL_MISS_REVIEW_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Models the review loop required when a FlowGuard pass is followed by a test,
runtime, replay, or manual-validation failure.

Guards against:
- finalizing after a runtime issue without classifying the model miss;
- validating a fix before representing the observed issue in the model;
- validating a point fix before representing a same-class generalized bad case;
- validating only the observed bug without same-class test evidence;
- treating a recurring same-class miss as another ordinary point fix;
- using the known bug as the whole model target instead of holdout evidence;
- treating a later green runtime check as enough to close a known miss.

Use before editing:
bug-fix, model-miss, runtime-validation, replay, or completion-gate logic after
FlowGuard already passed.

Run:
python .flowguard/model_miss_review/run_checks.py

Replace the event names and obligations with the bug class under review.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.review import review_scenario, review_scenarios
from flowguard.scenario import Scenario, ScenarioExpectation


@dataclass(frozen=True)
class State:
    flowguard_passed: bool = False
    runtime_issue_observed: bool = False
    model_miss_classified: bool = False
    issue_represented_in_model: bool = False
    generalized_bad_case_in_scope: bool = True
    generalized_bad_case_represented_in_model: bool = False
    known_bug_used_as_holdout: bool = False
    observed_regression_test_added: bool = False
    same_class_test_evidence_added: bool = False
    model_test_alignment_rerun: bool = False
    recurring_family_detected: bool = False
    defect_family_gate_promoted: bool = False
    defect_family_gate_reviewed: bool = False
    fix_validated_after_refinement: bool = False
    completed: bool = False


@dataclass(frozen=True)
class Event:
    name: str


FLOWGUARD_PASS = Event("flowguard_pass")
RUNTIME_FAIL = Event("runtime_fail")
CLASSIFY_MISS = Event("classify_miss")
REPRESENT_ISSUE = Event("represent_issue")
REPRESENT_GENERALIZED_BAD_CASE = Event("represent_generalized_bad_case")
RECORD_KNOWN_BUG_HOLDOUT = Event("record_known_bug_holdout")
ADD_OBSERVED_REGRESSION_TEST = Event("add_observed_regression_test")
ADD_SAME_CLASS_TEST_EVIDENCE = Event("add_same_class_test_evidence")
RERUN_MODEL_TEST_ALIGNMENT = Event("rerun_model_test_alignment")
MARK_RECURRING_FAMILY = Event("mark_recurring_family")
PROMOTE_DEFECT_FAMILY_GATE = Event("promote_defect_family_gate")
REVIEW_DEFECT_FAMILY_GATE = Event("review_defect_family_gate")
VALIDATE_FIX = Event("validate_fix")
FINALIZE = Event("finalize")


class ApplyReviewStep:
    name = "ApplyReviewStep"
    reads = (
        "flowguard_passed",
        "runtime_issue_observed",
        "model_miss_classified",
        "issue_represented_in_model",
        "generalized_bad_case_in_scope",
        "generalized_bad_case_represented_in_model",
        "known_bug_used_as_holdout",
        "observed_regression_test_added",
        "same_class_test_evidence_added",
        "model_test_alignment_rerun",
        "recurring_family_detected",
        "defect_family_gate_promoted",
        "defect_family_gate_reviewed",
        "fix_validated_after_refinement",
    )
    writes = (
        "flowguard_passed",
        "runtime_issue_observed",
        "model_miss_classified",
        "issue_represented_in_model",
        "generalized_bad_case_represented_in_model",
        "known_bug_used_as_holdout",
        "observed_regression_test_added",
        "same_class_test_evidence_added",
        "model_test_alignment_rerun",
        "recurring_family_detected",
        "defect_family_gate_promoted",
        "defect_family_gate_reviewed",
        "fix_validated_after_refinement",
        "completed",
    )
    accepted_input_type = Event
    input_description = "review event"
    output_description = "updated model-miss review state"
    idempotency = "Repeated review events keep one obligation state."

    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "flowguard_pass":
            yield FunctionResult("flowguard_passed", replace(state, flowguard_passed=True), label="flowguard_passed")
            return
        if input_obj.name == "runtime_fail":
            if not state.flowguard_passed:
                yield FunctionResult("runtime_fail_before_model_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "runtime_issue_observed",
                replace(state, runtime_issue_observed=True, completed=False),
                label="runtime_issue_observed",
            )
            return
        if input_obj.name == "classify_miss":
            if not state.runtime_issue_observed:
                yield FunctionResult("classification_not_needed", state, label="blocked")
                return
            yield FunctionResult(
                "model_miss_classified",
                replace(state, model_miss_classified=True),
                label="model_miss_classified",
            )
            return
        if input_obj.name == "represent_issue":
            if not state.model_miss_classified:
                yield FunctionResult("representation_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "issue_represented_in_model",
                replace(state, issue_represented_in_model=True),
                label="issue_represented_in_model",
            )
            return
        if input_obj.name == "represent_generalized_bad_case":
            if not state.issue_represented_in_model:
                yield FunctionResult("generalized_bad_case_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "generalized_bad_case_represented_in_model",
                replace(state, generalized_bad_case_represented_in_model=True),
                label="generalized_bad_case_represented_in_model",
            )
            return
        if input_obj.name == "record_known_bug_holdout":
            if not state.generalized_bad_case_represented_in_model:
                yield FunctionResult("holdout_role_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "known_bug_used_as_holdout",
                replace(state, known_bug_used_as_holdout=True),
                label="known_bug_used_as_holdout",
            )
            return
        if input_obj.name == "add_observed_regression_test":
            if not state.known_bug_used_as_holdout:
                yield FunctionResult("observed_regression_test_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "observed_regression_test_added",
                replace(state, observed_regression_test_added=True),
                label="observed_regression_test_added",
            )
            return
        if input_obj.name == "add_same_class_test_evidence":
            if not state.observed_regression_test_added:
                yield FunctionResult("same_class_test_evidence_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "same_class_test_evidence_added",
                replace(state, same_class_test_evidence_added=True),
                label="same_class_test_evidence_added",
            )
            return
        if input_obj.name == "rerun_model_test_alignment":
            if not state.same_class_test_evidence_added:
                yield FunctionResult("model_test_alignment_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "model_test_alignment_rerun",
                replace(state, model_test_alignment_rerun=True),
                label="model_test_alignment_rerun",
            )
            return
        if input_obj.name == "mark_recurring_family":
            if not state.model_miss_classified:
                yield FunctionResult("recurring_family_mark_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "recurring_family_detected",
                replace(state, recurring_family_detected=True),
                label="recurring_family_detected",
            )
            return
        if input_obj.name == "promote_defect_family_gate":
            if not state.recurring_family_detected:
                yield FunctionResult("defect_family_gate_not_required", state, label="blocked")
                return
            if state.generalized_bad_case_in_scope and not state.model_test_alignment_rerun:
                yield FunctionResult("defect_family_gate_promotion_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "defect_family_gate_promoted",
                replace(state, defect_family_gate_promoted=True),
                label="defect_family_gate_promoted",
            )
            return
        if input_obj.name == "review_defect_family_gate":
            if not state.defect_family_gate_promoted:
                yield FunctionResult("defect_family_gate_review_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "defect_family_gate_reviewed",
                replace(state, defect_family_gate_reviewed=True),
                label="defect_family_gate_reviewed",
            )
            return
        if input_obj.name == "validate_fix":
            if not state.issue_represented_in_model:
                yield FunctionResult("fix_validation_blocked", state, label="blocked")
                return
            if state.generalized_bad_case_in_scope and not state.generalized_bad_case_represented_in_model:
                yield FunctionResult("point_fix_only_validation_blocked", state, label="blocked")
                return
            if state.generalized_bad_case_in_scope and not state.known_bug_used_as_holdout:
                yield FunctionResult("holdout_role_validation_blocked", state, label="blocked")
                return
            if state.generalized_bad_case_in_scope and not state.observed_regression_test_added:
                yield FunctionResult("observed_regression_test_validation_blocked", state, label="blocked")
                return
            if state.generalized_bad_case_in_scope and not state.same_class_test_evidence_added:
                yield FunctionResult("same_class_test_evidence_validation_blocked", state, label="blocked")
                return
            if state.generalized_bad_case_in_scope and not state.model_test_alignment_rerun:
                yield FunctionResult("model_test_alignment_validation_blocked", state, label="blocked")
                return
            if state.recurring_family_detected and not (
                state.defect_family_gate_promoted and state.defect_family_gate_reviewed
            ):
                yield FunctionResult("defect_family_gate_validation_blocked", state, label="blocked")
                return
            yield FunctionResult(
                "fix_validated_after_refinement",
                replace(state, fix_validated_after_refinement=True),
                label="fix_validated_after_refinement",
            )
            return
        if input_obj.name == "finalize":
            if state.runtime_issue_observed and not state.fix_validated_after_refinement:
                yield FunctionResult("finalize_blocked_open_model_miss", state, label="finalize_blocked")
                return
            if state.recurring_family_detected and not state.defect_family_gate_reviewed:
                yield FunctionResult("finalize_blocked_open_defect_family_gate", state, label="finalize_blocked")
                return
            yield FunctionResult("completed", replace(state, completed=True), label="completed")
            return
        yield FunctionResult("unknown_event", state, label="blocked")


class BrokenFinalizeIgnoresModelMiss(ApplyReviewStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "finalize":
            yield FunctionResult(
                "completed_without_review",
                replace(state, completed=True),
                label="broken_completed_without_review",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenValidateFixWithoutRepresentation(ApplyReviewStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "validate_fix":
            yield FunctionResult(
                "fix_validated_without_model_representation",
                replace(state, fix_validated_after_refinement=True),
                label="broken_fix_validated_without_model_representation",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenPointFixOnlyValidation(ApplyReviewStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "validate_fix" and state.issue_represented_in_model:
            yield FunctionResult(
                "point_fix_validated_without_generalized_bad_case",
                replace(state, fix_validated_after_refinement=True),
                label="broken_point_fix_only_validation",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenValidateWithoutHoldoutRole(ApplyReviewStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if (
            input_obj.name == "validate_fix"
            and state.issue_represented_in_model
            and state.generalized_bad_case_represented_in_model
        ):
            yield FunctionResult(
                "validated_without_known_bug_holdout_role",
                replace(state, fix_validated_after_refinement=True),
                label="broken_validate_without_holdout_role",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenValidateWithoutSameClassTestEvidence(ApplyReviewStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if (
            input_obj.name == "validate_fix"
            and state.issue_represented_in_model
            and state.generalized_bad_case_represented_in_model
            and state.known_bug_used_as_holdout
        ):
            yield FunctionResult(
                "validated_without_same_class_test_evidence",
                replace(state, fix_validated_after_refinement=True),
                label="broken_validate_without_same_class_test_evidence",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenValidateRecurringWithoutDefectFamilyGate(ApplyReviewStep):
    def apply(self, input_obj: Event, state: State) -> Iterable[FunctionResult]:
        if input_obj.name == "validate_fix" and state.recurring_family_detected:
            yield FunctionResult(
                "recurring_family_validated_without_defect_family_gate",
                replace(state, fix_validated_after_refinement=True),
                label="broken_validate_recurring_without_defect_family_gate",
            )
            return
        yield from super().apply(input_obj, state)


def invariants() -> tuple[Invariant, ...]:
    def completion_requires_review(state: State, _trace) -> InvariantResult:
        if state.completed and state.runtime_issue_observed:
            if not (
                state.model_miss_classified
                and state.issue_represented_in_model
                and (
                    not state.generalized_bad_case_in_scope
                    or state.generalized_bad_case_represented_in_model
                )
                and (not state.generalized_bad_case_in_scope or state.known_bug_used_as_holdout)
                and (
                    not state.generalized_bad_case_in_scope
                    or (
                        state.observed_regression_test_added
                        and state.same_class_test_evidence_added
                        and state.model_test_alignment_rerun
                    )
                )
                and (
                    not state.recurring_family_detected
                    or (
                        state.defect_family_gate_promoted
                        and state.defect_family_gate_reviewed
                    )
                )
                and state.fix_validated_after_refinement
            ):
                return InvariantResult.fail(
                    "completed runtime issue without classification, observed issue model representation, same-class generalized bad case representation, known-bug holdout role, same-class test evidence, Model-Test Alignment rerun, recurring defect-family gate when needed, and refined validation"
                )
        return InvariantResult.pass_()

    def fix_validation_requires_model_representation(state: State, _trace) -> InvariantResult:
        if state.fix_validated_after_refinement and not state.issue_represented_in_model:
            return InvariantResult.fail("fix validated before the issue was represented in the model")
        return InvariantResult.pass_()

    def fix_validation_requires_generalized_bad_case(state: State, _trace) -> InvariantResult:
        if (
            state.fix_validated_after_refinement
            and state.generalized_bad_case_in_scope
            and not state.generalized_bad_case_represented_in_model
        ):
            return InvariantResult.fail("fix validated as point-fix-only without a same-class generalized bad case")
        return InvariantResult.pass_()

    def fix_validation_requires_known_bug_holdout_role(state: State, _trace) -> InvariantResult:
        if (
            state.fix_validated_after_refinement
            and state.generalized_bad_case_in_scope
            and not state.known_bug_used_as_holdout
        ):
            return InvariantResult.fail("fix validated before recording the known bug as holdout validation evidence")
        return InvariantResult.pass_()

    def fix_validation_requires_same_class_test_evidence(state: State, _trace) -> InvariantResult:
        if not (state.fix_validated_after_refinement and state.generalized_bad_case_in_scope):
            return InvariantResult.pass_()
        if not state.observed_regression_test_added:
            return InvariantResult.fail("fix validated before adding observed-regression test evidence")
        if not state.same_class_test_evidence_added:
            return InvariantResult.fail("fix validated before adding same-class generalized test evidence")
        if not state.model_test_alignment_rerun:
            return InvariantResult.fail("fix validated before rerunning Model-Test Alignment")
        return InvariantResult.pass_()

    def recurring_family_requires_defect_family_gate(state: State, _trace) -> InvariantResult:
        if not (state.fix_validated_after_refinement and state.recurring_family_detected):
            return InvariantResult.pass_()
        if not state.defect_family_gate_promoted:
            return InvariantResult.fail("recurring same-class miss validated before promoting a defect-family gate")
        if not state.defect_family_gate_reviewed:
            return InvariantResult.fail("recurring same-class miss validated before reviewing defect-family gate evidence")
        return InvariantResult.pass_()

    return (
        Invariant("completion_requires_review", "Runtime issues must be reviewed before completion.", completion_requires_review),
        Invariant(
            "fix_validation_requires_model_representation",
            "Fix validation requires executable model representation or an explicit boundary.",
            fix_validation_requires_model_representation,
        ),
        Invariant(
            "fix_validation_requires_generalized_bad_case",
            "Fix validation requires a same-class generalized bad case when that class is in scope.",
            fix_validation_requires_generalized_bad_case,
        ),
        Invariant(
            "fix_validation_requires_known_bug_holdout_role",
            "Fix validation records the known bug as holdout validation evidence, not the whole model target.",
            fix_validation_requires_known_bug_holdout_role,
        ),
        Invariant(
            "fix_validation_requires_same_class_test_evidence",
            "Fix validation requires observed regression and same-class test evidence aligned to the repaired model.",
            fix_validation_requires_same_class_test_evidence,
        ),
        Invariant(
            "recurring_family_requires_defect_family_gate",
            "Recurring same-class misses require a reviewed defect-family gate before validation.",
            recurring_family_requires_defect_family_gate,
        ),
    )


def workflow(block=None) -> Workflow:
    return Workflow((block or ApplyReviewStep(),), name="model_miss_review_template")


def scenario(name, description, events, expected, block=None) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        initial_state=State(),
        external_input_sequence=events,
        expected=expected,
        workflow=workflow(block),
        invariants=invariants(),
    )


def run_checks():
    correct = review_scenario(
        scenario(
            "correct_model_miss_review",
            "Runtime issue is classified, observed issue and generalized bad case are represented, then the fix is validated and finalized.",
            (
                FLOWGUARD_PASS,
                RUNTIME_FAIL,
                CLASSIFY_MISS,
                REPRESENT_ISSUE,
                REPRESENT_GENERALIZED_BAD_CASE,
                RECORD_KNOWN_BUG_HOLDOUT,
                ADD_OBSERVED_REGRESSION_TEST,
                ADD_SAME_CLASS_TEST_EVIDENCE,
                RERUN_MODEL_TEST_ALIGNMENT,
                MARK_RECURRING_FAMILY,
                PROMOTE_DEFECT_FAMILY_GATE,
                REVIEW_DEFECT_FAMILY_GATE,
                VALIDATE_FIX,
                FINALIZE,
            ),
            ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("completed",),
                summary="model-miss obligation is closed before completion",
            ),
        )
    )
    broken = review_scenarios(
        (
            scenario(
                "finalize_without_review",
                "Broken workflow finalizes after runtime issue without review.",
                (FLOWGUARD_PASS, RUNTIME_FAIL, FINALIZE),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("completion_requires_review",),
                ),
                block=BrokenFinalizeIgnoresModelMiss(),
            ),
            scenario(
                "validate_fix_without_representation",
                "Broken workflow validates the fix before representing the issue.",
                (FLOWGUARD_PASS, RUNTIME_FAIL, CLASSIFY_MISS, VALIDATE_FIX, FINALIZE),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("fix_validation_requires_model_representation",),
                ),
                block=BrokenValidateFixWithoutRepresentation(),
            ),
            scenario(
                "point_fix_only_without_generalized_bad_case",
                "Broken workflow validates only the observed issue and misses a same-class generalized bad case.",
                (FLOWGUARD_PASS, RUNTIME_FAIL, CLASSIFY_MISS, REPRESENT_ISSUE, VALIDATE_FIX, FINALIZE),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("fix_validation_requires_generalized_bad_case",),
                ),
                block=BrokenPointFixOnlyValidation(),
            ),
            scenario(
                "validate_without_known_bug_holdout_role",
                "Broken workflow models the class but forgets to record the known bug as holdout validation evidence.",
                (
                    FLOWGUARD_PASS,
                    RUNTIME_FAIL,
                    CLASSIFY_MISS,
                    REPRESENT_ISSUE,
                    REPRESENT_GENERALIZED_BAD_CASE,
                    VALIDATE_FIX,
                    FINALIZE,
                ),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("fix_validation_requires_known_bug_holdout_role",),
                ),
                block=BrokenValidateWithoutHoldoutRole(),
            ),
            scenario(
                "validate_without_same_class_test_evidence",
                "Broken workflow models the class but only validates the observed bug.",
                (
                    FLOWGUARD_PASS,
                    RUNTIME_FAIL,
                    CLASSIFY_MISS,
                    REPRESENT_ISSUE,
                    REPRESENT_GENERALIZED_BAD_CASE,
                    RECORD_KNOWN_BUG_HOLDOUT,
                    ADD_OBSERVED_REGRESSION_TEST,
                    VALIDATE_FIX,
                    FINALIZE,
                ),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("fix_validation_requires_same_class_test_evidence",),
                ),
                block=BrokenValidateWithoutSameClassTestEvidence(),
            ),
            scenario(
                "validate_recurring_without_defect_family_gate",
                "Broken workflow treats a recurring same-class miss as another ordinary point fix.",
                (
                    FLOWGUARD_PASS,
                    RUNTIME_FAIL,
                    CLASSIFY_MISS,
                    REPRESENT_ISSUE,
                    REPRESENT_GENERALIZED_BAD_CASE,
                    RECORD_KNOWN_BUG_HOLDOUT,
                    ADD_OBSERVED_REGRESSION_TEST,
                    ADD_SAME_CLASS_TEST_EVIDENCE,
                    RERUN_MODEL_TEST_ALIGNMENT,
                    MARK_RECURRING_FAMILY,
                    VALIDATE_FIX,
                    FINALIZE,
                ),
                ScenarioExpectation(
                    expected_status="violation",
                    expected_violation_names=("recurring_family_requires_defect_family_gate",),
                ),
                block=BrokenValidateRecurringWithoutDefectFamilyGate(),
            ),
        )
    )
    return correct, broken
'''


MODEL_MISS_REVIEW_RUN_CHECKS_TEMPLATE = '''"""Run the post-runtime model-miss review template."""

from model import run_checks


def main() -> int:
    correct, broken = run_checks()
    print(f"{correct.scenario_name}: {correct.status.upper()}")
    for item in correct.evidence:
        print(f"  - {item}")
    print()
    print(broken.format_text(max_counterexamples=2))
    return 0 if correct.ok and broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


MODEL_MISS_REVIEW_NOTES_TEMPLATE = """# FlowGuard Model-Miss Review Notes

Use this scaffold when real validation finds an issue after a FlowGuard pass.

## Review Questions

- Why did the earlier model miss this bug class?
- Was the boundary too narrow, the state too coarse, an input branch missing, an
  invariant weak, a replay skipped, or the issue outside the modeled scope?
- How is the issue now represented: scenario, invariant, replay adapter,
  representative trace, or explicit out-of-scope boundary?
- What same-class generalized bad case prevents a point-fix-only repair, and is
  that class represented or explicitly out of scope?
- How is the known bug used as validation or holdout evidence instead of the
  whole model target?
- Which observed-regression test and same-class generalized test evidence now
  prove the repaired obligation?
- Which Model-Test Alignment rows prove the new model obligations, optional
  code contracts, and same-class tests cover the same behavior?
- Has this same-class family appeared before, or is it high risk enough to
  require a defect-family gate rather than another ordinary bug fix?
- Which defect-family gate records the family id, authority boundary, observed
  failure, same-class generalized case, historical holdout, and current proof?
- Which refined model checks, runtime checks, and same-class tests must pass
  before completion?
- If the repair changed a child model under a parent ModelMesh, which parent
  reattachment gate consumed the new child evidence id?
- If same-class validation is large, slow, layered, background, or release-only,
  which TestMesh parent/child suite owns it and where is final result evidence?

Do not let a later green runtime check, one observed-bug regression test, or a
second local point fix close a known model miss by itself. Full closure needs
same-class test evidence, and recurring families need a defect-family gate or
an explicit scoped-confidence boundary.
Child-local green is not enough when parent mesh confidence depends on the
child's input/output/state/side-effect handoff.
"""


MODEL_TEST_ALIGNMENT_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Reviews whether explicit FlowGuard model obligations, optional code external
contracts, and ordinary test evidence describe the same behavioral surface.

Guards against:
- model scenarios, invariants, hazards, or transitions with no test evidence;
- model obligations with no code external contract owner;
- code functions or entrypoints that miss model-declared external behavior;
- code functions or entrypoints that add model-forbidden external behavior;
- tests that are not bound to any model obligation;
- tests that are not bound to the code contract they are meant to prove;
- tests that inspect only internal paths while claiming external contract proof;
- duplicate tests claiming the same model obligation without clear intent;
- risky model paths covered only by happy-path tests;
- model-miss repairs that only test the observed bug without same-class evidence;
- stale, skipped, failed, timeout, not-run, or overclaiming test evidence.

Use before editing:
test coverage claims, model confidence reports, model-backed feature work, or
release notes that claim model and test coverage agree.

Run:
python .flowguard/model_test_alignment/run_checks.py

This template does not use TestMesh, StructureMesh, or ModelMesh. It compares
plain model obligations, optional code external contracts, and plain test
evidence. If one obligation has several primary edge-path tests, split child
obligations or attach those tests to leaf matrix cells instead of relabeling one
as generic support.
"""

from __future__ import annotations

from flowguard import (
    CodeBoundaryContract,
    CodeBoundaryObservation,
    CodeContract,
    ModelObligation,
    ModelTestAlignmentPlan,
    ProofArtifactRef,
    TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
    TEST_ASSERTION_SCOPE_INTERNAL_PATH,
    TEST_CLOSURE_ROLE_OBSERVED_REGRESSION,
    TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED,
    TEST_KIND_FAILURE_PATH,
    TEST_KIND_HAPPY_PATH,
    TestEvidence,
    audit_python_code_contracts,
    audit_python_test_assertions,
    review_code_boundary_conformance,
    review_python_contract_source_audit,
    review_model_test_alignment,
)


def proof_artifact(evidence_id: str, *covered: str) -> ProofArtifactRef:
    result_path = f"tmp/{evidence_id}.json"
    return ProofArtifactRef(
        f"artifact:{evidence_id}",
        result_status="passed",
        exit_code=0,
        result_path=result_path,
        artifact_fingerprints={result_path: "sha256:template"},
        covered_obligation_ids=covered,
    )


def aligned_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="sample_checkout_model",
        require_proof_artifacts=True,
        obligations=(
            ModelObligation(
                "accept_valid_order",
                obligation_type="scenario",
                description="valid order reaches Accepted",
                external_inputs=("order_id", "payment_token"),
                external_outputs=("Accepted",),
                state_writes=("order_status",),
                required_test_kinds=(TEST_KIND_HAPPY_PATH,),
            ),
            ModelObligation(
                "reject_duplicate_order",
                obligation_type="hazard",
                description="duplicate order is rejected without a second side effect",
                external_inputs=("order_id",),
                external_outputs=("Rejected",),
                state_reads=("order_status",),
                side_effects=(),
                error_paths=("duplicate_order",),
                exact_external_contract=True,
                required_test_kinds=(TEST_KIND_HAPPY_PATH, TEST_KIND_FAILURE_PATH),
            ),
            ModelObligation(
                "model_miss_duplicate_submit_family",
                obligation_type="model_miss",
                description="post-runtime duplicate-submit miss is closed by observed and same-class tests",
                model_miss_origin=True,
                requires_same_class_test_evidence=True,
                required_test_kinds=(TEST_KIND_HAPPY_PATH,),
            ),
        ),
        code_contracts=(
            CodeContract(
                "checkout_accept_order",
                path="checkout/service.py",
                symbol="accept_order",
                implements_obligations=("accept_valid_order",),
                external_inputs=("order_id", "payment_token"),
                external_outputs=("Accepted",),
                state_writes=("order_status",),
            ),
            CodeContract(
                "checkout_reject_duplicate",
                path="checkout/service.py",
                symbol="reject_duplicate_order",
                implements_obligations=("reject_duplicate_order",),
                external_inputs=("order_id",),
                external_outputs=("Rejected",),
                state_reads=("order_status",),
                error_paths=("duplicate_order",),
            ),
            CodeContract(
                "checkout_duplicate_submit_family",
                path="checkout/service.py",
                symbol="reject_duplicate_order",
                implements_obligations=("model_miss_duplicate_submit_family",),
                external_inputs=("order_id",),
                external_outputs=("Rejected",),
                error_paths=("duplicate_order",),
            ),
        ),
        test_evidence=(
            TestEvidence(
                "test_accept_valid_order",
                test_name="test_accept_valid_order",
                path="tests/test_checkout.py",
                result_status="passed",
                test_kind=TEST_KIND_HAPPY_PATH,
                covered_obligations=("accept_valid_order",),
                covered_code_contracts=("checkout_accept_order",),
                assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
                proof_artifact=proof_artifact("test_accept_valid_order", "accept_valid_order"),
            ),
            TestEvidence(
                "test_reject_duplicate_order_happy",
                test_name="test_reject_duplicate_order_happy",
                path="tests/test_checkout.py",
                result_status="passed",
                test_kind=TEST_KIND_HAPPY_PATH,
                covered_obligations=("reject_duplicate_order",),
                covered_code_contracts=("checkout_reject_duplicate",),
                assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
                proof_artifact=proof_artifact(
                    "test_reject_duplicate_order_happy",
                    "reject_duplicate_order",
                ),
            ),
            TestEvidence(
                "test_reject_duplicate_order_failure",
                test_name="test_reject_duplicate_order_failure",
                path="tests/test_checkout.py",
                result_status="passed",
                test_kind=TEST_KIND_FAILURE_PATH,
                covered_obligations=("reject_duplicate_order",),
                covered_code_contracts=("checkout_reject_duplicate",),
                assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
                proof_artifact=proof_artifact(
                    "test_reject_duplicate_order_failure",
                    "reject_duplicate_order",
                ),
            ),
            TestEvidence(
                "test_observed_duplicate_submit_regression",
                test_name="test_observed_duplicate_submit_regression",
                path="tests/test_checkout.py",
                result_status="passed",
                test_kind=TEST_KIND_HAPPY_PATH,
                covered_obligations=("model_miss_duplicate_submit_family",),
                covered_code_contracts=("checkout_duplicate_submit_family",),
                assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
                closure_evidence_role=TEST_CLOSURE_ROLE_OBSERVED_REGRESSION,
                proof_artifact=proof_artifact(
                    "test_observed_duplicate_submit_regression",
                    "model_miss_duplicate_submit_family",
                ),
            ),
            TestEvidence(
                "test_same_class_duplicate_submit_variants",
                test_name="test_same_class_duplicate_submit_variants",
                path="tests/test_checkout.py",
                result_status="passed",
                test_kind=TEST_KIND_HAPPY_PATH,
                covered_obligations=("model_miss_duplicate_submit_family",),
                covered_code_contracts=("checkout_duplicate_submit_family",),
                assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
                closure_evidence_role=TEST_CLOSURE_ROLE_SAME_CLASS_GENERALIZED,
                proof_artifact=proof_artifact(
                    "test_same_class_duplicate_submit_variants",
                    "model_miss_duplicate_submit_family",
                ),
            ),
        ),
        boundary_contracts=(
            CodeBoundaryContract(
                "checkout_reject_duplicate_boundary",
                code_contract_id="checkout_reject_duplicate",
                model_obligation_id="reject_duplicate_order",
                allowed_inputs=("duplicate_order",),
                rejected_inputs=("unknown_event",),
                allowed_outputs=("Rejected", "RejectedInvalidInput"),
                allowed_error_paths=("duplicate_order", "invalid_input"),
                exact=True,
            ),
        ),
        boundary_observations=(
            CodeBoundaryObservation(
                "boundary_reject_duplicate_order",
                "checkout_reject_duplicate_boundary",
                input_case="duplicate_order",
                accepted=True,
                observed_output="Rejected",
                observed_error_path="duplicate_order",
            ),
            CodeBoundaryObservation(
                "boundary_reject_unknown_event",
                "checkout_reject_duplicate_boundary",
                input_case="unknown_event",
                accepted=False,
                observed_output="RejectedInvalidInput",
                observed_error_path="invalid_input",
            ),
        ),
    )


def broken_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="sample_checkout_model",
        obligations=(
            ModelObligation(
                "reject_duplicate_order",
                obligation_type="hazard",
                external_outputs=("Rejected",),
                side_effects=(),
                error_paths=("duplicate_order",),
                exact_external_contract=True,
                required_test_kinds=(TEST_KIND_HAPPY_PATH, TEST_KIND_FAILURE_PATH),
            ),
            ModelObligation(
                "model_miss_duplicate_submit_family",
                obligation_type="model_miss",
                model_miss_origin=True,
                requires_same_class_test_evidence=True,
            ),
        ),
        code_contracts=(
            CodeContract(
                "checkout_reject_duplicate",
                path="checkout/service.py",
                symbol="reject_duplicate_order",
                implements_obligations=("reject_duplicate_order",),
                external_outputs=("Rejected",),
                side_effects=("publish_duplicate_metric",),
                error_paths=("duplicate_order",),
            ),
            CodeContract(
                "checkout_duplicate_submit_family",
                path="checkout/service.py",
                symbol="reject_duplicate_order",
                implements_obligations=("model_miss_duplicate_submit_family",),
                external_outputs=("Rejected",),
            ),
        ),
        test_evidence=(
            TestEvidence(
                "test_duplicate_only_happy",
                test_name="test_duplicate_only_happy",
                path="tests/test_checkout.py",
                result_status="passed",
                test_kind=TEST_KIND_HAPPY_PATH,
                covered_obligations=("reject_duplicate_order",),
                covered_code_contracts=("checkout_reject_duplicate",),
                assertion_scope=TEST_ASSERTION_SCOPE_INTERNAL_PATH,
            ),
            TestEvidence(
                "test_unbound_helper",
                test_name="test_unbound_helper",
                path="tests/test_checkout.py",
                result_status="passed",
            ),
            TestEvidence(
                "test_observed_duplicate_submit_only",
                test_name="test_observed_duplicate_submit_only",
                path="tests/test_checkout.py",
                result_status="passed",
                covered_obligations=("model_miss_duplicate_submit_family",),
                covered_code_contracts=("checkout_duplicate_submit_family",),
                assertion_scope=TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
                closure_evidence_role=TEST_CLOSURE_ROLE_OBSERVED_REGRESSION,
            ),
        ),
        boundary_contracts=(
            CodeBoundaryContract(
                "checkout_reject_duplicate_boundary",
                code_contract_id="checkout_reject_duplicate",
                model_obligation_id="reject_duplicate_order",
                allowed_inputs=("duplicate_order",),
                rejected_inputs=("unknown_event",),
                allowed_outputs=("Rejected",),
                allowed_side_effects=(),
                allowed_error_paths=("duplicate_order",),
                exact=True,
            ),
        ),
        boundary_observations=(
            CodeBoundaryObservation(
                "boundary_duplicate_extra_metric",
                "checkout_reject_duplicate_boundary",
                input_case="duplicate_order",
                accepted=True,
                observed_output="Rejected",
                observed_side_effects=("publish_duplicate_metric",),
            ),
            CodeBoundaryObservation(
                "boundary_unknown_event_accepted",
                "checkout_reject_duplicate_boundary",
                input_case="unknown_event",
                accepted=True,
                observed_output="Rejected",
            ),
        ),
    )


ALIGNED_SOURCE = {
    "checkout/service.py": """
def accept_order(order_id, payment_token):
    state = {}
    state["order_status"] = "Accepted"
    return "Accepted"

def reject_duplicate_order(order_id):
    if order_id:
        return "Rejected"
    raise duplicate_order()
""",
    "tests/test_checkout.py": """
def test_accept_valid_order():
    result = accept_order("order-1", "token")
    assert result == "Accepted"

def test_reject_duplicate_order_happy():
    result = reject_duplicate_order("order-1")
    assert result == "Rejected"

def test_reject_duplicate_order_failure():
    result = reject_duplicate_order("order-1")
    assert result == "Rejected"

def test_observed_duplicate_submit_regression():
    assert reject_duplicate_order("observed-duplicate") == "Rejected"

def test_same_class_duplicate_submit_variants():
    assert reject_duplicate_order("duplicate-via-alt-entry") == "Rejected"
""",
}


BROKEN_SOURCE = {
    "checkout/service.py": """
def reject_duplicate_order(order_id):
    publish_duplicate_metric(order_id)
    return "Rejected"
""",
    "tests/test_checkout.py": """
def test_duplicate_only_happy():
    result = helper_reject_duplicate("order-1")
    assert result == "Rejected"

def test_unbound_helper():
    assert helper_reject_duplicate("order-1") == "Rejected"
""",
}


def source_audit(plan: ModelTestAlignmentPlan, source_by_path: dict[str, str]):
    code_evidence = audit_python_code_contracts(plan.code_contracts, source_by_path)
    test_assertions = audit_python_test_assertions(plan.test_evidence, plan.code_contracts, source_by_path)
    return review_python_contract_source_audit(
        plan.code_contracts,
        plan.test_evidence,
        code_evidence,
        test_assertions,
    )


def run_checks():
    aligned = aligned_plan()
    broken = broken_plan()
    aligned_boundary = review_code_boundary_conformance(aligned.boundary_contracts, aligned.boundary_observations, aligned.code_contracts)
    broken_boundary = review_code_boundary_conformance(broken.boundary_contracts, broken.boundary_observations, broken.code_contracts)
    return (
        review_model_test_alignment(aligned),
        review_model_test_alignment(broken),
        aligned_boundary,
        broken_boundary,
        source_audit(aligned, ALIGNED_SOURCE),
        source_audit(broken, BROKEN_SOURCE),
    )
'''


MODEL_TEST_ALIGNMENT_RUN_CHECKS_TEMPLATE = '''"""Run the Model-Test Alignment template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    aligned, broken, aligned_boundary, broken_boundary, aligned_source, broken_source = run_checks()
    print(aligned.format_text())
    print()
    print(broken.format_text(max_findings=10))
    print()
    print(aligned_boundary.format_text())
    print()
    print(broken_boundary.format_text(max_findings=5))
    print()
    print(aligned_source.format_text())
    print()
    print(broken_source.format_text(max_findings=5))
    return 0 if aligned.ok and not broken.ok and aligned_boundary.ok and not broken_boundary.ok and aligned_source.ok and not broken_source.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


MODEL_TEST_ALIGNMENT_NOTES_TEMPLATE = """# FlowGuard Model-Test Alignment Notes

Use this scaffold to compare a FlowGuard model's explicit obligations with
optional code external contracts, ordinary test evidence, and conservative
Python source audits for those contracts. When the model says the real code
surface has a finite input/output boundary, also add code-boundary conformance
observations from runtime tests, replay, or a harness.

## Inputs

List model obligations:

- scenario ids;
- invariant ids;
- hazard ids;
- state-transition or input/output contract ids;
- external inputs and outputs;
- state reads and writes;
- side effects and error paths;
- whether the external contract is exact, so extra code-visible behavior blocks
  confidence;
- required test kinds such as happy path, failure path, edge path, negative
  path, or replay.

List code external contracts when the review needs model-to-code alignment:

- code contract id;
- path, symbol, and surface type;
- whether the surface is the obligation owner, helper, adapter, facade, or
  read-only support;
- implemented model obligation ids;
- external inputs and outputs;
- state reads and writes;
- side effects and error paths.

List test evidence:

- evidence id;
- test name and path;
- command or runner;
- pass, fail, timeout, skipped, not-run, running, or error status;
- freshness and stale reasons;
- covered model obligation ids.
- covered code contract ids;
- assertion scope, especially whether the test proves the external contract or
  only an internal path.

List code-boundary conformance evidence when a code surface must be closed:

- `CodeBoundaryContract` rows declare allowed input cases, rejected input cases,
  allowed outputs, state writes, side effects, and error paths.
- `CodeBoundaryObservation` rows record what real code did for one input case:
  accepted or rejected, returned output, error path, state writes, and side
  effects.
- `review_code_boundary_conformance(...)` blocks when forbidden inputs are
  accepted, allowed inputs are rejected, missing input-gate evidence is reused,
  or real code produces undeclared output, state write, side effect, or error.
- Boundary observations are runtime evidence. They do not replace conformance
  replay when ordered production traces, durable state, or adapter projection
  are part of the claim.

Optionally run the conservative source audit:

- `audit_python_code_contracts(...)` returns `PythonCodeContractEvidence` from
  real Python functions: symbol presence, parameters, return statements,
  raises, state writes, and side-effect-looking calls.
- `audit_python_test_assertions(...)` returns `PythonTestAssertionEvidence`
  from real Python tests: whether the test calls the target code contract and
  contains assertions.
- `review_python_contract_source_audit(...)` flags source-level gaps before the
  declared rows are trusted. This is not a full semantic proof.
- Code audits inspect function signatures, return values, raises, assignments, and calls.
  They can flag a missing Python symbol, missing input, missing output, missing
  state write, and extra side effect.
- Test audits check that tests must call the declared code contract symbol and
  contain an assert or unittest assertion; helper/internal path evidence and no
  assert evidence stay visible as source-level gaps.

## Boundary

Model-Test Alignment does not split tests, refactor source code, or read mesh
reports. It compares declared obligations, optional external code contracts,
and evidence. Use TestMesh only when a large validation flow needs parent/child
test hierarchy ownership. Use StructureMesh only when a large script, module,
command, or API surface is being split.
"""


DEVELOPMENT_PROCESS_FLOW_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Review a development lifecycle as a sibling process route, tracking artifact versions, automatic model/test split gates, and validation evidence freshness before done or release claims.
Guards against: stale validation after code/test/model/requirement changes, oversized direct model evidence, slow or broad direct validation evidence, progress-only evidence, hidden skips, missing V-style validation pairs, peer writes, and release overclaims.
Use before editing: Update this development process flow when changing development ordering, validation gates, automatic split triggers, release readiness, or evidence freshness policy.
Run: python .flowguard/development_process_flow/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    PROCESS_ARTIFACT_CODE,
    PROCESS_ARTIFACT_MODEL,
    PROCESS_ARTIFACT_REQUIREMENT,
    PROCESS_ARTIFACT_TEST,
    PROCESS_EVIDENCE_PASSED,
    PROCESS_SCOPE_RELEASE,
    DevelopmentProcessPlan,
    FreshnessRule,
    ProofArtifactRef,
    ProcessAction,
    ProcessArtifact,
    ProcessEvidence,
    ValidationRequirement,
    review_development_process_flow,
)


def proof_artifact(artifact_id: str, *covered: str) -> ProofArtifactRef:
    result_path = f"tmp/{artifact_id.replace(':', '_')}.json"
    return ProofArtifactRef(
        artifact_id,
        result_status=PROCESS_EVIDENCE_PASSED,
        exit_code=0,
        result_path=result_path,
        artifact_fingerprints={result_path: "sha256:template"},
        covered_obligation_ids=covered,
    )


def artifacts(code_version: str = "2", test_version: str = "1", requirement_version: str = "1"):
    return (
        ProcessArtifact("requirements.checkout", PROCESS_ARTIFACT_REQUIREMENT, requirement_version),
        ProcessArtifact(
            "model.checkout",
            PROCESS_ARTIFACT_MODEL,
            "1",
            upstream_artifact_ids=("requirements.checkout",),
        ),
        ProcessArtifact(
            "code.checkout",
            PROCESS_ARTIFACT_CODE,
            code_version,
            upstream_artifact_ids=("requirements.checkout", "model.checkout"),
        ),
        ProcessArtifact("tests.checkout", PROCESS_ARTIFACT_TEST, test_version),
    )


def routine_plan() -> DevelopmentProcessPlan:
    return DevelopmentProcessPlan(
        "checkout-development-lifecycle",
        require_proof_artifacts=True,
        artifacts=artifacts(code_version="2"),
        actions=(
            ProcessAction("edit-code", writes_artifacts=("code.checkout",)),
            ProcessAction("run-unit", produced_evidence_ids=("unit-pass",)),
            ProcessAction("claim-done", action_type="claim_done", required_validation_ids=("unit-current",)),
        ),
        evidence=(
            ProcessEvidence(
                "unit-pass",
                evidence_kind="unit",
                producer_route="test_mesh_maintenance",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("code.checkout",),
                verifier_artifacts=("tests.checkout",),
                covered_versions={"code.checkout": "2", "tests.checkout": "1"},
                validation_requirement_ids=("unit-current",),
                produced_by_action_id="run-unit",
                command="python -m unittest tests.test_checkout",
                proof_artifact=proof_artifact("artifact:unit-pass", "unit-current"),
            ),
        ),
        validation_requirements=(
            ValidationRequirement(
                "unit-current",
                required_artifact_ids=("code.checkout",),
                required_evidence_kinds=("unit",),
                v_model_pair=True,
                command="python -m unittest tests.test_checkout",
            ),
        ),
    )


def broken_plan() -> DevelopmentProcessPlan:
    return DevelopmentProcessPlan(
        "checkout-broken-lifecycle",
        artifacts=artifacts(code_version="2", requirement_version="2"),
        actions=(
            ProcessAction("run-unit", produced_evidence_ids=("unit-pass",)),
            ProcessAction("edit-code", writes_artifacts=("code.checkout",)),
            ProcessAction("edit-requirement", writes_artifacts=("requirements.checkout",)),
            ProcessAction(
                "claim-release",
                action_type="claim_release",
                required_evidence_ids=("unit-pass",),
                decision_scope=PROCESS_SCOPE_RELEASE,
            ),
        ),
        evidence=(
            ProcessEvidence(
                "unit-pass",
                evidence_kind="unit",
                producer_route="test_mesh_maintenance",
                status=PROCESS_EVIDENCE_PASSED,
                covers_artifacts=("code.checkout",),
                verifier_artifacts=("tests.checkout",),
                covered_versions={"code.checkout": "1", "tests.checkout": "1"},
                validation_requirement_ids=("unit-current",),
                produced_by_action_id="run-unit",
                command="python -m unittest tests.test_checkout",
            ),
        ),
        validation_requirements=(
            ValidationRequirement(
                "unit-current",
                required_artifact_ids=("code.checkout",),
                required_evidence_kinds=("unit",),
                evidence_ids=("unit-pass",),
                v_model_pair=True,
                command="python -m unittest tests.test_checkout",
            ),
        ),
        freshness_rules=(
            FreshnessRule(
                "requirements-affect-code-validation",
                upstream_artifact_id="requirements.checkout",
                invalidates_artifact_ids=("code.checkout", "model.checkout"),
            ),
        ),
        decision_scope=PROCESS_SCOPE_RELEASE,
    )


def run_checks():
    return review_development_process_flow(routine_plan()), review_development_process_flow(broken_plan())
'''


DEVELOPMENT_PROCESS_FLOW_RUN_CHECKS_TEMPLATE = '''"""Run the DevelopmentProcessFlow template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    routine, broken = run_checks()
    print(routine.format_text())
    print()
    print(broken.format_text(max_findings=6))
    return 0 if routine.ok and not broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


DEVELOPMENT_PROCESS_FLOW_NOTES_TEMPLATE = """# FlowGuard DevelopmentProcessFlow Notes

Use this scaffold to model a development lifecycle as a stateful process.

## What DevelopmentProcessFlow Reviews

- versioned requirements, designs, models, code, tests, docs, release assets,
  adapters, and sibling route report artifacts;
- ordered development actions that read, write, invalidate, or claim evidence;
- validation evidence and the exact artifact versions it covers;
- verifier changes, such as tests or model files changing after evidence was
  produced;
- freshness rules that propagate upstream changes to downstream artifacts;
- automatic ModelMesh/TestMesh split triggers for direct evidence that is
  oversized, incomplete, slow, broad, progress-only, or release-only;
- whether done, release, archive, or publish claims have current evidence;
- the minimum revalidation needed when evidence is stale or missing.

## Sibling Route Boundary

This is a sibling sub-protocol. It can reference evidence produced by ModelMesh,
TestMesh, StructureMesh, Model-Test Alignment, LongCheck, or Conformance
Adoption through evidence ids and freshness metadata. It does not inspect,
supervise, replace, or repair those routes. If sibling evidence is failed,
stale, skipped, missing, or progress-only, this route keeps that lifecycle gap
visible for the current process claim.

When direct model/test evidence reports state counts, pending budgeted states,
long durations, broad obligation coverage, background progress-only status, or
release-only scope, call `review_auto_mesh_splits()` and consume the resulting
ModelMesh or TestMesh gate before claiming broad parent confidence.

Use this route when development ordering, artifact overwrite, verification
freshness, or release readiness is the risk. It is not mandatory for every
small edit and it does not make FlowGuard a task orchestrator.
"""


WORKFLOW_STEP_CONTRACTS_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Declare workflow steps as receipt-producing contracts so later steps and done/release claims cannot skip required work.
Guards against: skipped mandatory steps, wrong step order, premature completion claims, stale receipts after invalidation, and progress-only evidence being treated as completion.
Use before editing: Update this workflow step contract model when adding, removing, reordering, or renaming required process steps, receipts, claims, or validation evidence.
Run: python .flowguard/workflow_step_contracts/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    Trace,
    TraceStep,
    WorkflowStepContract,
    review_step_contract_trace,
    step_contracts_to_model_obligations,
    step_contracts_to_validation_requirements,
)


CONTRACTS = (
    WorkflowStepContract(
        "write_change_inventory",
        completion_labels=("change_inventory_written",),
        produces_receipts=("change_inventory",),
        description="The work starts by listing the changed files and affected behavior.",
    ),
    WorkflowStepContract(
        "write_coverage_matrix",
        completion_labels=("coverage_matrix_written",),
        requires_receipts=("change_inventory",),
        produces_receipts=("coverage_matrix",),
        description="Coverage matrix maps changed behavior to model, replay, and test evidence.",
    ),
    WorkflowStepContract(
        "run_regression",
        completion_labels=("regression_passed",),
        requires_receipts=("coverage_matrix",),
        produces_receipts=("full_regression",),
        required_for_claims=("done_claimed",),
        required_test_kinds=("replay", "edge_path"),
        description="Full regression is required before the done claim.",
    ),
)


def step(label: str) -> TraceStep:
    return TraceStep(
        external_input=label,
        function_name="development_step",
        function_input=label,
        function_output=label,
        old_state=(),
        new_state=(),
        label=label,
    )


def good_trace() -> Trace:
    return Trace(
        steps=(
            step("change_inventory_written"),
            step("coverage_matrix_written"),
            step("regression_passed"),
            step("done_claimed"),
        )
    )


def broken_trace() -> Trace:
    return Trace(
        steps=(
            step("change_inventory_written"),
            step("coverage_matrix_written"),
            step("done_claimed"),
        )
    )


def run_checks():
    good = review_step_contract_trace(good_trace(), CONTRACTS)
    broken = review_step_contract_trace(broken_trace(), CONTRACTS)
    process_requirements = step_contracts_to_validation_requirements(CONTRACTS)
    model_obligations = step_contracts_to_model_obligations(CONTRACTS)
    return good, broken, process_requirements, model_obligations
'''


WORKFLOW_STEP_CONTRACTS_RUN_CHECKS_TEMPLATE = '''"""Run the workflow step contracts template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    good, broken, process_requirements, model_obligations = run_checks()
    print("=== flowguard workflow step contracts ===")
    print(good.format_text())
    print()
    print(broken.format_text())
    print(f"process_requirements: {len(process_requirements)}")
    print(f"model_obligations: {len(model_obligations)}")
    return 0 if good.ok and not broken.ok and process_requirements and model_obligations else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


WORKFLOW_STEP_CONTRACTS_NOTES_TEMPLATE = """# FlowGuard workflow step contracts

## FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Make required workflow steps explicit as receipts that later steps and claims must consume.
Guards against: skipped mandatory steps, premature done/release claims, stale receipts after invalidation, and hidden workflow shortcuts.
Use before editing: Update these contracts whenever the project changes required steps, evidence receipts, claim labels, or validation scope.
Run: python .flowguard/workflow_step_contracts/run_checks.py

## How to read this template

Each `WorkflowStepContract` is a small promise:

- `requires_receipts` says what must already be current.
- `produces_receipts` says what this step proves when it completes.
- `invalidates_receipts` says which older receipts stop being current.
- `required_for_claims` says which done, release, archive, or publish labels need this receipt.
- `skip_policy` says whether a skipped step is forbidden or must carry an explicit reason.

The same contract list can feed model exploration, DevelopmentProcessFlow
validation requirements, Model-Test Alignment obligations, and conformance
replay metadata checks.
"""


TEST_MESH_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Review whether a parent test gate can trust child suites/scripts as owned validation regions.
Guards against: flat test splits, stale child suites, hidden skips, progress-only background runs, duplicate ownership, and release checks blocking routine confidence.
Use before editing: Update this TestMesh when changing validation layout, test partitions, child test scripts, slow regression gates, or background evidence contracts.
Run: python .flowguard/test_mesh/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    EVIDENCE_ABSTRACT_GREEN,
    EVIDENCE_CONFORMANCE_GREEN,
    TestMeshPlan,
    TestPartitionItem,
    TestSuiteEvidence,
    TestTargetSplitDerivation,
    review_test_mesh,
)


def routine_plan() -> TestMeshPlan:
    return TestMeshPlan(
        parent_suite_id="project-validation",
        decision_scope="routine",
        partition_items=(
            TestPartitionItem("unit-fast", owner_suite_id="unit"),
            TestPartitionItem("runtime-contract", owner_suite_id="runtime"),
        ),
        child_suites=(
            TestSuiteEvidence(
                "unit",
                command="python -m unittest tests.test_fast",
                result_status="passed",
                evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                evidence_current=True,
                test_count=12,
                selected_count=12,
            ),
            TestSuiteEvidence(
                "runtime",
                command="python -m unittest tests.test_runtime_contract",
                result_status="passed",
                evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                evidence_current=True,
                test_count=8,
                selected_count=8,
            ),
            TestSuiteEvidence(
                "release-full",
                command="python -m unittest discover -s tests",
                layer="release",
                result_status="not_run",
                evidence_tier=EVIDENCE_CONFORMANCE_GREEN,
                release_required=True,
                not_run_reason="release-only regression deferred during routine check",
            ),
        ),
        target_split_derivation=TestTargetSplitDerivation(
            "project-validation-model",
            target_suite_ids=("unit", "runtime", "release-full"),
            covered_partition_item_ids=("unit-fast", "runtime-contract"),
            rationale="derived from the parent validation FlowGuard model and release gate boundaries",
        ),
    )


def broken_plan() -> TestMeshPlan:
    return TestMeshPlan(
        parent_suite_id="project-validation",
        partition_items=(TestPartitionItem("runtime-contract", owner_suite_id="runtime"),),
        child_suites=(
            TestSuiteEvidence(
                "runtime",
                command="python -m unittest tests.test_runtime_contract",
                result_status="passed",
                evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                evidence_current=False,
                skipped_count=2,
                skipped_visible=False,
                stale_reasons=("source_changed",),
            ),
        ),
        target_split_derivation=TestTargetSplitDerivation(
            "project-validation-model",
            target_suite_ids=("runtime",),
            covered_partition_item_ids=("runtime-contract",),
            rationale="derived from the parent validation FlowGuard model and runtime contract boundary",
        ),
    )


def run_checks():
    return review_test_mesh(routine_plan()), review_test_mesh(broken_plan())
'''


TEST_MESH_RUN_CHECKS_TEMPLATE = '''"""Run the TestMesh template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    routine, broken = run_checks()
    print(routine.format_text())
    print()
    print(broken.format_text(max_findings=3))
    return 0 if routine.ok and not broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


TEST_MESH_NOTES_TEMPLATE = """# FlowGuard TestMesh Notes

Use this scaffold to keep a project's validation hierarchy explicit.

## What TestMesh Reviews

- how a broad parent test gate is split into child suites or child scripts;
- which FlowGuard validation-structure model derived the target child
  suites/scripts before evidence is trusted;
- which child owns each behavior, state, command, invariant, or release
  partition;
- whether child suite/script evidence is current and strong enough for the
  parent;
- whether background logs include final exit/result artifacts;
- whether skipped, timed-out, not-run, or release-only checks remain visible.

TestMesh is parallel to ModelMesh and StructureMesh: the object being split is
the test structure. The parent should consume child ownership and evidence
contracts instead of expanding every child test case into one giant parent graph.
A child suite can become its own parent gate when it needs another layer.

The target child-suite layout should be recorded as a model-derived split
before parent confidence is claimed. A partition map by itself is not enough.

TestMesh does not run your tests. Project adapters should run pytest, unittest,
Playwright, simulation runners, or shell commands, then feed structured evidence
into the TestMesh model.
"""


CODE_STRUCTURE_RECOMMENDATION_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Recommend an implementation structure from a FlowGuard functional model before production code is written.
Guards against: monolithic implementation plans, unclear state ownership, mixed side effects, missing facades, and test boundaries that do not map back to the model.
Use before editing: Ask for this recommendation when a model-first feature needs a code architecture plan before implementation.
Run: python .flowguard/code_structure_recommendation/run_checks.py
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
        source_model_path=".flowguard/checkout/model.py",
        parent_module_id="checkout",
        target_modules=(
            TargetModuleRecommendation(
                "orchestrator",
                path="checkout/orchestrator.py",
                owns_function_blocks=("RouteCheckout",),
                validation_boundaries=("route scenario test",),
                rationale="The orchestrator owns ordering only and does not own durable state.",
            ),
            TargetModuleRecommendation(
                "state",
                path="checkout/state.py",
                owns_state=("orders", "attempts"),
                validation_boundaries=("state shape test",),
                rationale="State and type definitions stay separate from transition logic.",
            ),
            TargetModuleRecommendation(
                "effects",
                path="checkout/effects.py",
                owns_function_blocks=("PersistOrder",),
                owns_side_effects=("write_order",),
                validation_boundaries=("effect idempotency replay",),
                rationale="Durable writes are isolated behind an adapter boundary.",
            ),
        ),
        function_block_map=(
            ("RouteCheckout", "orchestrator"),
            ("PersistOrder", "effects"),
        ),
        state_owner_map=(("orders", "state"), ("attempts", "state")),
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
- public entrypoint or facade plans when relevant;
- validation boundaries that keep the recommendation tied to executable model
  evidence.

This route recommends structure. It does not write production code and does not
replace StructureMesh. StructureMesh uses model-derived target structure when an
existing large script or module is being split.
"""


UI_FLOW_STRUCTURE_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Model UI-level interaction behavior first, then derive parent/child UI structure and text hierarchy from that model.
Guards against: layout-only UI plans, unmodeled controls, missing recovery actions, drifting menu levels, unstable global controls, duplicate information, overlapping same-level controls, ad hoc headings, over-prominent button text, and hierarchy recommendations that are not tied to UI state.
Use before editing: Ask for this route before visual design or frontend implementation when UI controls, states, navigation, panels, menus, overlays, or parent/child UI topology matter.
Run: python .flowguard/ui_flow_structure/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    UIControl,
    UIDisplayElement,
    UIFeatureContract,
    UIFeatureJourney,
    UIImplementationBlindspot,
    UIImplementationJourneyRun,
    UIImplementationStepEvidence,
    UIImplementationValidation,
    UIInteractionModel,
    UIJourneyCoverage,
    UIJourneyEntryPoint,
    UIRegionRecommendation,
    UIResidualBlindspot,
    UIStateNode,
    UIStructureDerivation,
    UITextElement,
    UITextHierarchyBlueprint,
    UITypographyToken,
    UITerminalActionAllowance,
    UITransition,
    review_ui_implementation_validation,
    review_ui_interaction_model,
    review_ui_journey_coverage,
    review_ui_structure_derivation,
    review_ui_text_hierarchy,
)


def interaction_model() -> UIInteractionModel:
    return UIInteractionModel(
        "project-workbench-ui-flow",
        initial_state_id="launch",
        source_product_model_id="project-workbench-product-flow",
        states=(
            UIStateNode(
                "launch",
                visible_controls=("new_project", "load_project", "settings", "run", "export", "exit"),
                enabled_controls=("new_project", "load_project", "settings", "exit"),
                disabled_controls=("run", "export"),
                rationale="The first screen lets the user create a new project, load an existing project, adjust settings, or exit.",
            ),
            UIStateNode(
                "new_project_setup",
                visible_controls=("create_project", "cancel", "settings"),
                enabled_controls=("create_project", "cancel", "settings"),
                disabled_controls=("run", "export"),
                rationale="A new project flow collects setup before workbench actions become available.",
            ),
            UIStateNode(
                "load_picker",
                visible_controls=("choose_file", "cancel", "settings"),
                enabled_controls=("choose_file", "cancel", "settings"),
                disabled_controls=("run", "export"),
                rationale="Loading an existing project scopes the UI to file choice or cancellation.",
            ),
            UIStateNode(
                "loaded",
                visible_controls=("run", "settings", "export"),
                enabled_controls=("run", "settings"),
                disabled_controls=("export",),
                rationale="A loaded file enables the primary run action.",
            ),
            UIStateNode(
                "running",
                visible_controls=("cancel", "settings"),
                enabled_controls=("cancel",),
                disabled_controls=("run", "export"),
                rationale="Running work scopes the UI to cancellation and status.",
            ),
            UIStateNode(
                "result_ready",
                visible_controls=("export", "settings"),
                enabled_controls=("export", "settings"),
                visible_displays=("summary_card", "result_table"),
                terminal=True,
                rationale="The result state is a success terminal that enables export.",
            ),
            UIStateNode(
                "failed",
                visible_controls=("retry", "settings"),
                enabled_controls=("retry", "settings"),
                recovery_controls=("retry",),
                failure=True,
                rationale="A recoverable failure offers retry and global settings.",
            ),
            UIStateNode(
                "cancelled",
                visible_controls=("exit", "settings"),
                enabled_controls=("exit", "settings"),
                terminal=True,
                rationale="Cancelled setup or load work reaches a terminal cancellation state.",
            ),
            UIStateNode(
                "exited",
                visible_controls=(),
                enabled_controls=(),
                terminal=True,
                rationale="Exit closes the app-level flow.",
            ),
        ),
        controls=(
            UIControl(
                "settings",
                label="Settings",
                level="global",
                placement_hint="top-toolbar",
                persistent=True,
                rationale="Settings are always available and should not drift between screens.",
            ),
            UIControl("new_project", label="New", level="primary", rationale="New project starts a launch-level feature journey."),
            UIControl("load_project", label="Load", level="primary", rationale="Load project starts a launch-level feature journey."),
            UIControl(
                "create_project",
                label="Create",
                level="primary",
                depends_on_states=("new_project_setup",),
                rationale="Create completes new project setup.",
            ),
            UIControl(
                "choose_file",
                label="Choose",
                level="primary",
                depends_on_states=("load_picker",),
                rationale="Choose loads an existing project file.",
            ),
            UIControl(
                "run",
                label="Run",
                level="primary",
                depends_on_states=("loaded",),
                rationale="Run advances the main workflow after input exists.",
            ),
            UIControl(
                "cancel",
                label="Cancel",
                level="contextual",
                depends_on_states=("running",),
                rationale="Cancel only exists while work is running.",
            ),
            UIControl(
                "retry",
                label="Retry",
                level="contextual",
                depends_on_states=("failed",),
                rationale="Retry recovers from a failed run.",
            ),
            UIControl(
                "export",
                label="Export",
                level="secondary",
                depends_on_states=("result_ready",),
                rationale="Export depends on completed results.",
            ),
            UIControl("exit", label="Exit", level="secondary", rationale="Exit closes the app-level flow."),
        ),
        displays=(
            UIDisplayElement(
                "summary_card",
                "run_summary",
                label="Run summary",
                display_type="status",
                depends_on_states=("result_ready",),
                rationale="The compact summary states the result once.",
            ),
            UIDisplayElement(
                "result_table",
                "result_rows",
                label="Result table",
                display_type="table",
                depends_on_states=("result_ready",),
                rationale="The table shows row-level output, not a duplicate summary.",
            ),
        ),
        transitions=(
            UITransition("click_new_project", "new_project", "launch", "new_project_setup", function_block="StartNewProject", output="new_project_setup", rationale="New project opens the setup state."),
            UITransition("create_project_success", "create_project", "new_project_setup", "loaded", function_block="CreateProject", output="project_created", rationale="Successful creation loads the workbench."),
            UITransition("create_project_failure", "create_project", "new_project_setup", "failed", function_block="CreateProject", output="recoverable_error", rationale="Creation can fail into recoverable state."),
            UITransition("click_load_project", "load_project", "launch", "load_picker", function_block="StartLoadProject", output="load_picker_opened", rationale="Load project opens the file picker state."),
            UITransition("load_project_success", "choose_file", "load_picker", "loaded", function_block="LoadProject", output="project_loaded", rationale="Successful load reaches the workbench."),
            UITransition("load_project_failure", "choose_file", "load_picker", "failed", function_block="LoadProject", output="recoverable_error", rationale="Loading can fail into recoverable state."),
            UITransition("click_run", "run", "loaded", "running", function_block="StartRun", output="run_started", rationale="Run starts the primary processing state."),
            UITransition("click_cancel", "cancel", "running", "loaded", function_block="CancelRun", output="run_cancelled", rationale="Cancel returns to the loaded state."),
            UITransition("click_cancel_new", "cancel", "new_project_setup", "cancelled", function_block="CancelNewProject", output="cancelled", rationale="Cancel leaves new project setup."),
            UITransition("click_cancel_load", "cancel", "load_picker", "cancelled", function_block="CancelLoadProject", output="cancelled", rationale="Cancel leaves load project setup."),
            UITransition("run_success", "run", "running", "result_ready", function_block="FinishRun", output="result_ready", rationale="A successful run exposes results."),
            UITransition("run_failure", "run", "running", "failed", function_block="FailRun", output="recoverable_error", rationale="A failed run enters a recoverable failure state."),
            UITransition("click_retry", "retry", "failed", "running", function_block="RetryRun", output="retry_started", rationale="Retry returns to the running state."),
            UITransition("click_export", "export", "result_ready", "result_ready", function_block="ExportResult", output="exported", rationale="Export is terminal-state output, not a new workflow phase."),
            UITransition("click_exit", "exit", "launch", "exited", function_block="ExitApp", output="exited", rationale="Exit closes the launch flow."),
            UITransition("click_exit_cancelled", "exit", "cancelled", "exited", function_block="ExitApp", output="exited", rationale="Exit closes the app after cancellation."),
        ),
        validation_boundaries=("UI scenario review", "browser state transition test"),
        rationale="The model separates launch, new-project, load-existing, loaded, running, result, failure, cancel, and exit UI states before any layout is derived.",
    )


def journey_coverage() -> UIJourneyCoverage:
    return UIJourneyCoverage(
        "project-workbench-journey-coverage",
        source_interaction_model_id="project-workbench-ui-flow",
        launch_state_id="launch",
        interaction_model_reviewed=True,
        entry_points=(
            UIJourneyEntryPoint("new_project", "new_project", "click_new_project", label="New", source_state_ids=("launch",), rationale="New project is a launch entry."),
            UIJourneyEntryPoint("load_project", "load_project", "click_load_project", label="Load", source_state_ids=("launch",), rationale="Load project is a launch entry."),
            UIJourneyEntryPoint("exit_app", "exit", "click_exit", label="Exit", source_state_ids=("launch",), rationale="Exit is available from launch."),
        ),
        feature_journeys=(
            UIFeatureJourney(
                "new_project",
                label="New project",
                entry_point_ids=("new_project",),
                required_state_ids=("new_project_setup", "loaded", "running"),
                required_event_ids=("click_new_project", "create_project_success", "create_project_failure", "click_run", "run_success", "run_failure"),
                success_terminal_state_ids=("result_ready",),
                failure_state_ids=("failed",),
                recovery_event_ids=("click_retry",),
                cancel_event_ids=("click_cancel_new", "click_cancel"),
                validation_boundaries=("journey scenario review",),
                rationale="A user can create a project, run it, recover from failure, or cancel setup.",
            ),
            UIFeatureJourney(
                "load_project",
                label="Load project",
                entry_point_ids=("load_project",),
                required_state_ids=("load_picker", "loaded", "running"),
                required_event_ids=("click_load_project", "load_project_success", "load_project_failure", "click_run", "run_success", "run_failure"),
                success_terminal_state_ids=("result_ready",),
                failure_state_ids=("failed",),
                recovery_event_ids=("click_retry",),
                cancel_event_ids=("click_cancel_load", "click_cancel"),
                validation_boundaries=("journey scenario review",),
                rationale="A user can load an existing project, run it, recover from failure, or cancel loading.",
            ),
            UIFeatureJourney(
                "exit_app",
                label="Exit app",
                entry_point_ids=("exit_app",),
                required_event_ids=("click_exit",),
                success_terminal_state_ids=("exited",),
                validation_boundaries=("journey scenario review",),
                rationale="A user can leave the app from launch.",
            ),
        ),
        terminal_action_allowances=(
            UITerminalActionAllowance(
                "result_ready",
                "click_export",
                "export",
                rationale="Export is a terminal-state output action.",
            ),
            UITerminalActionAllowance(
                "cancelled",
                "click_exit_cancelled",
                "exit",
                rationale="Exit closes the app after a cancelled setup or load branch.",
            ),
        ),
        residual_blindspots=(
            UIResidualBlindspot(
                "open_recent_project",
                feature_id="open_recent_project",
                reason="Recent-project shell history is outside this starter template.",
                owner="target app integration tests",
                validation_boundaries=("browser or desktop shell test",),
                rationale="The template records the omitted branch instead of claiming full coverage for it.",
            ),
            UIResidualBlindspot(
                "settings_panel",
                feature_id="settings_panel",
                control_ids=("settings",),
                reason="Settings are app-specific configuration details outside this starter template.",
                owner="target app settings journey review",
                validation_boundaries=("settings panel browser test",),
                rationale="The persistent settings button is explicitly bounded instead of becoming a silent no-op.",
            ),
        ),
        validation_boundaries=("journey scenario review", "browser state transition test"),
        rationale="Complete app-level UI coverage is declared from launch through feature terminals.",
    )


def feature_contract(feature_id: str, controls: tuple[str, ...], events: tuple[str, ...]) -> UIFeatureContract:
    return UIFeatureContract(
        feature_id,
        label=feature_id.replace("_", " ").title(),
        journey_ids=(feature_id,),
        required_control_ids=controls,
        required_event_ids=events,
        validation_boundaries=("functional model review",),
        rationale=f"{feature_id} is user-visible functionality that must align with a UI journey and implementation evidence.",
    )


def step(event_id: str, control_id: str, source_state_id: str, target_state_id: str) -> UIImplementationStepEvidence:
    return UIImplementationStepEvidence(
        f"{event_id}_step",
        event_id,
        control_id=control_id,
        source_state_id=source_state_id,
        target_state_id=target_state_id,
        method="browser",
        result="passed",
        evidence_ref=f"evidence://browser/{event_id}",
        observed_state_id=target_state_id,
        rationale=f"{event_id} was clicked or observed in the running UI.",
    )


def journey_run(feature_id: str, *steps: UIImplementationStepEvidence) -> UIImplementationJourneyRun:
    return UIImplementationJourneyRun(
        f"{feature_id}_implementation_run",
        feature_id,
        journey_id=feature_id,
        steps=steps,
        method="browser",
        result="passed",
        evidence_ref=f"evidence://browser/{feature_id}",
        model_revision="template-ui-rev-1",
        validation_boundaries=("browser click-through",),
        rationale=f"{feature_id} was validated from the running UI against the model-derived journey.",
    )


def implementation_validation() -> UIImplementationValidation:
    return UIImplementationValidation(
        "project-workbench-implementation-validation",
        source_feature_model_id="project-workbench-product-flow",
        source_interaction_model_id="project-workbench-ui-flow",
        source_journey_coverage_id="project-workbench-journey-coverage",
        implementation_target="local browser build",
        current_model_revision="template-ui-rev-1",
        feature_contracts=(
            feature_contract(
                "new_project",
                ("new_project", "create_project", "run", "retry"),
                (
                    "click_new_project",
                    "create_project_success",
                    "create_project_failure",
                    "click_run",
                    "run_success",
                    "run_failure",
                    "click_retry",
                    "click_cancel_new",
                    "click_cancel",
                ),
            ),
            feature_contract(
                "load_project",
                ("load_project", "choose_file", "run", "retry"),
                (
                    "click_load_project",
                    "load_project_success",
                    "load_project_failure",
                    "click_run",
                    "run_success",
                    "run_failure",
                    "click_retry",
                    "click_cancel_load",
                    "click_cancel",
                ),
            ),
            feature_contract("exit_app", ("exit",), ("click_exit",)),
        ),
        journey_runs=(
            journey_run(
                "new_project",
                step("click_new_project", "new_project", "launch", "new_project_setup"),
                step("create_project_success", "create_project", "new_project_setup", "loaded"),
                step("create_project_failure", "create_project", "new_project_setup", "failed"),
                step("click_run", "run", "loaded", "running"),
                step("run_success", "run", "running", "result_ready"),
                step("run_failure", "run", "running", "failed"),
                step("click_retry", "retry", "failed", "running"),
                step("click_cancel_new", "cancel", "new_project_setup", "cancelled"),
                step("click_cancel", "cancel", "running", "loaded"),
            ),
            journey_run(
                "load_project",
                step("click_load_project", "load_project", "launch", "load_picker"),
                step("load_project_success", "choose_file", "load_picker", "loaded"),
                step("load_project_failure", "choose_file", "load_picker", "failed"),
                step("click_run", "run", "loaded", "running"),
                step("run_success", "run", "running", "result_ready"),
                step("run_failure", "run", "running", "failed"),
                step("click_retry", "retry", "failed", "running"),
                step("click_cancel_load", "cancel", "load_picker", "cancelled"),
                step("click_cancel", "cancel", "running", "loaded"),
            ),
            journey_run(
                "exit_app",
                step("click_exit", "exit", "launch", "exited"),
            ),
        ),
        pure_ui_control_ids=("cancel", "export"),
        pure_ui_event_ids=("click_export", "click_exit_cancelled"),
        implementation_blindspots=(
            UIImplementationBlindspot(
                "settings_panel_implementation",
                feature_id="settings_panel",
                control_ids=("settings",),
                reason="Settings panel contents are app-specific and not part of this starter implementation.",
                owner="target app settings validation",
                validation_boundaries=("settings browser check",),
                rationale="The persistent settings control is bounded instead of silently claimed.",
            ),
            UIImplementationBlindspot(
                "open_recent_project_implementation",
                feature_id="open_recent_project",
                reason="Recent-project shell history is outside this starter template.",
                owner="target app integration tests",
                validation_boundaries=("browser or desktop shell test",),
                rationale="The omitted branch remains visible for downstream validation.",
            ),
        ),
        journey_coverage_reviewed=True,
        validation_boundaries=("browser click-through", "manual fallback for native dialogs"),
        rationale="Implemented UI evidence is generated from feature contracts and the reviewed journey coverage.",
    )


def structure_derivation() -> UIStructureDerivation:
    return UIStructureDerivation(
        "project-workbench-ui-structure",
        source_interaction_model_id="project-workbench-ui-flow",
        parent_surface_id="project-workbench",
        interaction_model_reviewed=True,
        target_regions=(
            UIRegionRecommendation(
                "top-toolbar",
                level="global",
                placement="top-toolbar",
                owns_controls=("settings",),
                stable_across_states=True,
                rationale="Global settings live in a first-level stable toolbar.",
            ),
            UIRegionRecommendation(
                "primary-workspace",
                level="primary",
                placement="main",
                owns_states=("launch", "new_project_setup", "load_picker", "loaded", "running", "result_ready", "cancelled", "exited"),
                owns_controls=("new_project", "load_project", "create_project", "choose_file", "run", "export", "exit"),
                owns_displays=("summary_card", "result_table"),
                owns_events=("click_new_project", "create_project_success", "click_load_project", "load_project_success", "click_run", "run_success", "click_export", "click_exit", "click_exit_cancelled"),
                stable_across_states=True,
                rationale="Main workflow actions live in the primary workspace.",
            ),
            UIRegionRecommendation(
                "failure-inspector",
                level="secondary",
                placement="right-inspector",
                parent_region_id="primary-workspace",
                owns_states=("failed",),
                owns_controls=("retry",),
                owns_events=("run_failure", "click_retry"),
                rationale="Recoverable failure is a child inspector of the main workflow.",
            ),
            UIRegionRecommendation(
                "cancel-overlay",
                level="overlay",
                placement="modal",
                parent_region_id="primary-workspace",
                owns_controls=("cancel",),
                owns_events=("click_cancel", "click_cancel_new", "click_cancel_load"),
                rationale="Cancel temporarily scopes the running parent flow.",
            ),
        ),
        state_region_map=(
            ("launch", "primary-workspace"),
            ("new_project_setup", "primary-workspace"),
            ("load_picker", "primary-workspace"),
            ("loaded", "primary-workspace"),
            ("running", "primary-workspace"),
            ("result_ready", "primary-workspace"),
            ("failed", "failure-inspector"),
            ("cancelled", "primary-workspace"),
            ("exited", "primary-workspace"),
        ),
        control_region_map=(
            ("settings", "top-toolbar"),
            ("new_project", "primary-workspace"),
            ("load_project", "primary-workspace"),
            ("create_project", "primary-workspace"),
            ("choose_file", "primary-workspace"),
            ("run", "primary-workspace"),
            ("export", "primary-workspace"),
            ("exit", "primary-workspace"),
            ("retry", "failure-inspector"),
            ("cancel", "cancel-overlay"),
        ),
        display_region_map=(
            ("summary_card", "primary-workspace"),
            ("result_table", "primary-workspace"),
        ),
        event_region_map=(
            ("click_new_project", "primary-workspace"),
            ("create_project_success", "primary-workspace"),
            ("create_project_failure", "failure-inspector"),
            ("click_load_project", "primary-workspace"),
            ("load_project_success", "primary-workspace"),
            ("load_project_failure", "failure-inspector"),
            ("click_run", "primary-workspace"),
            ("run_success", "primary-workspace"),
            ("run_failure", "failure-inspector"),
            ("click_retry", "failure-inspector"),
            ("click_cancel", "cancel-overlay"),
            ("click_cancel_new", "cancel-overlay"),
            ("click_cancel_load", "cancel-overlay"),
            ("click_export", "primary-workspace"),
            ("click_exit", "primary-workspace"),
            ("click_exit_cancelled", "primary-workspace"),
        ),
        hierarchy_edges=(("primary-workspace", "failure-inspector"), ("primary-workspace", "cancel-overlay")),
        persistent_control_ids=("settings",),
        contextual_control_ids=("retry", "cancel"),
        overlay_region_ids=("cancel-overlay",),
        stable_region_ids=("top-toolbar", "primary-workspace"),
        validation_boundaries=("browser state transition test", "design implementation review"),
        rationale="First-level persistent controls stay in the toolbar; phase controls and overlays follow the UI model.",
    )


def typography_token(token_id: str, level: int, roles: tuple[str, ...]) -> UITypographyToken:
    return UITypographyToken(
        token_id,
        hierarchy_level=level,
        text_roles=roles,
        scale=f"level-{level}",
        weight="regular" if level >= 4 else "semibold",
        color_role="default",
        rationale=f"{token_id} is reserved for {roles}.",
    )


def text_hierarchy() -> UITextHierarchyBlueprint:
    return UITextHierarchyBlueprint(
        "project-workbench-text-hierarchy",
        source_interaction_model_id="project-workbench-ui-flow",
        source_structure_derivation_id="project-workbench-ui-structure",
        parent_surface_id="project-workbench",
        structure_derivation_reviewed=True,
        typography_tokens=(
            typography_token("page-title", 1, ("page_title",)),
            typography_token("section-title", 2, ("section_title",)),
            typography_token("panel-title", 3, ("panel_title",)),
            typography_token("control-label", 4, ("button_label", "menu_label", "tab_label", "control_label")),
            typography_token("status-text", 4, ("status_text", "error_text")),
            typography_token("body-text", 5, ("body_text", "field_label", "data_value")),
            typography_token("caption-text", 6, ("caption", "help_text")),
        ),
        text_elements=(
            UITextElement(
                "surface_title",
                "page_title",
                "page-title",
                "surface_title",
                label="Project Workbench",
                region_id="primary-workspace",
                rationale="The parent surface title names the full workflow.",
            ),
            UITextElement(
                "workspace_title",
                "section_title",
                "section-title",
                "workflow_area",
                label="Run workspace",
                region_id="primary-workspace",
                parent_text_id="surface_title",
                rationale="The primary region gets one section title below the surface title.",
            ),
            UITextElement(
                "settings_label",
                "button_label",
                "control-label",
                "settings_action",
                label="Settings",
                region_id="top-toolbar",
                source_control_id="settings",
                rationale="The global settings control uses the shared control-label token.",
            ),
            UITextElement("new_project_label", "button_label", "control-label", "new_project_action", label="New", region_id="primary-workspace", source_control_id="new_project", rationale="New is an app-entry action label, not a heading."),
            UITextElement("load_project_label", "button_label", "control-label", "load_project_action", label="Load", region_id="primary-workspace", source_control_id="load_project", rationale="Load is an app-entry action label, not a heading."),
            UITextElement("run_label", "button_label", "control-label", "run_action", label="Run", region_id="primary-workspace", source_control_id="run", rationale="Run is an action label, not a heading."),
            UITextElement("export_label", "button_label", "control-label", "export_action", label="Export", region_id="primary-workspace", source_control_id="export", rationale="Export is an action label, not a heading."),
            UITextElement(
                "results_title",
                "panel_title",
                "panel-title",
                "results_panel",
                label="Results",
                region_id="primary-workspace",
                parent_text_id="workspace_title",
                source_state_ids=("result_ready",),
                rationale="The result panel is subordinate to the primary workspace.",
            ),
            UITextElement(
                "summary_value",
                "status_text",
                "status-text",
                "run_summary",
                label="Run completed",
                region_id="primary-workspace",
                source_display_id="summary_card",
                visible_in_states=("result_ready",),
                rationale="The summary card text uses a status role tied to the modeled display.",
            ),
            UITextElement(
                "result_table_caption",
                "caption",
                "caption-text",
                "result_rows",
                label="Result rows",
                region_id="primary-workspace",
                source_display_id="result_table",
                visible_in_states=("result_ready",),
                rationale="The table caption is less prominent than the result panel title.",
            ),
            UITextElement(
                "failure_title",
                "panel_title",
                "panel-title",
                "failure_panel",
                label="Recovery",
                region_id="failure-inspector",
                parent_text_id="workspace_title",
                source_state_ids=("failed",),
                rationale="The failure inspector title is a child of the main workflow section.",
            ),
            UITextElement(
                "retry_label",
                "button_label",
                "control-label",
                "retry_action",
                label="Retry",
                region_id="failure-inspector",
                source_control_id="retry",
                visible_in_states=("failed",),
                rationale="Retry is a recovery action label scoped to the failure inspector.",
            ),
            UITextElement(
                "cancel_label",
                "button_label",
                "control-label",
                "cancel_action",
                label="Cancel",
                region_id="cancel-overlay",
                source_control_id="cancel",
                visible_in_states=("running",),
                rationale="Cancel is an overlay action label, not a panel heading.",
            ),
        ),
        validation_boundaries=("design token review", "browser text hierarchy review"),
        rationale="Text roles and typography tokens are derived from source regions, controls, displays, and states.",
    )


def broken_interaction_model() -> UIInteractionModel:
    return UIInteractionModel(
        "broken-ui-flow",
        initial_state_id="empty",
        states=(UIStateNode("empty"), UIStateNode("failed", failure=True)),
        controls=(UIControl("delete", label="Delete", level="primary", destructive=True),),
        displays=(
            UIDisplayElement("chart", "same_summary", display_type="chart"),
            UIDisplayElement("text", "same_summary", display_type="text"),
        ),
        transitions=(UITransition("click_delete", "delete", "empty", "failed"),),
    )


def broken_structure_derivation() -> UIStructureDerivation:
    return UIStructureDerivation(
        "broken-ui-structure",
        source_interaction_model_id="project-workbench-ui-flow",
        parent_surface_id="project-workbench",
        target_regions=(UIRegionRecommendation("main"),),
        state_region_map=(("launch", "main"),),
        control_region_map=(("settings", "main"),),
        display_region_map=(("chart", "main"), ("text", "main")),
    )


def broken_journey_coverage() -> UIJourneyCoverage:
    return UIJourneyCoverage(
        "broken-project-workbench-journey",
        source_interaction_model_id="project-workbench-ui-flow",
        launch_state_id="launch",
        interaction_model_reviewed=True,
        entry_points=(
            UIJourneyEntryPoint("new_project", "new_project", "click_new_project", source_state_ids=("launch",), rationale="New project is modeled."),
        ),
        feature_journeys=(
            UIFeatureJourney(
                "load_project",
                entry_point_ids=("load_project",),
                required_state_ids=("load_picker",),
                required_event_ids=("missing_load_event",),
                success_terminal_state_ids=(),
                validation_boundaries=("journey review",),
                rationale="Broken because the load entry and terminal are missing.",
            ),
        ),
        residual_blindspots=(
            UIResidualBlindspot("open_recent_project", reason="deferred", rationale="Broken because no validation boundary is named."),
        ),
        validation_boundaries=("journey review",),
        rationale="Broken journey coverage demonstrates missing app-level branches.",
    )


def broken_implementation_validation() -> UIImplementationValidation:
    return UIImplementationValidation(
        "broken-project-workbench-implementation",
        source_feature_model_id="project-workbench-product-flow",
        source_interaction_model_id="project-workbench-ui-flow",
        source_journey_coverage_id="project-workbench-journey-coverage",
        implementation_target="local browser build",
        current_model_revision="template-ui-rev-1",
        feature_contracts=(
            feature_contract(
                "new_project",
                ("new_project", "create_project"),
                ("click_new_project", "create_project_success", "create_project_failure", "click_retry"),
            ),
            feature_contract(
                "load_project",
                ("load_project", "choose_file"),
                ("click_load_project", "load_project_success", "load_project_failure", "click_retry"),
            ),
        ),
        journey_runs=(
            journey_run(
                "new_project",
                step("click_new_project", "new_project", "launch", "new_project_setup"),
                step("create_project_success", "create_project", "new_project_setup", "loaded"),
            ),
        ),
        pure_ui_control_ids=("cancel",),
        journey_coverage_reviewed=True,
        validation_boundaries=("browser click-through",),
        rationale="Broken implementation validation omits load-project and failure/recovery evidence.",
    )


def broken_text_hierarchy() -> UITextHierarchyBlueprint:
    return UITextHierarchyBlueprint(
        "broken-text-hierarchy",
        source_interaction_model_id="project-workbench-ui-flow",
        source_structure_derivation_id="project-workbench-ui-structure",
        parent_surface_id="project-workbench",
        typography_tokens=(
            typography_token("section-title", 2, ("section_title",)),
            typography_token("hero-button", 1, ("button_label",)),
        ),
        text_elements=(
            UITextElement(
                "primary_section",
                "section_title",
                "section-title",
                "run_summary",
                label="Summary",
                region_id="primary-workspace",
                visible_in_states=("result_ready",),
                rationale="First duplicate summary heading.",
            ),
            UITextElement(
                "duplicate_summary",
                "section_title",
                "section-title",
                "run_summary",
                label="Summary again",
                region_id="primary-workspace",
                visible_in_states=("result_ready",),
                rationale="Second duplicate summary heading without a redundancy reason.",
            ),
            UITextElement(
                "import_label",
                "button_label",
                "hero-button",
                "new_project_action",
                label="New",
                region_id="primary-workspace",
                source_control_id="new_project",
                rationale="Broken because a button label uses a top-level token.",
            ),
        ),
        validation_boundaries=("text hierarchy review",),
        rationale="This intentionally broken blueprint demonstrates duplicate text and over-prominent action labels.",
    )


def run_checks():
    model = interaction_model()
    structure = structure_derivation()
    model_report = review_ui_interaction_model(model)
    journey_report = review_ui_journey_coverage(journey_coverage(), interaction_model=model)
    implementation_report = review_ui_implementation_validation(
        implementation_validation(),
        interaction_model=model,
        journey_coverage=journey_coverage(),
    )
    structure_report = review_ui_structure_derivation(structure, interaction_model=model)
    text_report = review_ui_text_hierarchy(
        text_hierarchy(),
        interaction_model=model,
        structure_derivation=structure,
    )
    broken_model_report = review_ui_interaction_model(broken_interaction_model())
    broken_journey_report = review_ui_journey_coverage(broken_journey_coverage(), interaction_model=model)
    broken_implementation_report = review_ui_implementation_validation(
        broken_implementation_validation(),
        interaction_model=model,
        journey_coverage=journey_coverage(),
    )
    broken_structure_report = review_ui_structure_derivation(
        broken_structure_derivation(),
        interaction_model=model,
    )
    broken_text_report = review_ui_text_hierarchy(
        broken_text_hierarchy(),
        interaction_model=model,
        structure_derivation=structure,
    )
    return (
        model_report,
        journey_report,
        implementation_report,
        structure_report,
        text_report,
        broken_model_report,
        broken_journey_report,
        broken_implementation_report,
        broken_structure_report,
        broken_text_report,
    )
'''


UI_FLOW_STRUCTURE_RUN_CHECKS_TEMPLATE = '''"""Run the UI Flow Structure template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    (
        model_report,
        journey_report,
        implementation_report,
        structure_report,
        text_report,
        broken_model,
        broken_journey,
        broken_implementation,
        broken_structure,
        broken_text,
    ) = run_checks()
    print(model_report.format_text())
    print()
    print(journey_report.format_text())
    print()
    print(implementation_report.format_text())
    print()
    print(structure_report.format_text())
    print()
    print(text_report.format_text())
    print()
    print(broken_model.format_text(max_findings=5))
    print()
    print(broken_journey.format_text(max_findings=5))
    print()
    print(broken_implementation.format_text(max_findings=25))
    print()
    print(broken_structure.format_text(max_findings=5))
    print()
    print(broken_text.format_text(max_findings=5))
    return 0 if (
        model_report.ok
        and journey_report.ok
        and implementation_report.ok
        and structure_report.ok
        and text_report.ok
        and not broken_model.ok
        and not broken_journey.ok
        and not broken_implementation.ok
        and not broken_structure.ok
        and not broken_text.ok
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


UI_FLOW_STRUCTURE_NOTES_TEMPLATE = """# FlowGuard UI Flow Structure Notes

Use this scaffold before visual design or frontend implementation when the UI
itself needs a model-first interaction flow.

## What This Route Produces

- a UI interaction model: initial state, controls, events, state nodes,
  transitions, failure and recovery states, terminal states, and availability;
- app-level journey coverage when the route claims complete UI coverage:
  launch state, entry points, feature journeys, terminal actions,
  failure/recovery handling, reachable visible/enabled control branches, and
  residual blindspots;
- a structure derivation from that model: parent/child UI nodes, first-level
  persistent menus, second-level contextual regions, third-level local actions,
  overlays, stable layout positions, and validation boundaries;
- a text hierarchy blueprint from that reviewed structure: page titles,
  section titles, panel titles, labels, button text, status text, captions,
  semantic text keys, typography tokens, parent/child text priority, and
  redundancy rationale;
- implementation validation when the route claims a running UI is implemented
  or complete: user-visible feature contracts, mapped journeys,
  browser/desktop/manual journey runs, step evidence, model revision, pure UI
  actions, and residual implementation blindspots;
- review findings when a control has no modeled event, a failure state has no
  recovery path, a destructive control is too prominent, or a persistent
  control is not assigned to a stable global region;
- journey coverage findings when a launch entry is missing, a reachable
  button/control has no modeled event, a modeled event is outside all journeys,
  a required feature path is unreachable, a terminal state has unclassified
  outgoing actions, or a residual blindspot lacks validation;
- implementation validation findings when a feature has no UI path, a visible
  control has no functional owner, a journey lacks click-through evidence,
  branch evidence is missing, or the recorded evidence is stale;
- redundancy findings when the same page/state shows the same semantic
  information twice or exposes multiple same-level controls for one function
  without an explicit rationale;
- text hierarchy findings when a button label uses a heading token, a child
  title is not visually subordinate to its parent title, or the same semantic
  text is repeated in one region and state without a modeled reason.

UI Flow Structure does not choose final brand styling or implement frontend
code. Use the derived structure and text hierarchy contract as input to Figma,
frontend implementation, browser checks, and design implementation review; feed
real click-through results back as implementation validation before claiming
the running UI is complete.
"""


STRUCTURE_MESH_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Review whether a large script or module can be split into owned child modules while preserving public behavior.
Guards against: missing child ownership, removed public entrypoints, missing facades, duplicate state or side-effect owners, unsafe dependency cycles, config drift, and overclaimed parity evidence.
Use before editing: Update this StructureMesh before splitting large scripts, moving module boundaries, extracting services, or changing public imports and CLI/API surfaces.
Run: python .flowguard/structure_mesh/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    CodeStructureRecommendation,
    EVIDENCE_ABSTRACT_GREEN,
    EVIDENCE_CONFORMANCE_GREEN,
    ModuleStructureEvidence,
    PublicEntrypointEvidence,
    StructureMeshPlan,
    StructurePartitionItem,
    TargetModuleRecommendation,
    review_structure_mesh,
)


def target_structure_recommendation() -> CodeStructureRecommendation:
    return CodeStructureRecommendation(
        "legacy-reporter-target-structure",
        source_model_id="legacy-reporter-functional-model",
        source_model_path=".flowguard/legacy_reporter/model.py",
        parent_module_id="legacy_reporter",
        target_modules=(
            TargetModuleRecommendation(
                "cli",
                path="reporter/cli.py",
                owns_function_blocks=("parse_args",),
                public_entrypoints=("python -m reporter",),
                validation_boundaries=("cli parity test",),
                rationale="CLI parsing and the public entrypoint stay together behind the facade.",
            ),
            TargetModuleRecommendation(
                "config",
                path="reporter/config.py",
                owns_function_blocks=("load_config",),
                owns_config=("report_defaults",),
                validation_boundaries=("config default parity test",),
                rationale="Configuration defaults have one owner to avoid drift.",
            ),
            TargetModuleRecommendation(
                "renderer",
                path="reporter/renderer.py",
                owns_function_blocks=("render_report",),
                owns_state=("render_cache",),
                owns_side_effects=("write_report",),
                validation_boundaries=("render replay",),
                rationale="Rendering owns cached render state and report writing side effects.",
            ),
        ),
        function_block_map=(
            ("parse_args", "cli"),
            ("load_config", "config"),
            ("render_report", "renderer"),
        ),
        state_owner_map=(("render_cache", "renderer"),),
        side_effect_owner_map=(("write_report", "renderer"),),
        config_owner_map=(("report_defaults", "config"),),
        public_entrypoint_map=(("python -m reporter", "cli"),),
        facade_module_id="cli",
        validation_boundaries=("cli parity test", "config default parity test", "render replay"),
        rationale="The FlowGuard functional model separates CLI intake, config loading, and rendering side effects.",
    )


def routine_plan() -> StructureMeshPlan:
    return StructureMeshPlan(
        parent_module_id="legacy_reporter",
        target_structure=target_structure_recommendation(),
        decision_scope="routine",
        required_evidence_tier=EVIDENCE_ABSTRACT_GREEN,
        partition_items=(
            StructurePartitionItem("parse_args", owner_module_id="cli"),
            StructurePartitionItem("load_config", owner_module_id="config"),
            StructurePartitionItem("render_report", owner_module_id="renderer"),
        ),
        child_modules=(
            ModuleStructureEvidence(
                "cli",
                path="reporter/cli.py",
                owns_functions=("parse_args",),
                behavior_parity_tier=EVIDENCE_ABSTRACT_GREEN,
            ),
            ModuleStructureEvidence(
                "config",
                path="reporter/config.py",
                owns_functions=("load_config",),
                owns_config=("report_defaults",),
                behavior_parity_tier=EVIDENCE_ABSTRACT_GREEN,
            ),
            ModuleStructureEvidence(
                "renderer",
                path="reporter/renderer.py",
                owns_functions=("render_report",),
                owns_state=("render_cache",),
                owns_side_effects=("write_report",),
                behavior_parity_tier=EVIDENCE_ABSTRACT_GREEN,
            ),
            ModuleStructureEvidence(
                "release_packaging",
                path="reporter/release.py",
                layer="release",
                release_required=True,
                behavior_parity_current=False,
                behavior_parity_tier=EVIDENCE_CONFORMANCE_GREEN,
                not_ready_reason="release packaging check is deferred during routine refactor work",
            ),
        ),
        public_entrypoints=(
            PublicEntrypointEvidence(
                "python -m reporter",
                entrypoint_type="cli",
                old_path="reporter.py",
                new_path="reporter/__main__.py",
                parity_evidence_tier=EVIDENCE_ABSTRACT_GREEN,
            ),
        ),
    )


def broken_plan() -> StructureMeshPlan:
    return StructureMeshPlan(
        parent_module_id="legacy_reporter",
        decision_scope="release",
        required_evidence_tier=EVIDENCE_CONFORMANCE_GREEN,
        partition_items=(
            StructurePartitionItem("parse_args", owner_module_id="cli"),
            StructurePartitionItem("load_config", owner_module_id="config"),
            StructurePartitionItem("render_report", owner_module_id="renderer"),
        ),
        child_modules=(
            ModuleStructureEvidence(
                "cli",
                path="reporter/cli.py",
                owns_functions=("parse_args",),
                owns_state=("shared_context",),
                dependency_cycles=("cli->renderer->cli",),
                behavior_parity_tier=EVIDENCE_ABSTRACT_GREEN,
            ),
            ModuleStructureEvidence(
                "renderer",
                path="reporter/renderer.py",
                owns_functions=("render_report",),
                owns_state=("shared_context",),
                owns_side_effects=("write_report",),
                facade_retained=False,
                config_defaults_changed=True,
                behavior_parity_current=False,
                behavior_parity_tier=EVIDENCE_ABSTRACT_GREEN,
            ),
        ),
        public_entrypoints=(
            PublicEntrypointEvidence(
                "python -m reporter",
                entrypoint_type="cli",
                compatibility_preserved=False,
                facade_available=False,
                parity_evidence_current=False,
                parity_evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                release_required=True,
            ),
        ),
    )


def run_checks():
    return review_structure_mesh(routine_plan()), review_structure_mesh(broken_plan())
'''


STRUCTURE_MESH_RUN_CHECKS_TEMPLATE = '''"""Run the StructureMesh template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    routine, broken = run_checks()
    print(routine.format_text())
    print()
    print(broken.format_text(max_findings=5))
    return 0 if routine.ok and not broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


STRUCTURE_MESH_NOTES_TEMPLATE = """# FlowGuard StructureMesh Notes

Use this scaffold to keep a module or script split explicit before code moves.

## What StructureMesh Reviews

- which child module owns each function, state item, config key, side effect,
  public entrypoint, or behavior contract;
- which FlowGuard functional model derived the target child-module structure
  before the existing script or module is split;
- whether old public imports, CLI commands, API routes, and data shapes remain
  available through a facade or compatibility layer;
- whether duplicated state, duplicated side effects, unsafe dependency cycles,
  config drift, or stale parity evidence make the split unsafe;
- whether routine work can proceed while release-only checks remain visible as
  deferred obligations.

StructureMesh does not refactor code. Project adapters or agents should collect
source inventory, model-derived target structure, ownership, dependency, and
parity evidence, then feed that evidence into the StructureMesh model.
"""


EXISTING_MODEL_PREFLIGHT_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Review whether an agent grounded an existing-system change in the FlowGuard models that already exist.
Guards against: proposing new modules, rules, workflows, or ownership boundaries before checking existing FunctionBlocks, state owners, side-effect owners, public entrypoints, and model responsibilities.
Use before editing: Run this before implementation, OpenSpec proposals, major architecture changes, or risky behavior changes in an existing modeled system.
Run: python .flowguard/existing_model_preflight/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    DuplicateBoundaryRisk,
    ExistingModelPreflight,
    ExistingOwnershipSnapshot,
    ModelContextHit,
    REUSE_DECISION_ADD_CHILD_MODEL,
    REUSE_DECISION_EXTEND_EXISTING,
    review_existing_model_preflight,
)


def correct_preflight():
    return ExistingModelPreflight(
        "router-existing-model-preflight",
        "Extend router scheduling behavior",
        mode="full",
        model_search_performed=True,
        search_paths=(".flowguard/router", "docs"),
        relevant_models=(
            ModelContextHit(
                "router-flow",
                model_path=".flowguard/router/model.py",
                evidence_id="router:v1",
                evidence_tier="abstract_green",
                responsibilities=("route scheduling",),
                function_blocks=("RouteTask",),
                state_owned=("pending_tasks",),
                side_effects_owned=("dispatch_task",),
                public_entrypoints=("router.dispatch",),
                validation_evidence=("router scenario replay",),
            ),
        ),
        ownership_snapshot=ExistingOwnershipSnapshot(
            function_block_owners=(("RouteTask", "router-flow"),),
            state_owners=(("pending_tasks", "router-flow"),),
            side_effect_owners=(("dispatch_task", "router-flow"),),
            public_entrypoint_owners=(("router.dispatch", "router-flow"),),
        ),
        reuse_decision=REUSE_DECISION_EXTEND_EXISTING,
        downstream_routes=("development_process_flow",),
        rationale="The existing router model owns task dispatch, so extend that boundary instead of creating a parallel scheduler.",
    )


def broken_duplicate_preflight():
    return ExistingModelPreflight(
        "broken-parallel-scheduler",
        "Create a parallel scheduler",
        mode="full",
        model_search_performed=True,
        search_paths=(".flowguard/router",),
        relevant_models=(correct_preflight().relevant_models[0],),
        ownership_snapshot=ExistingOwnershipSnapshot(
            state_owners=(("pending_tasks", "router-flow"),),
        ),
        reuse_decision=REUSE_DECISION_ADD_CHILD_MODEL,
        downstream_routes=("model_mesh_maintenance",),
        proposed_new_boundaries=("parallel-scheduler",),
        rationale="A new child was proposed, but the duplicate state risk is unresolved.",
        duplicate_risks=(
            DuplicateBoundaryRisk(
                "state",
                "pending_tasks",
                "router-flow",
                proposed_owner_id="parallel-scheduler",
            ),
        ),
    )


def run_checks():
    return (
        review_existing_model_preflight(correct_preflight()),
        review_existing_model_preflight(broken_duplicate_preflight()),
    )
'''


EXISTING_MODEL_PREFLIGHT_RUN_CHECKS_TEMPLATE = '''"""Run the existing-model preflight template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    correct, broken = run_checks()
    print(correct.format_text())
    print()
    print(broken.format_text(max_findings=5))
    return 0 if correct.ok and not broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


EXISTING_MODEL_PREFLIGHT_NOTES_TEMPLATE = """# FlowGuard Existing Model Preflight Notes

Use this scaffold before discussing, proposing, or implementing a non-trivial
change in an existing modeled system.

## What Existing Model Preflight Reviews

- which existing FlowGuard models were searched;
- which model responsibilities, FunctionBlocks, state fields, side effects,
  and public entrypoints already own the requested behavior;
- whether the change should reuse an existing boundary, extend an existing
  model, add a child model, or create a new boundary;
- whether duplicate model, state, side-effect, entrypoint, or responsibility
  ownership is resolved before downstream work starts;
- which downstream FlowGuard route should handle the concrete work.

Use a light grounding note for discussion and early analysis. Use a full
structured preflight before implementation, OpenSpec proposals, major
architecture changes, or risky behavior changes.
"""


MODEL_SIMILARITY_CONSOLIDATION_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Compare FlowGuard model signatures before creating parallel model or code boundaries.
Guards against: duplicate model ownership, unsafe shared-kernel extraction, false-friend consolidation, adapter-only duplication, and similarity advice without current evidence.
Use before editing: Run this before adding a model boundary, recommending code structure, or turning similar workflows into shared code.
Run: python .flowguard/model_similarity_consolidation/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    ModelSignature,
    ModelSimilarityEvidence,
    ModelSimilarityPlan,
    review_model_similarity_consolidation,
)


def correct_plan() -> ModelSimilarityPlan:
    return ModelSimilarityPlan(
        "checkout-model-similarity",
        signatures=(
            ModelSignature(
                "checkout-simple",
                workflow_family="checkout",
                variant_id="simple",
                function_blocks=("ValidateOrder", "PersistOrder"),
                inputs=("OrderInput",),
                outputs=("OrderStored",),
                state_owned=("orders",),
                side_effects_owned=("write_order",),
                invariants=("no_duplicate_order",),
                failure_modes=("duplicate_submit",),
                public_entrypoints=("checkout.submit",),
                evidence_ids=("sim:checkout-family",),
            ),
            ModelSignature(
                "checkout-retry",
                workflow_family="checkout",
                variant_id="retry",
                function_blocks=("ValidateOrder", "PersistOrder"),
                inputs=("OrderInput",),
                outputs=("OrderStored", "RetryScheduled"),
                state_owned=("orders",),
                side_effects_owned=("write_order",),
                invariants=("no_duplicate_order",),
                failure_modes=("duplicate_submit",),
                public_entrypoints=("checkout.submit_with_retry",),
                evidence_ids=("sim:checkout-family",),
            ),
        ),
        comparison_pairs=(("checkout-simple", "checkout-retry"),),
        evidence=(
            ModelSimilarityEvidence(
                "sim:checkout-family",
                summary="family review confirmed shared checkout kernel with variant retry edge",
            ),
        ),
        require_current_evidence=True,
        rationale="Use similarity review before creating a parallel checkout workflow.",
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

## What Model Similarity Reviews

- stable model signatures, including FunctionBlocks, inputs, outputs, state,
  side effects, invariants, failure modes, contracts, entrypoints, and evidence;
- typed relations such as same workflow, family variant, symmetric flow, shared
  kernel, duplicate boundary, ownership overlap, adapter-only difference,
  evidence duplicate, false friend, and unrelated;
- route handoffs to Existing Model Preflight, ModelMesh, Architecture
  Reduction, Code Structure Recommendation, StructureMesh, Model-Test
  Alignment, or manual review;
- evidence gaps that keep similarity advice scoped rather than full confidence.

Similarity advice is not an implementation proof. Use the downstream route it
names before merging models, extracting shared code, pruning adapters, or
claiming broad test and code confidence.
"""


RISK_EVIDENCE_LEDGER_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Review whether a final FlowGuard confidence claim is backed by model obligations, public code contracts, recurring defect-family gates, model/test split gates, and current evidence.
Guards against: coarse models hiding untested internal branches, oversized direct model evidence bypassing ModelMesh, slow or broad validation bypassing TestMesh, recurring same-class misses hiding behind local point fixes, tests covering only helper paths, skipped or stale evidence being treated as pass, and background progress being counted as final proof.
Use before editing: Run this before claiming done, release-ready, or fully validated after model/test/code changes.
Run: python .flowguard/risk_evidence_ledger/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    RISK_PROOF_SCOPE_INTERNAL_PATH,
    RISK_PROOF_STATUS_PASSED,
    RISK_PROOF_STATUS_PROGRESS_ONLY,
    ProofArtifactRef,
    RiskEvidenceLedgerPlan,
    RiskEvidenceProof,
    RiskEvidenceRow,
    review_risk_evidence_ledger,
)


def correct_ledger() -> RiskEvidenceLedgerPlan:
    return RiskEvidenceLedgerPlan(
        "checkout-final-confidence",
        require_code_contracts=True,
        require_proof_artifacts=True,
        rows=(
            RiskEvidenceRow(
                "duplicate_submit",
                description="Repeated submit must not create duplicate orders.",
                model_obligation_id="model:dedupe-submit",
                code_contract_id="api:submit_order",
                proof_evidence_ids=("test:duplicate-submit",),
                defect_family_id="defect-family:duplicate-submit",
                defect_family_gate_required=True,
            ),
            RiskEvidenceRow(
                "invalid_payment",
                description="Invalid payment must stop before storage.",
                model_obligation_id="model:reject-invalid-payment",
                code_contract_id="api:submit_order",
                proof_evidence_ids=("replay:invalid-payment",),
            ),
        ),
        proof_evidence=(
            RiskEvidenceProof(
                "test:duplicate-submit",
                result_status=RISK_PROOF_STATUS_PASSED,
                producer_route="model_test_alignment",
                command="python -m unittest tests.test_checkout",
                summary="external API duplicate-submit test passed",
                proof_artifact=ProofArtifactRef(
                    "artifact:test-duplicate-submit",
                    result_status=RISK_PROOF_STATUS_PASSED,
                    exit_code=0,
                    result_path="tmp/test-duplicate-submit.json",
                    artifact_fingerprints={"tmp/test-duplicate-submit.json": "sha256:template"},
                    covered_obligation_ids=("model:dedupe-submit",),
                ),
            ),
            RiskEvidenceProof(
                "replay:invalid-payment",
                proof_kind="replay",
                result_status=RISK_PROOF_STATUS_PASSED,
                producer_route="conformance_replay",
                command="python .flowguard/checkout/run_checks.py",
                summary="representative replay covered invalid payment",
                proof_artifact=ProofArtifactRef(
                    "artifact:replay-invalid-payment",
                    result_status=RISK_PROOF_STATUS_PASSED,
                    exit_code=0,
                    result_path="tmp/replay-invalid-payment.json",
                    artifact_fingerprints={"tmp/replay-invalid-payment.json": "sha256:template"},
                    covered_obligation_ids=("model:reject-invalid-payment",),
                ),
            ),
        ),
    )


def broken_internal_only_ledger() -> RiskEvidenceLedgerPlan:
    return RiskEvidenceLedgerPlan(
        "internal-only-confidence",
        require_code_contracts=True,
        rows=(
            RiskEvidenceRow(
                "duplicate_submit",
                description="Repeated submit must not create duplicate orders.",
                model_obligation_id="model:dedupe-submit",
                code_contract_id="api:submit_order",
                proof_evidence_ids=("test:helper-dedupe",),
            ),
        ),
        proof_evidence=(
            RiskEvidenceProof(
                "test:helper-dedupe",
                result_status=RISK_PROOF_STATUS_PASSED,
                assertion_scope=RISK_PROOF_SCOPE_INTERNAL_PATH,
                producer_route="model_test_alignment",
                command="python -m unittest tests.test_helpers",
                summary="helper path passed but external submit_order was not exercised",
            ),
        ),
    )


def broken_progress_only_ledger() -> RiskEvidenceLedgerPlan:
    return RiskEvidenceLedgerPlan(
        "progress-only-confidence",
        rows=(
            RiskEvidenceRow(
                "release_regression",
                description="Release regression must finish before publication.",
                model_obligation_id="model:release-regression",
                proof_evidence_ids=("suite:release-regression",),
            ),
        ),
        proof_evidence=(
            RiskEvidenceProof(
                "suite:release-regression",
                result_status=RISK_PROOF_STATUS_PROGRESS_ONLY,
                producer_route="test_mesh_maintenance",
                command="python -m pytest -q",
                summary="suite is still running, so it is liveness only",
            ),
        ),
    )


def broken_missing_defect_family_gate_ledger() -> RiskEvidenceLedgerPlan:
    return RiskEvidenceLedgerPlan(
        "missing-defect-family-gate",
        rows=(
            RiskEvidenceRow(
                "duplicate_submit",
                description="Repeated same-class submit miss must be promoted before full confidence.",
                model_obligation_id="model:dedupe-submit",
                proof_evidence_ids=("test:duplicate-submit",),
                defect_family_gate_required=True,
            ),
        ),
        proof_evidence=(
            RiskEvidenceProof(
                "test:duplicate-submit",
                result_status=RISK_PROOF_STATUS_PASSED,
                producer_route="model_test_alignment",
                command="python -m unittest tests.test_checkout",
                summary="observed and same-class test evidence passed, but no defect-family gate was consumed",
            ),
        ),
    )


def broken_missing_model_split_gate_ledger() -> RiskEvidenceLedgerPlan:
    return RiskEvidenceLedgerPlan(
        "missing-model-split-gate",
        rows=(
            RiskEvidenceRow(
                "oversized_checkout_model",
                description="Oversized checkout model must consume a current ModelMesh split before full confidence.",
                model_obligation_id="model:checkout-parent",
                proof_evidence_ids=("model:checkout-direct",),
                model_split_gate_required=True,
            ),
        ),
        proof_evidence=(
            RiskEvidenceProof(
                "model:checkout-direct",
                result_status=RISK_PROOF_STATUS_PASSED,
                producer_route="model_mesh_maintenance",
                command="python .flowguard/checkout/run_checks.py",
                summary="direct model evidence passed, but no current parent/child split gate was consumed",
            ),
        ),
    )


def run_checks():
    return (
        review_risk_evidence_ledger(correct_ledger()),
        review_risk_evidence_ledger(broken_internal_only_ledger()),
        review_risk_evidence_ledger(broken_progress_only_ledger()),
        review_risk_evidence_ledger(broken_missing_defect_family_gate_ledger()),
        review_risk_evidence_ledger(broken_missing_model_split_gate_ledger()),
    )
'''


RISK_EVIDENCE_LEDGER_RUN_CHECKS_TEMPLATE = '''"""Run the Risk Evidence Ledger template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    correct, internal_only, progress_only, missing_defect_family, missing_model_split = run_checks()
    print(correct.format_text())
    print()
    print(internal_only.format_text(max_findings=5))
    print()
    print(progress_only.format_text(max_findings=5))
    print()
    print(missing_defect_family.format_text(max_findings=5))
    print()
    print(missing_model_split.format_text(max_findings=5))
    expected_blockers = (
        not internal_only.ok
        and internal_only.decision == "internal_path_only_evidence"
        and not progress_only.ok
        and progress_only.decision == "proof_evidence_not_passing"
        and not missing_defect_family.ok
        and missing_defect_family.decision == "missing_defect_family_gate"
        and not missing_model_split.ok
        and missing_model_split.decision == "missing_model_split_gate"
    )
    return 0 if correct.ok and expected_blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


RISK_EVIDENCE_LEDGER_NOTES_TEMPLATE = """# FlowGuard Risk Evidence Ledger Notes

Use this scaffold before final confidence claims.

## What The Ledger Reviews

- each user-facing risk has a FlowGuard model obligation owner;
- each required public behavior has a code contract when the project requires it;
- each recurring or high-risk same-class model miss has a current defect-family gate;
- each required ModelMesh or TestMesh split gate is current before broad parent
  confidence is claimed;
- each risk has current proof evidence from tests, replay, route reports, or manual validation;
- internal-path-only tests, stale evidence, skipped checks, and progress-only background runs are visible;
- scoped-out risks have explicit reasons and cannot be silently counted as fully proven.

The ledger is a final claim boundary. It summarizes evidence produced by
Model-Test Alignment, TestMesh, ModelMesh, StructureMesh, UI Flow Structure,
DevelopmentProcessFlow, conformance replay, and ordinary tests. It does not run
those routes for you.
"""


LAYERED_BOUNDARY_PROOF_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Review whether a parent model is fully covered by child models, child boundaries are disjoint, child evidence reattaches to the parent, and leaf code boundaries have complete finite Input x State coverage.
Guards against: parent coverage gaps, illegal child overlap, stale child evidence, coarse leaf models, and happy-path-only boundary testing.
Use before editing: Run this before claiming parent model, full-system, release, or done confidence from a parent/child FlowGuard model tree.
Run: python .flowguard/layered_boundary_proof/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    ChildProofContract,
    ChildReattachmentProof,
    LeafBoundaryMatrix,
    LeafBoundaryMatrixCell,
    LayeredBoundaryProofPlan,
    ParentCoverageItem,
    ProofArtifactRef,
    review_layered_boundary_proof,
)


def proof_artifact(artifact_id: str, *covered: str) -> ProofArtifactRef:
    result_path = f"tmp/{artifact_id.replace(':', '_')}.json"
    return ProofArtifactRef(
        artifact_id,
        result_status="passed",
        exit_code=0,
        result_path=result_path,
        artifact_fingerprints={result_path: "sha256:template"},
        covered_obligation_ids=covered,
    )


def correct_layered_proof() -> LayeredBoundaryProofPlan:
    return LayeredBoundaryProofPlan(
        "checkout-layered-boundary-proof",
        "checkout-parent",
        require_proof_artifacts=True,
        parent_items=(
            ParentCoverageItem("validate-submit", owner_model_id="validate-submit"),
        ),
        child_contracts=(
            ChildProofContract(
                "validate-submit",
                evidence_id="validate-submit:v1",
                responsibilities=("validate-submit",),
                functions_owned=("validate_submit",),
                inputs_accepted=("empty-submit", "valid-submit"),
                outputs_emitted=("Rejected", "Accepted"),
                state_owned=("seen_ids",),
                contracts_out=("submit-validation",),
                is_leaf=True,
                proof_artifact=proof_artifact("artifact:validate-submit-child", "validate-submit"),
            ),
        ),
        reattachment_proofs=(
            ChildReattachmentProof(
                "validate-submit",
                consumed_evidence_id="validate-submit:v1",
                expected_inputs=("empty-submit", "valid-submit"),
                expected_outputs=("Rejected", "Accepted"),
                expected_state_owned=("seen_ids",),
                expected_contracts_out=("submit-validation",),
            ),
        ),
        leaf_matrices=(
            LeafBoundaryMatrix(
                "validate-submit",
                matrix_id="validate-submit:matrix:v1",
                input_cases=("empty-submit",),
                state_cases=("idle",),
                expected_cell_ids=("empty-submit:idle",),
                cells=(
                    LeafBoundaryMatrixCell(
                        "empty-submit:idle",
                        "empty-submit",
                        "idle",
                        expected_outputs=("Rejected",),
                        observed_outputs=("Rejected",),
                        expected_next_states=("idle",),
                        observed_next_states=("idle",),
                        expected_error_paths=("ValueError",),
                        observed_error_paths=("ValueError",),
                        evidence_ids=("test:reject-empty-submit",),
                        proof_artifact=proof_artifact(
                            "artifact:reject-empty-submit-cell",
                            "test:reject-empty-submit",
                        ),
                    ),
                ),
            ),
        ),
    )


def broken_layered_proof() -> LayeredBoundaryProofPlan:
    return LayeredBoundaryProofPlan(
        "broken-checkout-layered-boundary-proof",
        "checkout-parent",
        parent_items=(
            ParentCoverageItem("validate-submit"),
        ),
        child_contracts=(
            ChildProofContract(
                "validate-submit",
                evidence_id="validate-submit:v2",
                responsibilities=("validate-submit",),
                functions_owned=("validate_submit",),
                inputs_accepted=("empty-submit", "valid-submit"),
                outputs_emitted=("Rejected", "Accepted"),
                state_owned=("seen_ids",),
                contracts_out=("submit-validation",),
                is_leaf=True,
            ),
        ),
        reattachment_proofs=(
            ChildReattachmentProof(
                "validate-submit",
                consumed_evidence_id="validate-submit:v1",
                expected_inputs=("empty-submit", "valid-submit"),
                expected_outputs=("Rejected", "Accepted"),
                expected_state_owned=("seen_ids",),
                expected_contracts_out=("submit-validation",),
            ),
        ),
        leaf_matrices=(
            LeafBoundaryMatrix(
                "validate-submit",
                matrix_id="validate-submit:matrix:v2",
                input_cases=("empty-submit", "valid-submit"),
                state_cases=("idle",),
                expected_cell_ids=("empty-submit:idle", "valid-submit:idle"),
                cells=(
                    LeafBoundaryMatrixCell(
                        "empty-submit:idle",
                        "empty-submit",
                        "idle",
                        expected_outputs=("Rejected",),
                        observed_outputs=("Rejected", "Accepted"),
                        expected_next_states=("idle",),
                        observed_next_states=("idle",),
                        evidence_ids=("test:reject-empty-submit",),
                    ),
                ),
            ),
        ),
    )


def run_checks():
    return (
        review_layered_boundary_proof(correct_layered_proof()),
        review_layered_boundary_proof(broken_layered_proof()),
    )
'''


LAYERED_BOUNDARY_PROOF_RUN_CHECKS_TEMPLATE = '''"""Run the Layered Boundary Proof template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    correct, broken = run_checks()
    print(correct.format_text())
    print()
    print(broken.format_text(max_findings=5))
    return 0 if correct.ok and not broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


LAYERED_BOUNDARY_PROOF_NOTES_TEMPLATE = """# FlowGuard Layered Boundary Proof Notes

Use this scaffold when a FlowGuard model tree needs a parent-to-leaf proof
chain.

## The Four Tables

- Parent coverage: every parent responsibility is owned by a child, parent,
  read-only boundary, shared kernel, bridge, or explicit out-of-scope
  disposition.
- Child disjointness: child models do not illegally share functions, state,
  side effects, invariants, risk classes, or responsibilities.
- Child reattachment: the parent consumes each child's current evidence id and
  only the inputs, outputs, state owners, side effects, and contracts that the
  parent is allowed to consume.
- Leaf boundary matrix: each leaf model has complete finite
  `Input x State -> Set(Output x State)` evidence, including next states, state
  writes, side effects, and error paths.
- When input and state axes are declared, the expected cells must equal their
  Cartesian product; unexpected cells or missing observed behavior are blockers.

If a leaf matrix is too large, split the model further or record an explicit
scoped exemption. Progress-only, skipped, stale, or release-only evidence is
not a green proof.
"""


FLOWGUARD_CLOSURE_CONTRACT_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Reviews whether a broad done, release, publish, or production-confidence claim
has consumed current FlowGuard evidence from runtime traces, artifact
freshness, model quality, same-class misses, runtime gateway inventory, and the
risk ledger.

Guards against:
- treating a model pass or test pass as complete FlowGuard use;
- runtime traces that are not mapped back to model obligations;
- changed artifacts that still rely on stale proof;
- unresolved model-quality or same-class model-miss gaps;
- critical runtime writes without gateway inventory evidence.

Use before editing:
final confidence reports, runtime gateway adoption, release closure, or route
closure packages that depend on multiple FlowGuard evidence routes.

Run:
python .flowguard/closure_contract/run_checks.py

Replace the sample IDs with the project evidence IDs for the claim under
review.
"""

from __future__ import annotations

from flowguard import (
    CLOSURE_CONFIDENCE_FULL,
    CLOSURE_REPORT_RISK_LEDGER,
    CLOSURE_REPORT_RUNTIME_GATEWAY,
    MODEL_QUALITY_HIDDEN_STATE,
    ArtifactInvalidation,
    ClosureEvidenceReport,
    FlowGuardClosureContractPlan,
    ModelQualitySignal,
    RuntimeGatewayInventoryClosure,
    RuntimeTraceMapping,
    SameClassMissClosure,
    review_flowguard_closure_contract,
)


def evidence_report(report_id, report_kind=CLOSURE_REPORT_RISK_LEDGER, **overrides):
    values = {
        "report_id": report_id,
        "report_kind": report_kind,
        "decision": f"{report_kind}:green",
        "ok": True,
        "current": True,
        "confidence": CLOSURE_CONFIDENCE_FULL,
        "result_status": "passed",
        "proof_artifact_ids": (f"artifact:{report_id}",),
    }
    values.update(overrides)
    return ClosureEvidenceReport(**values)


def correct_closure_plan():
    return FlowGuardClosureContractPlan(
        claim_id="release:sample",
        runtime_trace_mappings=(
            RuntimeTraceMapping(
                "trace:critical-write",
                model_obligation_id="model:critical-write",
                source_evidence_id="artifact:runtime-replay",
            ),
        ),
        artifact_invalidations=(
            ArtifactInvalidation(
                "artifact:gateway-code",
                dependent_evidence_ids=("artifact:old-runtime-gateway-proof",),
                revalidation_evidence_ids=("artifact:new-runtime-gateway-proof",),
            ),
        ),
        model_quality_signals=(
            ModelQualitySignal(
                "quality:hidden-state-reviewed",
                MODEL_QUALITY_HIDDEN_STATE,
                model_id="model:critical-write",
                resolved=True,
                resolution_evidence_ids=("artifact:model-quality-review",),
            ),
        ),
        same_class_miss_closures=(
            SameClassMissClosure(
                "miss:critical-write",
                observed_failure_evidence_id="artifact:observed-runtime-failure",
                same_class_proof_evidence_id="artifact:same-class-regression",
                model_obligation_id="model:critical-write",
            ),
        ),
        runtime_gateway_closures=(
            RuntimeGatewayInventoryClosure(
                "gateway:critical-state",
                inventory_source_evidence_ids=("inventory:static-writers", "inventory:runtime-replay"),
                gateway_report_evidence_id="report:runtime-gateway",
            ),
        ),
        evidence_reports=(
            evidence_report("report:runtime-gateway", CLOSURE_REPORT_RUNTIME_GATEWAY),
            evidence_report("report:risk-ledger", CLOSURE_REPORT_RISK_LEDGER),
        ),
    )


def broken_closure_plan():
    return FlowGuardClosureContractPlan(
        claim_id="release:broken-point-evidence",
        runtime_trace_mappings=(RuntimeTraceMapping("trace:unmapped"),),
        artifact_invalidations=(
            ArtifactInvalidation(
                "artifact:changed-gateway",
                dependent_evidence_ids=("artifact:old-proof",),
                revalidation_evidence_ids=(),
            ),
        ),
        model_quality_signals=(
            ModelQualitySignal(
                "quality:hidden-state-open",
                MODEL_QUALITY_HIDDEN_STATE,
                model_id="model:critical-write",
            ),
        ),
        same_class_miss_closures=(
            SameClassMissClosure(
                "miss:no-same-class-proof",
                observed_failure_evidence_id="artifact:observed-failure",
            ),
        ),
        runtime_gateway_closures=(
            RuntimeGatewayInventoryClosure(
                "gateway:critical-state",
                gateway_report_evidence_id="report:runtime-gateway",
            ),
        ),
        evidence_reports=(
            evidence_report("report:runtime-gateway", CLOSURE_REPORT_RUNTIME_GATEWAY),
            evidence_report("report:risk-ledger", CLOSURE_REPORT_RISK_LEDGER),
        ),
    )


def run_checks():
    return (
        review_flowguard_closure_contract(correct_closure_plan()),
        review_flowguard_closure_contract(broken_closure_plan()),
    )
'''


FLOWGUARD_CLOSURE_CONTRACT_RUN_CHECKS_TEMPLATE = '''"""Run the FlowGuard Closure Contract template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    correct, broken = run_checks()
    print(correct.format_text())
    print()
    print(broken.format_text(max_findings=8))
    return 0 if correct.ok and not broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


FLOWGUARD_CLOSURE_CONTRACT_NOTES_TEMPLATE = """# FlowGuard Closure Contract Notes

Use this scaffold before a broad done, release, publish, or
production-confidence claim.

## What The Closure Review Consumes

- Runtime traces mapped back to named model obligations.
- Changed artifacts with dependent evidence and fresh revalidation evidence.
- Model-quality signals such as hidden state, missing side effects, owner
  ambiguity, helper-only proof, missing public boundary, and parent/child
  evidence gaps.
- Same-class model-miss closure evidence with both the observed failure and
  same-class proof.
- Runtime gateway inventory closure for critical state writers.
- Risk Evidence Ledger and route reports with current passing full-confidence
  evidence.

The closure review is a final coordinator. It does not replace the route that
owns each proof; it blocks or scopes the final claim when any required evidence
is stale, skipped, progress-only, missing, internally scoped, or unresolved.
"""


def project_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile("model.py", MODEL_TEMPLATE),
        TemplateFile("run_checks.py", RUN_CHECKS_TEMPLATE),
    )


def adoption_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile("docs/flowguard_adoption_log.md", ADOPTION_LOG_TEMPLATE),
        TemplateFile("docs/flowguard_model_notes.md", MODEL_NOTES_TEMPLATE),
    )


def project_adoption_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile("AGENTS.md", build_flowguard_agents_block() + "\n"),
        TemplateFile(".flowguard/project.toml", current_project_manifest_text()),
        TemplateFile("docs/flowguard_adoption_log.md", ADOPTION_LOG_TEMPLATE),
        TemplateFile("docs/flowguard_model_notes.md", MODEL_NOTES_TEMPLATE),
    )


def risk_intent_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/risk_intent_check_plan/model.py", RISK_INTENT_CHECK_PLAN_MODEL_TEMPLATE),
        TemplateFile(".flowguard/risk_intent_check_plan/run_checks.py", RISK_INTENT_CHECK_PLAN_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_risk_intent_check_plan.md", RISK_INTENT_CHECK_PLAN_NOTES_TEMPLATE),
    )


def model_miss_review_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/model_miss_review/model.py", MODEL_MISS_REVIEW_MODEL_TEMPLATE),
        TemplateFile(".flowguard/model_miss_review/run_checks.py", MODEL_MISS_REVIEW_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_model_miss_review.md", MODEL_MISS_REVIEW_NOTES_TEMPLATE),
    )


def maintenance_workflow_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/maintenance_workflow/model.py", MAINTENANCE_WORKFLOW_MODEL_TEMPLATE),
        TemplateFile(".flowguard/maintenance_workflow/run_checks.py", MAINTENANCE_WORKFLOW_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_maintenance_workflow.md", MAINTENANCE_WORKFLOW_NOTES_TEMPLATE),
    )


RUNTIME_PATH_EVIDENCE_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Models runtime path evidence for real code nodes that should line up with a
FlowGuard model.

Guards against:
- progress logs that do not name the FlowGuard model being compared;
- broad confidence claims without leaf runtime node observations;
- stale, non-passing, internal-only, or out-of-order runtime path evidence;
- runtime gateway or parent-model claims that cannot point to child path ids.

Use before editing:
real-code instrumentation, test adapters, model-test alignment rows, leaf
boundary matrices, parent/child reattachment, runtime gateway bindings, or
closure evidence.

Run:
python .flowguard/runtime_path_evidence/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    RuntimeNodeContract,
    RuntimeNodeObservation,
    RuntimePathAlignmentPlan,
    RuntimePathRecorder,
    review_runtime_path_alignment,
)


MODEL_ID = "checkout.leaf"
MODEL_PATH = ".flowguard/checkout_leaf/model.py"
OBLIGATION_ID = "accept_valid_order"
CODE_CONTRACT_ID = "checkout.submit"


def node_contracts():
    return (
        RuntimeNodeContract(
            "validate_order",
            model_id=MODEL_ID,
            model_path=MODEL_PATH,
            leaf_model_id=MODEL_ID,
            model_obligation_id=OBLIGATION_ID,
            code_contract_id=CODE_CONTRACT_ID,
            boundary_id="checkout.submit.boundary",
            allowed_outputs=("accepted",),
            allowed_state_writes=("order_status",),
            sequence_index=0,
        ),
    )


def good_plan():
    recorder = RuntimePathRecorder("run:checkout:happy-path")
    recorder.record(
        "validate_order",
        model_id=MODEL_ID,
        model_path=MODEL_PATH,
        leaf_model_id=MODEL_ID,
        model_obligation_id=OBLIGATION_ID,
        code_contract_id=CODE_CONTRACT_ID,
        boundary_id="checkout.submit.boundary",
        observed_output="accepted",
        observed_state_writes=("order_status",),
        evidence_id="runtime-path:validate-order:v1",
        progress_message="accepted valid order at model-owned boundary",
    )
    return RuntimePathAlignmentPlan(
        "checkout-runtime-path",
        model_id=MODEL_ID,
        node_contracts=node_contracts(),
        runs=(recorder.to_run(),),
        require_exact_path=True,
    )


def broken_plan():
    return RuntimePathAlignmentPlan(
        "checkout-runtime-path-broken",
        model_id=MODEL_ID,
        node_contracts=node_contracts(),
        observations=(
            RuntimeNodeObservation(
                "obs:internal-helper",
                "internal_helper_only",
                run_id="run:checkout:broken",
                model_id=MODEL_ID,
                model_path=MODEL_PATH,
                assertion_scope="internal_path",
                result_status="skipped",
                progress_message="helper log did not prove the model node",
            ),
        ),
        require_exact_path=True,
    )


def review():
    return review_runtime_path_alignment(good_plan()), review_runtime_path_alignment(broken_plan())
'''


RUNTIME_PATH_EVIDENCE_RUN_CHECKS_TEMPLATE = '''"""Run the Runtime Path Evidence template checks."""

from __future__ import annotations

from model import good_plan, review


def main() -> int:
    good_report, broken_report = review()
    print("=== flowguard runtime path evidence ===")
    print(good_report.format_text())
    print()
    print("runtime progress:")
    print(good_plan().runs[0].format_progress_lines())
    print()
    print("broken evidence:")
    print(broken_report.format_text(max_findings=5))
    ok = good_report.ok and not broken_report.ok
    print(f"status: {'OK' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


RUNTIME_PATH_EVIDENCE_NOTES_TEMPLATE = """# FlowGuard Runtime Path Evidence

Runtime path evidence connects real code progress output back to a FlowGuard
model. Each emitted node should name the compared `model_id`, `model_path`,
`node_id`, run id, status, and the relevant obligation or code contract when
known.

Use it at leaf model boundaries, state writes, side effects, parent/child
handoffs, runtime gateway writes, and final confidence claims. Do not treat
anonymous progress logs as FlowGuard evidence.
"""


def runtime_path_evidence_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/runtime_path_evidence/model.py", RUNTIME_PATH_EVIDENCE_MODEL_TEMPLATE),
        TemplateFile(".flowguard/runtime_path_evidence/run_checks.py", RUNTIME_PATH_EVIDENCE_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/runtime_path_evidence.md", RUNTIME_PATH_EVIDENCE_NOTES_TEMPLATE),
    )


def model_test_alignment_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/model_test_alignment/model.py", MODEL_TEST_ALIGNMENT_MODEL_TEMPLATE),
        TemplateFile(".flowguard/model_test_alignment/run_checks.py", MODEL_TEST_ALIGNMENT_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/model_test_alignment.md", MODEL_TEST_ALIGNMENT_NOTES_TEMPLATE),
    )


def development_process_flow_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/development_process_flow/model.py", DEVELOPMENT_PROCESS_FLOW_MODEL_TEMPLATE),
        TemplateFile(".flowguard/development_process_flow/run_checks.py", DEVELOPMENT_PROCESS_FLOW_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_development_process_flow.md", DEVELOPMENT_PROCESS_FLOW_NOTES_TEMPLATE),
    )


def workflow_step_contracts_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/workflow_step_contracts/model.py", WORKFLOW_STEP_CONTRACTS_MODEL_TEMPLATE),
        TemplateFile(
            ".flowguard/workflow_step_contracts/run_checks.py",
            WORKFLOW_STEP_CONTRACTS_RUN_CHECKS_TEMPLATE,
        ),
        TemplateFile("docs/flowguard_workflow_step_contracts.md", WORKFLOW_STEP_CONTRACTS_NOTES_TEMPLATE),
    )


def code_structure_recommendation_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(
            ".flowguard/code_structure_recommendation/model.py",
            CODE_STRUCTURE_RECOMMENDATION_MODEL_TEMPLATE,
        ),
        TemplateFile(
            ".flowguard/code_structure_recommendation/run_checks.py",
            CODE_STRUCTURE_RECOMMENDATION_RUN_CHECKS_TEMPLATE,
        ),
        TemplateFile(
            "docs/flowguard_code_structure_recommendation.md",
            CODE_STRUCTURE_RECOMMENDATION_NOTES_TEMPLATE,
        ),
    )


def existing_model_preflight_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/existing_model_preflight/model.py", EXISTING_MODEL_PREFLIGHT_MODEL_TEMPLATE),
        TemplateFile(".flowguard/existing_model_preflight/run_checks.py", EXISTING_MODEL_PREFLIGHT_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_existing_model_preflight.md", EXISTING_MODEL_PREFLIGHT_NOTES_TEMPLATE),
    )


def model_similarity_consolidation_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(
            ".flowguard/model_similarity_consolidation/model.py",
            MODEL_SIMILARITY_CONSOLIDATION_MODEL_TEMPLATE,
        ),
        TemplateFile(
            ".flowguard/model_similarity_consolidation/run_checks.py",
            MODEL_SIMILARITY_CONSOLIDATION_RUN_CHECKS_TEMPLATE,
        ),
        TemplateFile(
            "docs/flowguard_model_similarity_consolidation.md",
            MODEL_SIMILARITY_CONSOLIDATION_NOTES_TEMPLATE,
        ),
    )


def risk_evidence_ledger_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/risk_evidence_ledger/model.py", RISK_EVIDENCE_LEDGER_MODEL_TEMPLATE),
        TemplateFile(".flowguard/risk_evidence_ledger/run_checks.py", RISK_EVIDENCE_LEDGER_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_risk_evidence_ledger.md", RISK_EVIDENCE_LEDGER_NOTES_TEMPLATE),
    )


def layered_boundary_proof_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/layered_boundary_proof/model.py", LAYERED_BOUNDARY_PROOF_MODEL_TEMPLATE),
        TemplateFile(".flowguard/layered_boundary_proof/run_checks.py", LAYERED_BOUNDARY_PROOF_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_layered_boundary_proof.md", LAYERED_BOUNDARY_PROOF_NOTES_TEMPLATE),
    )


def closure_contract_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/closure_contract/model.py", FLOWGUARD_CLOSURE_CONTRACT_MODEL_TEMPLATE),
        TemplateFile(".flowguard/closure_contract/run_checks.py", FLOWGUARD_CLOSURE_CONTRACT_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_closure_contract_review.md", FLOWGUARD_CLOSURE_CONTRACT_NOTES_TEMPLATE),
    )


def ui_flow_structure_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/ui_flow_structure/model.py", UI_FLOW_STRUCTURE_MODEL_TEMPLATE),
        TemplateFile(".flowguard/ui_flow_structure/run_checks.py", UI_FLOW_STRUCTURE_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_ui_flow_structure.md", UI_FLOW_STRUCTURE_NOTES_TEMPLATE),
    )


def test_mesh_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/test_mesh/model.py", TEST_MESH_MODEL_TEMPLATE),
        TemplateFile(".flowguard/test_mesh/run_checks.py", TEST_MESH_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_test_mesh.md", TEST_MESH_NOTES_TEMPLATE),
    )


def structure_mesh_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/structure_mesh/model.py", STRUCTURE_MESH_MODEL_TEMPLATE),
        TemplateFile(".flowguard/structure_mesh/run_checks.py", STRUCTURE_MESH_RUN_CHECKS_TEMPLATE),
        TemplateFile("docs/flowguard_structure_mesh.md", STRUCTURE_MESH_NOTES_TEMPLATE),
    )


def write_template_files(
    root: str | Path,
    files: tuple[TemplateFile, ...],
    *,
    overwrite: bool = False,
) -> tuple[Path, ...]:
    target_root = Path(root)
    written: list[Path] = []
    for file in files:
        target = target_root / file.path
        if target.exists() and not overwrite:
            raise FileExistsError(f"template target already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file.content, encoding="utf-8")
        written.append(target)
    return tuple(written)


__all__ = [
    "ADOPTION_LOG_TEMPLATE",
    "CODE_STRUCTURE_RECOMMENDATION_MODEL_TEMPLATE",
    "CODE_STRUCTURE_RECOMMENDATION_NOTES_TEMPLATE",
    "CODE_STRUCTURE_RECOMMENDATION_RUN_CHECKS_TEMPLATE",
    "DEVELOPMENT_PROCESS_FLOW_MODEL_TEMPLATE",
    "DEVELOPMENT_PROCESS_FLOW_NOTES_TEMPLATE",
    "DEVELOPMENT_PROCESS_FLOW_RUN_CHECKS_TEMPLATE",
    "EXISTING_MODEL_PREFLIGHT_MODEL_TEMPLATE",
    "EXISTING_MODEL_PREFLIGHT_NOTES_TEMPLATE",
    "EXISTING_MODEL_PREFLIGHT_RUN_CHECKS_TEMPLATE",
    "FLOWGUARD_CLOSURE_CONTRACT_MODEL_TEMPLATE",
    "FLOWGUARD_CLOSURE_CONTRACT_NOTES_TEMPLATE",
    "FLOWGUARD_CLOSURE_CONTRACT_RUN_CHECKS_TEMPLATE",
    "LAYERED_BOUNDARY_PROOF_MODEL_TEMPLATE",
    "LAYERED_BOUNDARY_PROOF_NOTES_TEMPLATE",
    "LAYERED_BOUNDARY_PROOF_RUN_CHECKS_TEMPLATE",
    "MAINTENANCE_WORKFLOW_MODEL_TEMPLATE",
    "MAINTENANCE_WORKFLOW_NOTES_TEMPLATE",
    "MAINTENANCE_WORKFLOW_RUN_CHECKS_TEMPLATE",
    "MODEL_MISS_REVIEW_MODEL_TEMPLATE",
    "MODEL_MISS_REVIEW_NOTES_TEMPLATE",
    "MODEL_MISS_REVIEW_RUN_CHECKS_TEMPLATE",
    "MODEL_TEST_ALIGNMENT_MODEL_TEMPLATE",
    "MODEL_TEST_ALIGNMENT_NOTES_TEMPLATE",
    "MODEL_TEST_ALIGNMENT_RUN_CHECKS_TEMPLATE",
    "MODEL_NOTES_TEMPLATE",
    "RISK_INTENT_CHECK_PLAN_MODEL_TEMPLATE",
    "RISK_INTENT_CHECK_PLAN_NOTES_TEMPLATE",
    "RISK_INTENT_CHECK_PLAN_RUN_CHECKS_TEMPLATE",
    "RISK_EVIDENCE_LEDGER_MODEL_TEMPLATE",
    "RISK_EVIDENCE_LEDGER_NOTES_TEMPLATE",
    "RISK_EVIDENCE_LEDGER_RUN_CHECKS_TEMPLATE",
    "RUNTIME_PATH_EVIDENCE_MODEL_TEMPLATE",
    "RUNTIME_PATH_EVIDENCE_NOTES_TEMPLATE",
    "RUNTIME_PATH_EVIDENCE_RUN_CHECKS_TEMPLATE",
    "STRUCTURE_MESH_MODEL_TEMPLATE",
    "STRUCTURE_MESH_NOTES_TEMPLATE",
    "STRUCTURE_MESH_RUN_CHECKS_TEMPLATE",
    "TEST_MESH_MODEL_TEMPLATE",
    "TEST_MESH_NOTES_TEMPLATE",
    "TEST_MESH_RUN_CHECKS_TEMPLATE",
    "TemplateFile",
    "WORKFLOW_STEP_CONTRACTS_MODEL_TEMPLATE",
    "WORKFLOW_STEP_CONTRACTS_NOTES_TEMPLATE",
    "WORKFLOW_STEP_CONTRACTS_RUN_CHECKS_TEMPLATE",
    "adoption_template_files",
    "closure_contract_template_files",
    "code_structure_recommendation_template_files",
    "development_process_flow_template_files",
    "existing_model_preflight_template_files",
    "layered_boundary_proof_template_files",
    "maintenance_workflow_template_files",
    "model_miss_review_template_files",
    "model_similarity_consolidation_template_files",
    "model_test_alignment_template_files",
    "project_template_files",
    "project_adoption_template_files",
    "risk_evidence_ledger_template_files",
    "risk_intent_template_files",
    "runtime_path_evidence_template_files",
    "structure_mesh_template_files",
    "test_mesh_template_files",
    "ui_flow_structure_template_files",
    "workflow_step_contracts_template_files",
    "write_template_files",
]

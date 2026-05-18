"""Reusable project template content for model-first flowguard adoption."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
- validating a fix before representing the issue in the model;
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
    fix_validated_after_refinement: bool = False
    completed: bool = False


@dataclass(frozen=True)
class Event:
    name: str


FLOWGUARD_PASS = Event("flowguard_pass")
RUNTIME_FAIL = Event("runtime_fail")
CLASSIFY_MISS = Event("classify_miss")
REPRESENT_ISSUE = Event("represent_issue")
VALIDATE_FIX = Event("validate_fix")
FINALIZE = Event("finalize")


class ApplyReviewStep:
    name = "ApplyReviewStep"
    reads = (
        "flowguard_passed",
        "runtime_issue_observed",
        "model_miss_classified",
        "issue_represented_in_model",
        "fix_validated_after_refinement",
    )
    writes = (
        "flowguard_passed",
        "runtime_issue_observed",
        "model_miss_classified",
        "issue_represented_in_model",
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
        if input_obj.name == "validate_fix":
            if not state.issue_represented_in_model:
                yield FunctionResult("fix_validation_blocked", state, label="blocked")
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


def invariants() -> tuple[Invariant, ...]:
    def completion_requires_review(state: State, _trace) -> InvariantResult:
        if state.completed and state.runtime_issue_observed:
            if not (
                state.model_miss_classified
                and state.issue_represented_in_model
                and state.fix_validated_after_refinement
            ):
                return InvariantResult.fail(
                    "completed runtime issue without classification, model representation, and refined validation"
                )
        return InvariantResult.pass_()

    def fix_validation_requires_model_representation(state: State, _trace) -> InvariantResult:
        if state.fix_validated_after_refinement and not state.issue_represented_in_model:
            return InvariantResult.fail("fix validated before the issue was represented in the model")
        return InvariantResult.pass_()

    return (
        Invariant("completion_requires_review", "Runtime issues must be reviewed before completion.", completion_requires_review),
        Invariant(
            "fix_validation_requires_model_representation",
            "Fix validation requires executable model representation or an explicit boundary.",
            fix_validation_requires_model_representation,
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
            "Runtime issue is classified, represented, validated, then finalized.",
            (FLOWGUARD_PASS, RUNTIME_FAIL, CLASSIFY_MISS, REPRESENT_ISSUE, VALIDATE_FIX, FINALIZE),
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
- Which refined model checks and runtime checks must pass before completion?
- If the repair changed a child model under a parent ModelMesh, which parent
  reattachment gate consumed the new child evidence id?

Do not let a later green runtime check close a known model miss by itself.
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
- stale, skipped, failed, timeout, not-run, or overclaiming test evidence.

Use before editing:
test coverage claims, model confidence reports, model-backed feature work, or
release notes that claim model and test coverage agree.

Run:
python .flowguard/model_test_alignment/run_checks.py

This template does not use TestMesh, StructureMesh, or ModelMesh. It compares
plain model obligations, optional code external contracts, and plain test
evidence.
"""

from __future__ import annotations

from flowguard import (
    CodeContract,
    ModelObligation,
    ModelTestAlignmentPlan,
    TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
    TEST_ASSERTION_SCOPE_INTERNAL_PATH,
    TEST_KIND_FAILURE_PATH,
    TEST_KIND_HAPPY_PATH,
    TestEvidence,
    audit_python_code_contracts,
    audit_python_test_assertions,
    review_python_contract_source_audit,
    review_model_test_alignment,
)


def aligned_plan() -> ModelTestAlignmentPlan:
    return ModelTestAlignmentPlan(
        model_id="sample_checkout_model",
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
    return (
        review_model_test_alignment(aligned),
        review_model_test_alignment(broken),
        source_audit(aligned, ALIGNED_SOURCE),
        source_audit(broken, BROKEN_SOURCE),
    )
'''


MODEL_TEST_ALIGNMENT_RUN_CHECKS_TEMPLATE = '''"""Run the Model-Test Alignment template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    aligned, broken, aligned_source, broken_source = run_checks()
    print(aligned.format_text())
    print()
    print(broken.format_text(max_findings=5))
    print()
    print(aligned_source.format_text())
    print()
    print(broken_source.format_text(max_findings=5))
    return 0 if aligned.ok and not broken.ok and aligned_source.ok and not broken_source.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


MODEL_TEST_ALIGNMENT_NOTES_TEMPLATE = """# FlowGuard Model-Test Alignment Notes

Use this scaffold to compare a FlowGuard model's explicit obligations with
optional code external contracts, ordinary test evidence, and conservative
Python source audits for those contracts.

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
Purpose: Review a development lifecycle as a sibling process route, tracking artifact versions and validation evidence freshness before done or release claims.
Guards against: stale validation after code/test/model/requirement changes, progress-only evidence, hidden skips, missing V-style validation pairs, peer writes, and release overclaims.
Use before editing: Update this development process flow when changing development ordering, validation gates, release readiness, or evidence freshness policy.
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
    ProcessAction,
    ProcessArtifact,
    ProcessEvidence,
    ValidationRequirement,
    review_development_process_flow,
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
- whether done, release, archive, or publish claims have current evidence;
- the minimum revalidation needed when evidence is stale or missing.

## Sibling Route Boundary

This is a sibling sub-protocol. It can reference evidence produced by ModelMesh,
TestMesh, StructureMesh, Model-Test Alignment, LongCheck, or Conformance
Adoption through evidence ids and freshness metadata. It does not inspect,
supervise, replace, or repair those routes. If sibling evidence is failed,
stale, skipped, missing, or progress-only, this route keeps that lifecycle gap
visible for the current process claim.

Use this route when development ordering, artifact overwrite, verification
freshness, or release readiness is the risk. It is not mandatory for every
small edit and it does not make FlowGuard a task orchestrator.
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
    UIInteractionModel,
    UIRegionRecommendation,
    UIStateNode,
    UIStructureDerivation,
    UITextElement,
    UITextHierarchyBlueprint,
    UITypographyToken,
    UITransition,
    review_ui_interaction_model,
    review_ui_structure_derivation,
    review_ui_text_hierarchy,
)


def interaction_model() -> UIInteractionModel:
    return UIInteractionModel(
        "import-run-ui-flow",
        initial_state_id="empty",
        source_product_model_id="import-run-product-flow",
        states=(
            UIStateNode(
                "empty",
                visible_controls=("import", "settings", "run", "export"),
                enabled_controls=("import", "settings"),
                disabled_controls=("run", "export"),
                rationale="The first screen lets the user import data or adjust global settings.",
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
                visible_controls=("run", "export", "settings"),
                enabled_controls=("run", "export", "settings"),
                visible_displays=("summary_card", "result_table"),
                terminal=True,
                rationale="The result state enables export and rerun actions.",
            ),
            UIStateNode(
                "failed",
                visible_controls=("retry", "settings"),
                enabled_controls=("retry", "settings"),
                recovery_controls=("retry",),
                failure=True,
                rationale="A recoverable failure offers retry and global settings.",
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
            UIControl("import", label="Import", level="primary", rationale="Import starts the main workflow."),
            UIControl(
                "run",
                label="Run",
                level="primary",
                depends_on_states=("loaded", "result_ready"),
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
            UITransition("click_import", "import", "empty", "loaded", function_block="ImportFile", output="file_loaded", rationale="Import creates the loaded state."),
            UITransition("click_run", "run", "loaded", "running", function_block="StartRun", output="run_started", rationale="Run starts the primary processing state."),
            UITransition("click_cancel", "cancel", "running", "loaded", function_block="CancelRun", output="run_cancelled", rationale="Cancel returns to the loaded state."),
            UITransition("run_success", "run", "running", "result_ready", function_block="FinishRun", output="result_ready", rationale="A successful run exposes results."),
            UITransition("run_failure", "run", "running", "failed", function_block="FailRun", output="recoverable_error", rationale="A failed run enters a recoverable failure state."),
            UITransition("click_retry", "retry", "failed", "running", function_block="RetryRun", output="retry_started", rationale="Retry returns to the running state."),
            UITransition("click_export", "export", "result_ready", "result_ready", function_block="ExportResult", output="exported", rationale="Export is terminal-state output, not a new workflow phase."),
        ),
        validation_boundaries=("UI scenario review", "browser state transition test"),
        rationale="The model separates initial, loaded, running, result, and failure UI states before any layout is derived.",
    )


def structure_derivation() -> UIStructureDerivation:
    return UIStructureDerivation(
        "import-run-ui-structure",
        source_interaction_model_id="import-run-ui-flow",
        parent_surface_id="import-run-workbench",
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
                owns_states=("empty", "loaded", "running", "result_ready"),
                owns_controls=("import", "run", "export"),
                owns_displays=("summary_card", "result_table"),
                owns_events=("click_import", "click_run", "run_success", "click_export"),
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
                owns_events=("click_cancel",),
                rationale="Cancel temporarily scopes the running parent flow.",
            ),
        ),
        state_region_map=(
            ("empty", "primary-workspace"),
            ("loaded", "primary-workspace"),
            ("running", "primary-workspace"),
            ("result_ready", "primary-workspace"),
            ("failed", "failure-inspector"),
        ),
        control_region_map=(
            ("settings", "top-toolbar"),
            ("import", "primary-workspace"),
            ("run", "primary-workspace"),
            ("export", "primary-workspace"),
            ("retry", "failure-inspector"),
            ("cancel", "cancel-overlay"),
        ),
        display_region_map=(
            ("summary_card", "primary-workspace"),
            ("result_table", "primary-workspace"),
        ),
        event_region_map=(
            ("click_import", "primary-workspace"),
            ("click_run", "primary-workspace"),
            ("run_success", "primary-workspace"),
            ("run_failure", "failure-inspector"),
            ("click_retry", "failure-inspector"),
            ("click_cancel", "cancel-overlay"),
            ("click_export", "primary-workspace"),
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
        "import-run-text-hierarchy",
        source_interaction_model_id="import-run-ui-flow",
        source_structure_derivation_id="import-run-ui-structure",
        parent_surface_id="import-run-workbench",
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
                label="Import Run",
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
            UITextElement("import_label", "button_label", "control-label", "import_action", label="Import", region_id="primary-workspace", source_control_id="import", rationale="Import is an action label, not a heading."),
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
        source_interaction_model_id="import-run-ui-flow",
        parent_surface_id="import-run-workbench",
        target_regions=(UIRegionRecommendation("main"),),
        state_region_map=(("empty", "main"),),
        control_region_map=(("settings", "main"),),
        display_region_map=(("chart", "main"), ("text", "main")),
    )


def broken_text_hierarchy() -> UITextHierarchyBlueprint:
    return UITextHierarchyBlueprint(
        "broken-text-hierarchy",
        source_interaction_model_id="import-run-ui-flow",
        source_structure_derivation_id="import-run-ui-structure",
        parent_surface_id="import-run-workbench",
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
                "import_action",
                label="Import",
                region_id="primary-workspace",
                source_control_id="import",
                rationale="Broken because a button label uses a top-level token.",
            ),
        ),
        validation_boundaries=("text hierarchy review",),
        rationale="This intentionally broken blueprint demonstrates duplicate text and over-prominent action labels.",
    )


def run_checks():
    model_report = review_ui_interaction_model(interaction_model())
    structure_report = review_ui_structure_derivation(structure_derivation(), interaction_model=interaction_model())
    text_report = review_ui_text_hierarchy(
        text_hierarchy(),
        interaction_model=interaction_model(),
        structure_derivation=structure_derivation(),
    )
    broken_model_report = review_ui_interaction_model(broken_interaction_model())
    broken_structure_report = review_ui_structure_derivation(
        broken_structure_derivation(),
        interaction_model=interaction_model(),
    )
    broken_text_report = review_ui_text_hierarchy(
        broken_text_hierarchy(),
        interaction_model=interaction_model(),
        structure_derivation=structure_derivation(),
    )
    return model_report, structure_report, text_report, broken_model_report, broken_structure_report, broken_text_report
'''


UI_FLOW_STRUCTURE_RUN_CHECKS_TEMPLATE = '''"""Run the UI Flow Structure template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    model_report, structure_report, text_report, broken_model, broken_structure, broken_text = run_checks()
    print(model_report.format_text())
    print()
    print(structure_report.format_text())
    print()
    print(text_report.format_text())
    print()
    print(broken_model.format_text(max_findings=5))
    print()
    print(broken_structure.format_text(max_findings=5))
    print()
    print(broken_text.format_text(max_findings=5))
    return 0 if model_report.ok and structure_report.ok and text_report.ok and not broken_model.ok and not broken_structure.ok and not broken_text.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


UI_FLOW_STRUCTURE_NOTES_TEMPLATE = """# FlowGuard UI Flow Structure Notes

Use this scaffold before visual design or frontend implementation when the UI
itself needs a model-first interaction flow.

## What This Route Produces

- a UI interaction model: initial state, controls, events, state nodes,
  transitions, failure and recovery states, terminal states, and availability;
- a structure derivation from that model: parent/child UI nodes, first-level
  persistent menus, second-level contextual regions, third-level local actions,
  overlays, stable layout positions, and validation boundaries;
- a text hierarchy blueprint from that reviewed structure: page titles,
  section titles, panel titles, labels, button text, status text, captions,
  semantic text keys, typography tokens, parent/child text priority, and
  redundancy rationale;
- review findings when a control has no modeled event, a failure state has no
  recovery path, a destructive control is too prominent, or a persistent
  control is not assigned to a stable global region;
- redundancy findings when the same page/state shows the same semantic
  information twice or exposes multiple same-level controls for one function
  without an explicit rationale;
- text hierarchy findings when a button label uses a heading token, a child
  title is not visually subordinate to its parent title, or the same semantic
  text is repeated in one region and state without a modeled reason.

UI Flow Structure does not choose final brand styling or implement frontend
code. Use the derived structure and text hierarchy contract as input to Figma,
frontend implementation, browser checks, and design implementation review.
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
    "STRUCTURE_MESH_MODEL_TEMPLATE",
    "STRUCTURE_MESH_NOTES_TEMPLATE",
    "STRUCTURE_MESH_RUN_CHECKS_TEMPLATE",
    "TEST_MESH_MODEL_TEMPLATE",
    "TEST_MESH_NOTES_TEMPLATE",
    "TEST_MESH_RUN_CHECKS_TEMPLATE",
    "TemplateFile",
    "adoption_template_files",
    "code_structure_recommendation_template_files",
    "development_process_flow_template_files",
    "maintenance_workflow_template_files",
    "model_miss_review_template_files",
    "model_test_alignment_template_files",
    "project_template_files",
    "risk_intent_template_files",
    "structure_mesh_template_files",
    "test_mesh_template_files",
    "ui_flow_structure_template_files",
    "write_template_files",
]

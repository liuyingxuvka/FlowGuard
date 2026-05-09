"""Reusable project template content for model-first flowguard adoption."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TemplateFile:
    path: str
    content: str


MODEL_TEMPLATE = '''"""Minimal flowguard model template.

Copy this file before production edits and replace the sample domain with the
behavior under review.
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


MAINTENANCE_WORKFLOW_MODEL_TEMPLATE = '''"""Maintenance workflow template for recurring multi-role agent systems.

This template is useful for Sleep/Dream/Architect/Installer/Reviewer style
flows. Rename the roles and state fields to match the project under review.
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


RISK_INTENT_CHECK_PLAN_MODEL_TEMPLATE = '''"""Risk Intent + CheckPlan template.

Use this scaffold when the risk should be named before the function-flow model
is written. Replace the sample item workflow with the current behavior under
review.
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


MODEL_MISS_REVIEW_MODEL_TEMPLATE = '''"""Post-runtime model-miss review template.

Use this scaffold when a FlowGuard pass is followed by a test, runtime, replay,
or manual-validation failure. Replace the event names and obligations with the
bug class under review.
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

Do not let a later green runtime check close a known model miss by itself.
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
    "MAINTENANCE_WORKFLOW_MODEL_TEMPLATE",
    "MAINTENANCE_WORKFLOW_NOTES_TEMPLATE",
    "MAINTENANCE_WORKFLOW_RUN_CHECKS_TEMPLATE",
    "MODEL_MISS_REVIEW_MODEL_TEMPLATE",
    "MODEL_MISS_REVIEW_NOTES_TEMPLATE",
    "MODEL_MISS_REVIEW_RUN_CHECKS_TEMPLATE",
    "MODEL_NOTES_TEMPLATE",
    "RISK_INTENT_CHECK_PLAN_MODEL_TEMPLATE",
    "RISK_INTENT_CHECK_PLAN_NOTES_TEMPLATE",
    "RISK_INTENT_CHECK_PLAN_RUN_CHECKS_TEMPLATE",
    "TemplateFile",
    "adoption_template_files",
    "maintenance_workflow_template_files",
    "model_miss_review_template_files",
    "project_template_files",
    "risk_intent_template_files",
    "write_template_files",
]

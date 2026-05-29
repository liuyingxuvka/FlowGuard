"""Template text for FlowGuard maintenance workflow route."""

from __future__ import annotations

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

__all__ = [
    'MAINTENANCE_WORKFLOW_MODEL_TEMPLATE',
    'MAINTENANCE_WORKFLOW_RUN_CHECKS_TEMPLATE',
    'MAINTENANCE_WORKFLOW_NOTES_TEMPLATE',
]

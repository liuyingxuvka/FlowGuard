"""Local FlowGuard model for user-facing model visibility guidance.

This model is a release preflight artifact, not a public API. It checks that
the prompt rollout defaults to a visible Mermaid snapshot for non-trivial
FlowGuard work while preserving a concise path for trivial tasks. It also
checks that non-trivial snapshots are introduced with a short current-situation
note so users can see what FlowGuard is doing now.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class PromptTask:
    task_id: str
    route: str
    non_trivial: bool
    user_suppressed_diagram: bool = False
    material_change: bool = False


@dataclass(frozen=True)
class VisibilityDecision:
    task_id: str
    mode: str
    route: str


@dataclass(frozen=True)
class WorkEvidence:
    task_id: str
    current_situation_shown: bool
    current_situation_updated: bool
    diagram_shown: bool
    diagram_updated: bool
    validation_run: bool
    validation_claimed: bool
    reason: str


@dataclass(frozen=True)
class State:
    tasks: tuple[PromptTask, ...] = ()
    decisions: tuple[VisibilityDecision, ...] = ()
    evidence: tuple[WorkEvidence, ...] = ()

    def task_for(self, task_id: str) -> PromptTask | None:
        return next((task for task in self.tasks if task.task_id == task_id), None)

    def decision_for(self, task_id: str) -> VisibilityDecision | None:
        return next((decision for decision in self.decisions if decision.task_id == task_id), None)

    def with_task(self, task: PromptTask) -> "State":
        return replace(self, tasks=tuple(item for item in self.tasks if item.task_id != task.task_id) + (task,))

    def with_decision(self, decision: VisibilityDecision) -> "State":
        return replace(
            self,
            decisions=tuple(item for item in self.decisions if item.task_id != decision.task_id) + (decision,),
        )

    def with_evidence(self, evidence: WorkEvidence) -> "State":
        return replace(
            self,
            evidence=tuple(item for item in self.evidence if item.task_id != evidence.task_id) + (evidence,),
        )


class DecideVisibility:
    name = "DecideVisibility"
    reads = ("tasks",)
    writes = ("tasks", "decisions")
    accepted_input_type = PromptTask
    input_description = "FlowGuard-routed task"
    output_description = "VisibilityDecision"
    idempotency = "same task has one visibility decision"

    def apply(self, input_obj: PromptTask, state: State) -> Iterable[FunctionResult]:
        state = state.with_task(input_obj)
        if input_obj.user_suppressed_diagram or not input_obj.non_trivial:
            decision = VisibilityDecision(input_obj.task_id, "concise_ok", input_obj.route)
            yield FunctionResult(
                decision,
                state.with_decision(decision),
                label="diagram_not_required_for_small_or_suppressed",
                reason="tiny or user-suppressed work may remain concise",
            )
            return
        decision = VisibilityDecision(input_obj.task_id, "default_visible_snapshot", input_obj.route)
        yield FunctionResult(
            decision,
            state.with_decision(decision),
            label="non_trivial_defaults_visible_snapshot",
            reason="non-trivial FlowGuard work defaults to a user-facing model snapshot",
        )


class ShowOrUpdateSnapshot:
    name = "ShowOrUpdateSnapshot"
    reads = ("tasks", "decisions")
    writes = ("evidence",)
    accepted_input_type = VisibilityDecision
    input_description = "VisibilityDecision"
    output_description = "WorkEvidence"
    idempotency = "same task has one diagram evidence row"

    def apply(self, input_obj: VisibilityDecision, state: State) -> Iterable[FunctionResult]:
        task = state.task_for(input_obj.task_id)
        if task is None:
            return
        if input_obj.mode == "default_visible_snapshot":
            evidence = WorkEvidence(
                input_obj.task_id,
                current_situation_shown=True,
                current_situation_updated=task.material_change,
                diagram_shown=True,
                diagram_updated=task.material_change,
                validation_run=True,
                validation_claimed=True,
                reason="current situation and diagram explain route, states, branches, evidence, gaps, and claim boundary",
            )
            yield FunctionResult(
                evidence,
                state.with_evidence(evidence),
                label="visible_snapshot_recorded",
                reason=evidence.reason,
            )
            return
        evidence = WorkEvidence(
            input_obj.task_id,
            current_situation_shown=False,
            current_situation_updated=False,
            diagram_shown=False,
            diagram_updated=False,
            validation_run=not task.non_trivial,
            validation_claimed=not task.non_trivial,
            reason="concise output is allowed for tiny or user-suppressed tasks",
        )
        yield FunctionResult(
            evidence,
            state.with_evidence(evidence),
            label="concise_path_recorded",
            reason=evidence.reason,
        )


class BrokenOptionalOnly(DecideVisibility):
    def apply(self, input_obj: PromptTask, state: State) -> Iterable[FunctionResult]:
        state = state.with_task(input_obj)
        decision = VisibilityDecision(input_obj.task_id, "concise_ok", input_obj.route)
        yield FunctionResult(
            decision,
            state.with_decision(decision),
            label="broken_optional_only",
            reason="broken prompt lets non-trivial work omit the visible snapshot",
        )


class BrokenDiagramAsValidation(ShowOrUpdateSnapshot):
    def apply(self, input_obj: VisibilityDecision, state: State) -> Iterable[FunctionResult]:
        task = state.task_for(input_obj.task_id)
        if task is None:
            return
        evidence = WorkEvidence(
            input_obj.task_id,
            current_situation_shown=input_obj.mode == "default_visible_snapshot",
            current_situation_updated=task.material_change,
            diagram_shown=input_obj.mode == "default_visible_snapshot",
            diagram_updated=task.material_change,
            validation_run=False,
            validation_claimed=True,
            reason="broken prompt treats diagram as validation evidence",
        )
        yield FunctionResult(
            evidence,
            state.with_evidence(evidence),
            label="broken_diagram_as_validation",
            reason=evidence.reason,
        )


class BrokenNoUpdateOnChange(ShowOrUpdateSnapshot):
    def apply(self, input_obj: VisibilityDecision, state: State) -> Iterable[FunctionResult]:
        task = state.task_for(input_obj.task_id)
        if task is None:
            return
        evidence = WorkEvidence(
            input_obj.task_id,
            current_situation_shown=input_obj.mode == "default_visible_snapshot",
            current_situation_updated=False,
            diagram_shown=input_obj.mode == "default_visible_snapshot",
            diagram_updated=False,
            validation_run=True,
            validation_claimed=True,
            reason="broken prompt never updates the visible snapshot after model changes",
        )
        yield FunctionResult(
            evidence,
            state.with_evidence(evidence),
            label="broken_no_update_on_change",
            reason=evidence.reason,
        )


class BrokenNoCurrentSituation(ShowOrUpdateSnapshot):
    def apply(self, input_obj: VisibilityDecision, state: State) -> Iterable[FunctionResult]:
        task = state.task_for(input_obj.task_id)
        if task is None:
            return
        evidence = WorkEvidence(
            input_obj.task_id,
            current_situation_shown=False,
            current_situation_updated=False,
            diagram_shown=input_obj.mode == "default_visible_snapshot",
            diagram_updated=task.material_change,
            validation_run=True,
            validation_claimed=True,
            reason="broken prompt shows a diagram without saying what FlowGuard is checking now",
        )
        yield FunctionResult(
            evidence,
            state.with_evidence(evidence),
            label="broken_no_current_situation",
            reason=evidence.reason,
        )


class BrokenForceTinyDiagram(DecideVisibility):
    def apply(self, input_obj: PromptTask, state: State) -> Iterable[FunctionResult]:
        state = state.with_task(input_obj)
        decision = VisibilityDecision(input_obj.task_id, "default_visible_snapshot", input_obj.route)
        yield FunctionResult(
            decision,
            state.with_decision(decision),
            label="broken_tiny_forced_diagram",
            reason="broken prompt forces diagrams for tiny tasks",
        )


def workflow(decider=None, shower=None) -> Workflow:
    return Workflow((decider or DecideVisibility(), shower or ShowOrUpdateSnapshot()), name="model_visibility")


def visible_snapshot_for_non_trivial(state: State, _trace) -> InvariantResult:
    bad = []
    for task in state.tasks:
        if task.non_trivial and not task.user_suppressed_diagram:
            evidence = next((item for item in state.evidence if item.task_id == task.task_id), None)
            if evidence is None or not evidence.diagram_shown:
                bad.append(task.task_id)
    if bad:
        return InvariantResult.fail(f"non-trivial tasks missing visible snapshot: {tuple(bad)!r}")
    return InvariantResult.pass_()


def current_situation_for_non_trivial(state: State, _trace) -> InvariantResult:
    bad = []
    for task in state.tasks:
        if task.non_trivial and not task.user_suppressed_diagram:
            evidence = next((item for item in state.evidence if item.task_id == task.task_id), None)
            if evidence is None or not evidence.current_situation_shown:
                bad.append(task.task_id)
    if bad:
        return InvariantResult.fail(f"non-trivial tasks missing current situation note: {tuple(bad)!r}")
    return InvariantResult.pass_()


def tiny_tasks_not_forced(state: State, _trace) -> InvariantResult:
    bad = []
    for task in state.tasks:
        if not task.non_trivial:
            decision = state.decision_for(task.task_id)
            if decision is not None and decision.mode == "default_visible_snapshot":
                bad.append(task.task_id)
    if bad:
        return InvariantResult.fail(f"tiny tasks forced to show diagrams: {tuple(bad)!r}")
    return InvariantResult.pass_()


def diagram_not_validation(state: State, _trace) -> InvariantResult:
    bad = tuple(
        evidence.task_id
        for evidence in state.evidence
        if evidence.validation_claimed and evidence.diagram_shown and not evidence.validation_run
    )
    if bad:
        return InvariantResult.fail(f"diagram treated as validation evidence: {bad!r}")
    return InvariantResult.pass_()


def material_changes_update_snapshot(state: State, _trace) -> InvariantResult:
    bad = []
    for task in state.tasks:
        if task.non_trivial and task.material_change and not task.user_suppressed_diagram:
            evidence = next((item for item in state.evidence if item.task_id == task.task_id), None)
            if evidence is None or not evidence.diagram_updated or not evidence.current_situation_updated:
                bad.append(task.task_id)
    if bad:
        return InvariantResult.fail(f"material model changes did not update snapshot and current situation: {tuple(bad)!r}")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant("visible_snapshot_for_non_trivial", "Non-trivial work defaults to visible model snapshots.", visible_snapshot_for_non_trivial),
    Invariant("current_situation_for_non_trivial", "Non-trivial work shows what FlowGuard is doing now.", current_situation_for_non_trivial),
    Invariant("tiny_tasks_not_forced", "Tiny tasks may remain concise.", tiny_tasks_not_forced),
    Invariant("diagram_not_validation", "Diagrams explain the model and do not validate it.", diagram_not_validation),
    Invariant("material_changes_update_snapshot", "Material model changes update the visible snapshot.", material_changes_update_snapshot),
)


TASKS = {
    "tiny": PromptTask("tiny-copyedit", "core_modeling", False),
    "ui": PromptTask("ui-journey", "ui_flow_structure", True),
    "miss": PromptTask("model-miss", "model_miss_review", True, material_change=True),
    "release": PromptTask("release-sync", "development_process_flow", True, material_change=True),
    "suppressed": PromptTask("user-suppressed", "model_mesh_maintenance", True, user_suppressed_diagram=True),
}

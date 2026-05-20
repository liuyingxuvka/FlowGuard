"""Self-review model for deciding when agents should trigger FlowGuard."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Sequence

from flowguard import (
    FunctionResult,
    Invariant,
    InvariantResult,
    Scenario,
    ScenarioExpectation,
    Workflow,
)


RISK_FLAGS = {
    "workflow",
    "state",
    "retry",
    "cache",
    "dedup",
    "idempotency",
    "side_effect",
    "module_boundary",
    "migration",
    "ui_state_flow",
    "ui_display_redundancy",
    "ui_control_overlap",
    "queue",
    "loop",
    "identity_conflict",
    "production_change",
    "argument_dependency",
    "reader_state",
    "evidence_chain",
    "proof_dependency",
    "decision_commitment",
    "goal_constraint",
    "assumption_validation",
    "reassessment",
    "irreversible_commitment",
    "many_flowguard_models",
    "cross_model_evidence",
    "stale_model_result",
    "staged_validation",
    "validation_freshness",
    "release_confidence",
    "model_test_alignment",
    "test_mesh",
    "stale_validation",
    "structure_mesh",
    "public_api_split",
    "code_structure",
    "model_miss",
    "runtime_after_pass",
    "existing_model_context",
}

DIRECT_SKILL_BY_ROUTE = {
    "existing_model_preflight": "flowguard-existing-model-preflight",
    "code_structure_recommendation": "flowguard-code-structure-recommendation",
    "ui_flow_structure": "flowguard-ui-flow-structure",
    "model_test_alignment": "flowguard-model-test-alignment",
    "model_mesh_maintenance": "flowguard-model-mesh",
    "test_mesh_maintenance": "flowguard-test-mesh",
    "structure_mesh_maintenance": "flowguard-structure-mesh",
    "development_process_flow": "flowguard-development-process-flow",
    "model_miss_review": "flowguard-model-miss-review",
}

FLOWGUARD_ROUTE_ACTIONS = {"use_direct_flowguard_skill", "use_model_first_kernel"}


@dataclass(frozen=True)
class TaskDescription:
    task_id: str
    kind: str
    risk_flags: tuple[str, ...] = ()
    production_code_exists: bool = True


@dataclass(frozen=True)
class RiskAssessment:
    task_id: str
    decision: str
    required_checks: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class SkillTriggerDecision:
    task_id: str
    action: str
    required_checks: tuple[str, ...]
    reason: str
    selected_skill: str = ""


@dataclass(frozen=True)
class ModelFirstAction:
    task_id: str
    model_started: bool
    checks_run: tuple[str, ...]
    status: str
    skip_reason: str


@dataclass(frozen=True)
class AdoptionEvidence:
    task_id: str
    status: str
    reason: str


@dataclass(frozen=True)
class TaskFact:
    task_id: str
    kind: str
    risk_flags: tuple[str, ...]
    production_code_exists: bool


@dataclass(frozen=True)
class State:
    task_facts: tuple[TaskFact, ...] = ()
    assessments: tuple[RiskAssessment, ...] = ()
    decisions: tuple[SkillTriggerDecision, ...] = ()
    actions: tuple[ModelFirstAction, ...] = ()
    evidence: tuple[AdoptionEvidence, ...] = ()

    def with_task(self, task: TaskDescription) -> "State":
        fact = TaskFact(task.task_id, task.kind, tuple(task.risk_flags), task.production_code_exists)
        if fact in self.task_facts:
            return self
        return replace(self, task_facts=self.task_facts + (fact,))

    def with_assessment(self, assessment: RiskAssessment) -> "State":
        return replace(
            self,
            assessments=tuple(item for item in self.assessments if item.task_id != assessment.task_id)
            + (assessment,),
        )

    def with_decision(self, decision: SkillTriggerDecision) -> "State":
        return replace(
            self,
            decisions=tuple(item for item in self.decisions if item.task_id != decision.task_id)
            + (decision,),
        )

    def with_action(self, action: ModelFirstAction) -> "State":
        return replace(
            self,
            actions=tuple(item for item in self.actions if item.task_id != action.task_id)
            + (action,),
        )

    def with_evidence(self, evidence: AdoptionEvidence) -> "State":
        return replace(
            self,
            evidence=tuple(item for item in self.evidence if item.task_id != evidence.task_id)
            + (evidence,),
        )

    def fact_for(self, task_id: str) -> TaskFact | None:
        return next((fact for fact in self.task_facts if fact.task_id == task_id), None)

    def assessment_for(self, task_id: str) -> RiskAssessment | None:
        return next((item for item in self.assessments if item.task_id == task_id), None)

    def decision_for(self, task_id: str) -> SkillTriggerDecision | None:
        return next((item for item in self.decisions if item.task_id == task_id), None)

    def action_for(self, task_id: str) -> ModelFirstAction | None:
        return next((item for item in self.actions if item.task_id == task_id), None)

    def evidence_for(self, task_id: str) -> AdoptionEvidence | None:
        return next((item for item in self.evidence if item.task_id == task_id), None)


def requires_flowguard(task: TaskDescription | TaskFact) -> bool:
    if task.kind in {"trivial_docs", "formatting", "read_only_question"}:
        return False
    if task.kind in {
        "major_architecture",
        "stateful_workflow",
        "new_project",
        "bug_fix",
        "structured_argument",
        "decision_plan",
        "model_maintenance",
        "process_change",
        "test_alignment",
        "validation_maintenance",
        "structure_refactor",
        "model_miss",
        "model_preflight",
    }:
        return True
    return bool(set(task.risk_flags) & RISK_FLAGS)


def needs_human_review(task: TaskDescription | TaskFact) -> bool:
    return task.kind == "uncertain_scope" or "unclear_boundary" in task.risk_flags


def required_checks_for(task: TaskDescription | TaskFact) -> tuple[str, ...]:
    if not requires_flowguard(task):
        return ()
    flags = set(task.risk_flags)
    checks = ["scenario"]
    if task.production_code_exists or "production_change" in flags:
        checks.append("conformance")
    if flags & {"retry", "queue", "loop", "workflow"}:
        checks.append("loop")
    if flags & {"retry", "queue", "loop"}:
        checks.append("progress")
    if flags & {"module_boundary", "migration"}:
        checks.append("contract")
    if flags & {"ui_state_flow", "ui_display_redundancy", "ui_control_overlap"}:
        checks.append("ui_flow_structure")
    if flags & {"many_flowguard_models", "cross_model_evidence", "stale_model_result"}:
        checks.append("model_mesh")
    if flags & {"staged_validation", "validation_freshness", "release_confidence"}:
        checks.append("development_process_flow")
    if flags & {"model_test_alignment"}:
        checks.append("model_test_alignment")
    if flags & {"test_mesh", "stale_validation"}:
        checks.append("test_mesh")
    if flags & {"structure_mesh", "public_api_split"}:
        checks.append("structure_mesh")
    if flags & {"code_structure"}:
        checks.append("code_structure_recommendation")
    if flags & {"model_miss", "runtime_after_pass"}:
        checks.append("model_miss_review")
    if flags & {"existing_model_context"}:
        checks.append("existing_model_preflight")
    return tuple(dict.fromkeys(checks))


def direct_route_for(task: TaskDescription | TaskFact | None) -> str:
    if task is None:
        return ""
    flags = set(task.risk_flags)
    if task.kind == "model_preflight" or flags & {"existing_model_context"}:
        return "existing_model_preflight"
    if task.kind == "major_architecture" or flags & {"code_structure", "module_boundary", "migration"}:
        return "code_structure_recommendation"
    if flags & {"ui_state_flow", "ui_display_redundancy", "ui_control_overlap"}:
        return "ui_flow_structure"
    if flags & {"model_test_alignment"}:
        return "model_test_alignment"
    if flags & {"many_flowguard_models", "cross_model_evidence", "stale_model_result"}:
        return "model_mesh_maintenance"
    if flags & {"test_mesh", "stale_validation"}:
        return "test_mesh_maintenance"
    if flags & {"structure_mesh", "public_api_split"}:
        return "structure_mesh_maintenance"
    if flags & {"staged_validation", "validation_freshness", "release_confidence"}:
        return "development_process_flow"
    if flags & {"model_miss", "runtime_after_pass"}:
        return "model_miss_review"
    return ""


def direct_skill_for(task: TaskDescription | TaskFact | None) -> str:
    return DIRECT_SKILL_BY_ROUTE.get(direct_route_for(task), "")


class ClassifyTaskRisk:
    name = "ClassifyTaskRisk"
    reads = ("task_facts",)
    writes = ("task_facts", "assessments")
    input_description = "TaskDescription"
    output_description = "RiskAssessment"
    idempotency = "same task produces one risk assessment"
    accepted_input_type = TaskDescription

    def apply(self, input_obj: TaskDescription, state: State) -> Iterable[FunctionResult]:
        state = state.with_task(input_obj)
        if needs_human_review(input_obj):
            assessment = RiskAssessment(input_obj.task_id, "needs_human_review", (), "scope boundary is unclear")
            yield FunctionResult(
                assessment,
                state.with_assessment(assessment),
                label="risk_needs_human_review",
                reason=assessment.reason,
            )
            return
        if requires_flowguard(input_obj):
            checks = required_checks_for(input_obj)
            assessment = RiskAssessment(
                input_obj.task_id,
                "flowguard_required",
                checks,
                "task changes behavior, state, workflow, side effects, module boundaries, argument dependencies, or decision commitments",
            )
            yield FunctionResult(
                assessment,
                state.with_assessment(assessment),
                label="risk_requires_flowguard",
                reason=assessment.reason,
            )
            return
        assessment = RiskAssessment(input_obj.task_id, "skip_allowed", (), "task is trivial or read-only")
        yield FunctionResult(
            assessment,
            state.with_assessment(assessment),
            label="risk_skip_allowed",
            reason=assessment.reason,
        )


class DecideSkillTrigger:
    name = "DecideSkillTrigger"
    reads = ("assessments",)
    writes = ("decisions",)
    input_description = "RiskAssessment"
    output_description = "SkillTriggerDecision"
    idempotency = "same assessment produces one trigger decision"
    accepted_input_type = RiskAssessment

    def apply(self, input_obj: RiskAssessment, state: State) -> Iterable[FunctionResult]:
        if input_obj.decision == "flowguard_required":
            fact = state.fact_for(input_obj.task_id)
            selected_skill = direct_skill_for(fact)
            if selected_skill:
                decision = SkillTriggerDecision(
                    input_obj.task_id,
                    "use_direct_flowguard_skill",
                    input_obj.required_checks,
                    f"{selected_skill} selected as the clear FlowGuard satellite route",
                    selected_skill,
                )
                label = "direct_satellite_selected"
            else:
                decision = SkillTriggerDecision(
                    input_obj.task_id,
                    "use_model_first_kernel",
                    input_obj.required_checks,
                    "model-first-function-flow selected for ordinary behavior/state modeling or route coordination",
                    "model-first-function-flow",
                )
                label = "kernel_route_selected"
        elif input_obj.decision == "needs_human_review":
            decision = SkillTriggerDecision(
                input_obj.task_id,
                "needs_human_review",
                (),
                "agent should ask or narrow scope before deciding whether to model",
            )
            label = "skill_trigger_needs_human_review"
        else:
            decision = SkillTriggerDecision(
                input_obj.task_id,
                "skip_skill",
                (),
                "skip is allowed because the task is trivial or read-only",
            )
            label = "skill_skipped_with_reason"
        yield FunctionResult(
            decision,
            state.with_decision(decision),
            label=label,
            reason=decision.reason,
        )


class RunModelFirstAction:
    name = "RunModelFirstAction"
    reads = ("decisions",)
    writes = ("actions",)
    input_description = "SkillTriggerDecision"
    output_description = "ModelFirstAction"
    idempotency = "same trigger decision records one model-first action"
    accepted_input_type = SkillTriggerDecision

    def apply(self, input_obj: SkillTriggerDecision, state: State) -> Iterable[FunctionResult]:
        if input_obj.action in FLOWGUARD_ROUTE_ACTIONS:
            action = ModelFirstAction(
                input_obj.task_id,
                True,
                input_obj.required_checks,
                "completed",
                "",
            )
            label = "flowguard_route_completed"
            reason = "required FlowGuard checks ran"
        elif input_obj.action == "needs_human_review":
            action = ModelFirstAction(
                input_obj.task_id,
                False,
                (),
                "blocked",
                input_obj.reason,
            )
            label = "flowguard_route_needs_human_review"
            reason = "scope must be clarified before validation can count"
        else:
            action = ModelFirstAction(
                input_obj.task_id,
                False,
                (),
                "skipped_with_reason",
                input_obj.reason,
            )
            label = "flowguard_skipped_with_reason"
            reason = "valid skip recorded"
        yield FunctionResult(action, state.with_action(action), label=label, reason=reason)


class RecordAdoptionEvidence:
    name = "RecordAdoptionEvidence"
    reads = ("actions",)
    writes = ("evidence",)
    input_description = "ModelFirstAction"
    output_description = "AdoptionEvidence"
    idempotency = "same task has one adoption evidence status"
    accepted_input_type = ModelFirstAction

    def apply(self, input_obj: ModelFirstAction, state: State) -> Iterable[FunctionResult]:
        evidence = AdoptionEvidence(
            input_obj.task_id,
            input_obj.status,
            "status records whether trigger work completed, skipped with reason, or blocked",
        )
        yield FunctionResult(
            evidence,
            state.with_evidence(evidence),
            label="trigger_evidence_recorded",
            reason=evidence.reason,
        )


class BrokenSkipRiskyTask(DecideSkillTrigger):
    name = "DecideSkillTrigger"

    def apply(self, input_obj: RiskAssessment, state: State) -> Iterable[FunctionResult]:
        decision = SkillTriggerDecision(input_obj.task_id, "skip_skill", (), "broken skip")
        yield FunctionResult(
            decision,
            state.with_decision(decision),
            label="broken_risky_skill_skipped",
            reason="broken trigger skips risky work",
        )


class BrokenTriggerTrivialTask(DecideSkillTrigger):
    name = "DecideSkillTrigger"

    def apply(self, input_obj: RiskAssessment, state: State) -> Iterable[FunctionResult]:
        decision = SkillTriggerDecision(input_obj.task_id, "trigger_skill", ("scenario",), "broken over-trigger")
        yield FunctionResult(
            decision,
            state.with_decision(decision),
            label="broken_trivial_skill_triggered",
            reason="broken trigger makes trivial tasks pay modeling cost",
        )


class BrokenRunMissingConformance(RunModelFirstAction):
    name = "RunModelFirstAction"

    def apply(self, input_obj: SkillTriggerDecision, state: State) -> Iterable[FunctionResult]:
        if input_obj.action in FLOWGUARD_ROUTE_ACTIONS:
            checks = tuple(check for check in input_obj.required_checks if check != "conformance")
            action = ModelFirstAction(input_obj.task_id, True, checks, "completed", "")
            yield FunctionResult(
                action,
                state.with_action(action),
                label="broken_missing_conformance",
                reason="broken action omits required conformance replay",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenRunMissingModelMesh(RunModelFirstAction):
    name = "RunModelFirstAction"

    def apply(self, input_obj: SkillTriggerDecision, state: State) -> Iterable[FunctionResult]:
        if input_obj.action in FLOWGUARD_ROUTE_ACTIONS:
            checks = tuple(check for check in input_obj.required_checks if check != "model_mesh")
            action = ModelFirstAction(input_obj.task_id, True, checks, "completed", "")
            yield FunctionResult(
                action,
                state.with_action(action),
                label="broken_missing_model_mesh",
                reason="broken action omits required model mesh for multi-model project",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenSkipWithoutReason(RunModelFirstAction):
    name = "RunModelFirstAction"

    def apply(self, input_obj: SkillTriggerDecision, state: State) -> Iterable[FunctionResult]:
        if input_obj.action == "skip_skill":
            action = ModelFirstAction(input_obj.task_id, False, (), "skipped_with_reason", "")
            yield FunctionResult(
                action,
                state.with_action(action),
                label="broken_skip_without_reason",
                reason="broken action records a skip without reason",
            )
            return
        yield from super().apply(input_obj, state)


class BrokenInProgressEvidence(RecordAdoptionEvidence):
    name = "RecordAdoptionEvidence"

    def apply(self, input_obj: ModelFirstAction, state: State) -> Iterable[FunctionResult]:
        evidence = AdoptionEvidence(input_obj.task_id, "in_progress", "broken evidence never finalized")
        yield FunctionResult(
            evidence,
            state.with_evidence(evidence),
            label="broken_in_progress_evidence",
            reason="broken evidence treats unfinished work as final",
        )


class BrokenClassifyAmbiguousAsSkip(ClassifyTaskRisk):
    name = "ClassifyTaskRisk"

    def apply(self, input_obj: TaskDescription, state: State) -> Iterable[FunctionResult]:
        state = state.with_task(input_obj)
        if needs_human_review(input_obj):
            assessment = RiskAssessment(input_obj.task_id, "skip_allowed", (), "broken ambiguity skipped")
            yield FunctionResult(
                assessment,
                state.with_assessment(assessment),
                label="broken_ambiguous_skipped",
                reason="broken classifier hides ambiguous scope",
            )
            return
        yield from super().apply(input_obj, state)


def risky_tasks_must_trigger_skill() -> Invariant:
    def predicate(state: State, _trace: object) -> InvariantResult:
        bad = []
        for fact in state.task_facts:
            if needs_human_review(fact):
                continue
            if requires_flowguard(fact):
                decision = state.decision_for(fact.task_id)
                if decision is None or decision.action not in FLOWGUARD_ROUTE_ACTIONS:
                    bad.append(fact.task_id)
        if bad:
            return InvariantResult.fail(f"risky tasks did not trigger Skill: {tuple(bad)!r}")
        return InvariantResult.pass_()

    return Invariant(
        "risky_tasks_must_trigger_skill",
        "Risky behavior/state/workflow/argument/decision tasks must select a FlowGuard route.",
        predicate,
    )


def trivial_tasks_should_not_overtrigger() -> Invariant:
    def predicate(state: State, _trace: object) -> InvariantResult:
        bad = []
        for fact in state.task_facts:
            if not requires_flowguard(fact) and not needs_human_review(fact):
                decision = state.decision_for(fact.task_id)
                if decision is not None and decision.action in FLOWGUARD_ROUTE_ACTIONS | {"trigger_skill"}:
                    bad.append(fact.task_id)
        if bad:
            return InvariantResult.fail(f"trivial tasks over-triggered FlowGuard: {tuple(bad)!r}")
        return InvariantResult.pass_()

    return Invariant(
        "trivial_tasks_should_not_overtrigger",
        "Trivial or read-only tasks should be allowed to skip with a reason.",
        predicate,
    )


def ambiguous_tasks_need_human_review() -> Invariant:
    def predicate(state: State, _trace: object) -> InvariantResult:
        bad = []
        for fact in state.task_facts:
            if needs_human_review(fact):
                decision = state.decision_for(fact.task_id)
                if decision is None or decision.action != "needs_human_review":
                    bad.append(fact.task_id)
        if bad:
            return InvariantResult.fail(f"ambiguous tasks did not request human review: {tuple(bad)!r}")
        return InvariantResult.pass_()

    return Invariant(
        "ambiguous_tasks_need_human_review",
        "Ambiguous workflow scope should be narrowed or reviewed before skipping or modeling.",
        predicate,
    )


def required_checks_must_run() -> Invariant:
    def predicate(state: State, _trace: object) -> InvariantResult:
        bad = []
        for decision in state.decisions:
            if decision.action not in FLOWGUARD_ROUTE_ACTIONS:
                continue
            action = state.action_for(decision.task_id)
            observed = set(action.checks_run if action else ())
            missing = tuple(sorted(set(decision.required_checks) - observed))
            if missing:
                bad.append((decision.task_id, missing))
        if bad:
            return InvariantResult.fail(f"triggered tasks missed required checks: {tuple(bad)!r}")
        return InvariantResult.pass_()

    return Invariant(
        "required_checks_must_run",
        "Triggered tasks must run the checks implied by their risk flags.",
        predicate,
    )


def direct_routes_select_matching_skill() -> Invariant:
    def predicate(state: State, _trace: object) -> InvariantResult:
        bad = []
        for fact in state.task_facts:
            if needs_human_review(fact) or not requires_flowguard(fact):
                continue
            expected = direct_skill_for(fact)
            if not expected:
                continue
            decision = state.decision_for(fact.task_id)
            if (
                decision is None
                or decision.action != "use_direct_flowguard_skill"
                or decision.selected_skill != expected
            ):
                bad.append((fact.task_id, expected, decision.selected_skill if decision else ""))
        if bad:
            return InvariantResult.fail(f"direct routes did not select matching skills: {tuple(bad)!r}")
        return InvariantResult.pass_()

    return Invariant(
        "direct_routes_select_matching_skill",
        "Clear satellite-route tasks must select the matching FlowGuard skill directly.",
        predicate,
    )


def skip_requires_reason() -> Invariant:
    def predicate(state: State, _trace: object) -> InvariantResult:
        bad = tuple(
            action.task_id
            for action in state.actions
            if action.status == "skipped_with_reason" and not action.skip_reason
        )
        if bad:
            return InvariantResult.fail(f"skipped tasks lack reasons: {bad!r}")
        return InvariantResult.pass_()

    return Invariant(
        "skip_requires_reason",
        "Any skipped Skill use must record the reason.",
        predicate,
    )


def final_evidence_must_not_be_in_progress() -> Invariant:
    def predicate(state: State, _trace: object) -> InvariantResult:
        bad = tuple(item.task_id for item in state.evidence if item.status == "in_progress")
        if bad:
            return InvariantResult.fail(f"final trigger evidence stayed in_progress: {bad!r}")
        return InvariantResult.pass_()

    return Invariant(
        "final_evidence_must_not_be_in_progress",
        "Final adoption evidence cannot stay in_progress.",
        predicate,
    )


INVARIANTS = (
    risky_tasks_must_trigger_skill(),
    trivial_tasks_should_not_overtrigger(),
    ambiguous_tasks_need_human_review(),
    required_checks_must_run(),
    direct_routes_select_matching_skill(),
    skip_requires_reason(),
    final_evidence_must_not_be_in_progress(),
)


TASK_ARCHITECTURE = TaskDescription(
    "architecture-cache-change",
    "major_architecture",
    ("state", "cache", "module_boundary", "production_change"),
)
TASK_UI_STATE = TaskDescription(
    "desktop-ui-flow",
    "stateful_workflow",
    ("ui_state_flow", "side_effect"),
    production_code_exists=False,
)
TASK_RETRY = TaskDescription(
    "retry-side-effect",
    "bug_fix",
    ("retry", "idempotency", "side_effect", "production_change"),
)
TASK_DOCS = TaskDescription("docs-copyedit", "trivial_docs", (), production_code_exists=False)
TASK_READ_ONLY = TaskDescription("explain-code", "read_only_question", (), production_code_exists=True)
TASK_AMBIGUOUS = TaskDescription(
    "unclear-redesign",
    "uncertain_scope",
    ("unclear_boundary",),
    production_code_exists=True,
)
TASK_ARGUMENT = TaskDescription(
    "paper-argument-flow",
    "structured_argument",
    ("argument_dependency", "reader_state", "evidence_chain"),
    production_code_exists=False,
)
TASK_DECISION = TaskDescription(
    "release-decision-flow",
    "decision_plan",
    ("decision_commitment", "goal_constraint", "reassessment"),
    production_code_exists=False,
)
TASK_MULTI_MODEL = TaskDescription(
    "multi-model-flowguard-project",
    "model_maintenance",
    ("many_flowguard_models", "cross_model_evidence", "stale_model_result"),
    production_code_exists=True,
)
TASK_PROCESS = TaskDescription(
    "release-process-flow",
    "process_change",
    ("staged_validation", "validation_freshness", "release_confidence"),
)
TASK_ALIGNMENT = TaskDescription(
    "model-test-alignment",
    "test_alignment",
    ("model_test_alignment",),
)
TASK_TEST_MESH = TaskDescription(
    "slow-test-mesh",
    "validation_maintenance",
    ("test_mesh", "stale_validation"),
)
TASK_STRUCTURE_MESH = TaskDescription(
    "large-structure-refactor",
    "structure_refactor",
    ("structure_mesh", "public_api_split"),
)
TASK_MODEL_MISS = TaskDescription(
    "post-runtime-model-miss",
    "model_miss",
    ("model_miss", "runtime_after_pass"),
)
TASK_EXISTING_MODEL_PREFLIGHT = TaskDescription(
    "existing-model-preflight",
    "model_preflight",
    ("existing_model_context",),
    production_code_exists=True,
)


def build_workflow(
    *,
    classify_block: object | None = None,
    trigger_block: object | None = None,
    action_block: object | None = None,
    evidence_block: object | None = None,
) -> Workflow:
    return Workflow(
        (
            classify_block or ClassifyTaskRisk(),
            trigger_block or DecideSkillTrigger(),
            action_block or RunModelFirstAction(),
            evidence_block or RecordAdoptionEvidence(),
        ),
        name="flowguard_skill_trigger",
    )


def _expect_ok(summary: str, labels: Sequence[str] = ()) -> ScenarioExpectation:
    return ScenarioExpectation(expected_status="ok", required_trace_labels=tuple(labels), summary=summary)


def _expect_violation(summary: str, names: Sequence[str]) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="violation",
        expected_violation_names=tuple(names),
        summary=summary,
    )


def scenario(
    name: str,
    description: str,
    task: TaskDescription,
    expected: ScenarioExpectation,
    *,
    workflow: Workflow | None = None,
) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        initial_state=State(),
        external_input_sequence=(task,),
        expected=expected,
        workflow=workflow or build_workflow(),
        invariants=INVARIANTS,
    )


def skill_trigger_scenarios() -> tuple[Scenario, ...]:
    return (
        scenario(
            "STS01_architecture_change_triggers_skill",
            "Architecture/state/module-boundary work should trigger FlowGuard.",
            TASK_ARCHITECTURE,
            _expect_ok(
                "OK; architecture task triggers Skill and runs scenario/conformance/contract",
                labels=("risk_requires_flowguard", "direct_satellite_selected", "flowguard_route_completed"),
            ),
        ),
        scenario(
            "STS02_ui_state_flow_triggers_skill",
            "UI state flow changes still have workflow state and side effects.",
            TASK_UI_STATE,
            _expect_ok(
                "OK; UI state workflow triggers Skill and includes UI flow structure",
                labels=("risk_requires_flowguard", "direct_satellite_selected", "flowguard_route_completed"),
            ),
        ),
        scenario(
            "STS03_trivial_docs_skips_with_reason",
            "Trivial copy edits should skip FlowGuard with an explicit reason.",
            TASK_DOCS,
            _expect_ok(
                "OK; trivial docs skip with reason",
                labels=("risk_skip_allowed", "skill_skipped_with_reason", "flowguard_skipped_with_reason"),
            ),
        ),
        scenario(
            "STS04_read_only_question_skips_with_reason",
            "Read-only explanation tasks should not pay modeling cost.",
            TASK_READ_ONLY,
            _expect_ok(
                "OK; read-only question skips with reason",
                labels=("risk_skip_allowed", "skill_skipped_with_reason"),
            ),
        ),
        scenario(
            "STS05_ambiguous_scope_needs_human_review",
            "Unclear redesign scope should not be silently skipped or blindly modeled.",
            TASK_AMBIGUOUS,
            ScenarioExpectation(
                expected_status="needs_human_review",
                required_trace_labels=("risk_needs_human_review", "skill_trigger_needs_human_review"),
                summary="NEEDS_HUMAN_REVIEW; narrow scope before deciding",
            ),
        ),
        scenario(
            "STS06_argument_flow_triggers_skill",
            "Structured writing with claim, evidence, and reader-state dependencies should trigger FlowGuard.",
            TASK_ARGUMENT,
            _expect_ok(
                "OK; argument flow triggers Skill and runs scenario review",
                labels=("risk_requires_flowguard", "kernel_route_selected", "flowguard_route_completed"),
            ),
        ),
        scenario(
            "STS07_decision_flow_triggers_skill",
            "Planning work with commitments, goals, and reassessment conditions should trigger FlowGuard.",
            TASK_DECISION,
            _expect_ok(
                "OK; decision flow triggers Skill and runs scenario review",
                labels=("risk_requires_flowguard", "kernel_route_selected", "flowguard_route_completed"),
            ),
        ),
        scenario(
            "STS08_multi_model_project_requires_model_mesh",
            "Projects with several local FlowGuard models should require a model mesh.",
            TASK_MULTI_MODEL,
            _expect_ok(
                "OK; multi-model project triggers Skill and runs model mesh",
                labels=("risk_requires_flowguard", "direct_satellite_selected", "flowguard_route_completed"),
            ),
        ),
        scenario(
            "STS09_process_flow_routes_directly",
            "Staged validation and release-confidence work should use DevelopmentProcessFlow.",
            TASK_PROCESS,
            _expect_ok(
                "OK; staged process work selects DevelopmentProcessFlow",
                labels=("risk_requires_flowguard", "direct_satellite_selected", "flowguard_route_completed"),
            ),
        ),
        scenario(
            "STS10_model_test_alignment_routes_directly",
            "Model obligations and test evidence should use Model-Test Alignment.",
            TASK_ALIGNMENT,
            _expect_ok(
                "OK; model-test alignment selects the alignment satellite",
                labels=("risk_requires_flowguard", "direct_satellite_selected", "flowguard_route_completed"),
            ),
        ),
        scenario(
            "STS11_test_mesh_routes_directly",
            "Large or stale validation evidence should use TestMesh.",
            TASK_TEST_MESH,
            _expect_ok(
                "OK; test hierarchy work selects TestMesh",
                labels=("risk_requires_flowguard", "direct_satellite_selected", "flowguard_route_completed"),
            ),
        ),
        scenario(
            "STS12_structure_mesh_routes_directly",
            "Large public API refactors should use StructureMesh.",
            TASK_STRUCTURE_MESH,
            _expect_ok(
                "OK; structure refactor work selects StructureMesh",
                labels=("risk_requires_flowguard", "direct_satellite_selected", "flowguard_route_completed"),
            ),
        ),
        scenario(
            "STS13_model_miss_routes_directly",
            "Runtime failures after a model pass should use Model-Miss Review.",
            TASK_MODEL_MISS,
            _expect_ok(
                "OK; model miss work selects Model-Miss Review",
                labels=("risk_requires_flowguard", "direct_satellite_selected", "flowguard_route_completed"),
            ),
        ),
        scenario(
            "STS14_existing_model_preflight_routes_directly",
            "Existing modeled system changes should be able to select Existing Model Preflight directly.",
            TASK_EXISTING_MODEL_PREFLIGHT,
            _expect_ok(
                "OK; existing-model context work selects Existing Model Preflight",
                labels=("risk_requires_flowguard", "direct_satellite_selected", "flowguard_route_completed"),
            ),
        ),
        scenario(
            "STB01_broken_skips_risky_architecture",
            "Broken trigger skips a risky architecture task.",
            TASK_ARCHITECTURE,
            _expect_violation(
                "VIOLATION risky_tasks_must_trigger_skill",
                ("risky_tasks_must_trigger_skill",),
            ),
            workflow=build_workflow(trigger_block=BrokenSkipRiskyTask()),
        ),
        scenario(
            "STB02_broken_overtriggers_trivial_docs",
            "Broken trigger makes trivial docs pay modeling cost.",
            TASK_DOCS,
            _expect_violation(
                "VIOLATION trivial_tasks_should_not_overtrigger",
                ("trivial_tasks_should_not_overtrigger",),
            ),
            workflow=build_workflow(trigger_block=BrokenTriggerTrivialTask()),
        ),
        scenario(
            "STB03_broken_missing_conformance",
            "Broken action skips conformance for production-facing retry work.",
            TASK_RETRY,
            _expect_violation(
                "VIOLATION required_checks_must_run",
                ("required_checks_must_run",),
            ),
            workflow=build_workflow(action_block=BrokenRunMissingConformance()),
        ),
        scenario(
            "STB04_broken_skip_without_reason",
            "Broken skip records no reason.",
            TASK_DOCS,
            _expect_violation(
                "VIOLATION skip_requires_reason",
                ("skip_requires_reason",),
            ),
            workflow=build_workflow(action_block=BrokenSkipWithoutReason()),
        ),
        scenario(
            "STB05_broken_in_progress_evidence_finalized",
            "Broken evidence leaves a completed trigger session marked in_progress.",
            TASK_ARCHITECTURE,
            _expect_violation(
                "VIOLATION final_evidence_must_not_be_in_progress",
                ("final_evidence_must_not_be_in_progress",),
            ),
            workflow=build_workflow(evidence_block=BrokenInProgressEvidence()),
        ),
        scenario(
            "STB06_broken_ambiguous_scope_skipped",
            "Broken classifier skips an ambiguous redesign instead of requesting review.",
            TASK_AMBIGUOUS,
            _expect_violation(
                "VIOLATION ambiguous_tasks_need_human_review",
                ("ambiguous_tasks_need_human_review",),
            ),
            workflow=build_workflow(classify_block=BrokenClassifyAmbiguousAsSkip()),
        ),
        scenario(
            "STB07_broken_missing_model_mesh",
            "Broken action skips the required model mesh for a multi-model project.",
            TASK_MULTI_MODEL,
            _expect_violation(
                "VIOLATION required_checks_must_run",
                ("required_checks_must_run",),
            ),
            workflow=build_workflow(action_block=BrokenRunMissingModelMesh()),
        ),
    )


def run_skill_trigger_review():
    from flowguard.review import review_scenarios

    return review_scenarios(skill_trigger_scenarios())


__all__ = [
    "State",
    "TaskDescription",
    "build_workflow",
    "run_skill_trigger_review",
    "skill_trigger_scenarios",
]

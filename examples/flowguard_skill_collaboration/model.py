"""Model optional collaboration between FlowGuard and upstream planning skills.

Risk Purpose Header:
This FlowGuard model reviews optional cooperation between FlowGuard
(https://github.com/liuyingxuvka/FlowGuard) and spec/SPAC-style planning or
orchestration skills. It guards against making FlowGuard depend on an external
planner, executing risky handoffs with hidden side effects, losing peer-agent
ownership boundaries, skipping checks without reasons, ignoring counterexamples,
over-triggering trivial work, and recording completion without evidence. Future
agents should run or update this model before changing FlowGuard Skill guidance,
handoff docs, or trigger logic for upstream planning tools.

Run:
python examples/flowguard_skill_collaboration/run_review.py
"""

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
    review_scenarios,
)


RISK_FLAGS = {
    "workflow",
    "state",
    "side_effect",
    "publish",
    "release",
    "install",
    "retry",
    "cache",
    "queue",
    "migration",
    "parallel_agents",
    "module_boundary",
    "external_action",
}


@dataclass(frozen=True)
class CollaborationPlan:
    task_id: str
    source: str
    risk_flags: tuple[str, ...] = ()
    upstream_tool_available: bool = False
    handoff_present: bool = False
    handoff_complete: bool = False
    side_effects_mapped: bool = False
    parallel_ownership_clear: bool = False
    skipped_checks: tuple[str, ...] = ()
    skip_reasons_present: bool = True
    model_checks_passed: bool = False
    counterexample_found: bool = False
    completion_evidence_present: bool = False
    trivial: bool = False


@dataclass(frozen=True)
class PlanAssessment:
    task_id: str
    mode: str
    risky: bool
    reason: str


@dataclass(frozen=True)
class ReviewDecision:
    task_id: str
    status: str
    model_started: bool
    checks_run: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ExecutionRecord:
    task_id: str
    status: str
    reason: str


@dataclass(frozen=True)
class State:
    plans: tuple[CollaborationPlan, ...] = ()
    assessments: tuple[PlanAssessment, ...] = ()
    decisions: tuple[ReviewDecision, ...] = ()
    executions: tuple[ExecutionRecord, ...] = ()

    def with_plan(self, plan: CollaborationPlan) -> "State":
        if plan in self.plans:
            return self
        return replace(self, plans=self.plans + (plan,))

    def with_assessment(self, assessment: PlanAssessment) -> "State":
        return replace(
            self,
            assessments=tuple(item for item in self.assessments if item.task_id != assessment.task_id)
            + (assessment,),
        )

    def with_decision(self, decision: ReviewDecision) -> "State":
        return replace(
            self,
            decisions=tuple(item for item in self.decisions if item.task_id != decision.task_id)
            + (decision,),
        )

    def with_execution(self, execution: ExecutionRecord) -> "State":
        return replace(
            self,
            executions=tuple(item for item in self.executions if item.task_id != execution.task_id)
            + (execution,),
        )

    def plan_for(self, task_id: str) -> CollaborationPlan | None:
        return next((item for item in self.plans if item.task_id == task_id), None)

    def assessment_for(self, task_id: str) -> PlanAssessment | None:
        return next((item for item in self.assessments if item.task_id == task_id), None)

    def decision_for(self, task_id: str) -> ReviewDecision | None:
        return next((item for item in self.decisions if item.task_id == task_id), None)

    def execution_for(self, task_id: str) -> ExecutionRecord | None:
        return next((item for item in self.executions if item.task_id == task_id), None)


def is_risky(plan: CollaborationPlan) -> bool:
    return bool(set(plan.risk_flags) & RISK_FLAGS)


class ClassifyCollaborationPlan:
    name = "ClassifyCollaborationPlan"
    reads = ("plans",)
    writes = ("plans", "assessments")
    input_description = "CollaborationPlan"
    output_description = "PlanAssessment"
    accepted_input_type = CollaborationPlan
    idempotency = "same collaboration plan produces one assessment"

    def apply(self, input_obj: CollaborationPlan, state: State) -> Iterable[FunctionResult]:
        state = state.with_plan(input_obj)
        risky = is_risky(input_obj)
        if input_obj.source == "upstream" and input_obj.upstream_tool_available:
            mode = "collaboration"
            reason = "upstream planner provided a candidate handoff"
        elif input_obj.source == "upstream":
            mode = "fallback"
            reason = "upstream planner unavailable; FlowGuard must stay standalone-capable"
        else:
            mode = "standalone"
            reason = "FlowGuard reviews the task directly"
        assessment = PlanAssessment(input_obj.task_id, mode, risky, reason)
        yield FunctionResult(
            assessment,
            state.with_assessment(assessment),
            label=f"mode_{mode}",
            reason=reason,
        )


class ReviewCollaborationPlan:
    name = "ReviewCollaborationPlan"
    reads = ("plans", "assessments")
    writes = ("decisions",)
    input_description = "PlanAssessment"
    output_description = "ReviewDecision"
    accepted_input_type = PlanAssessment
    idempotency = "same assessment records one review decision"

    def apply(self, input_obj: PlanAssessment, state: State) -> Iterable[FunctionResult]:
        plan = state.plan_for(input_obj.task_id)
        if plan is None:
            return

        if plan.trivial and not input_obj.risky:
            decision = ReviewDecision(
                plan.task_id,
                "skip_allowed",
                False,
                (),
                "trivial or read-only work can skip FlowGuard with a reason",
            )
            yield FunctionResult(
                decision,
                state.with_decision(decision),
                label="skip_allowed_with_reason",
                reason=decision.reason,
            )
            return

        if input_obj.mode == "collaboration":
            if not plan.handoff_present or not plan.handoff_complete:
                decision = ReviewDecision(
                    plan.task_id,
                    "needs_handoff_info",
                    False,
                    (),
                    "upstream handoff is missing required planning fields",
                )
                yield FunctionResult(
                    decision,
                    state.with_decision(decision),
                    label="handoff_info_required",
                    reason=decision.reason,
                )
                return
            if "side_effect" in plan.risk_flags and not plan.side_effects_mapped:
                decision = ReviewDecision(
                    plan.task_id,
                    "needs_handoff_info",
                    False,
                    (),
                    "side effects must be mapped before collaboration can continue",
                )
                yield FunctionResult(
                    decision,
                    state.with_decision(decision),
                    label="side_effect_map_required",
                    reason=decision.reason,
                )
                return
            if "parallel_agents" in plan.risk_flags and not plan.parallel_ownership_clear:
                decision = ReviewDecision(
                    plan.task_id,
                    "needs_handoff_info",
                    False,
                    (),
                    "parallel agent ownership must be explicit",
                )
                yield FunctionResult(
                    decision,
                    state.with_decision(decision),
                    label="parallel_ownership_required",
                    reason=decision.reason,
                )
                return

        if plan.skipped_checks and not plan.skip_reasons_present:
            decision = ReviewDecision(
                plan.task_id,
                "blocked",
                False,
                (),
                "skipped checks require explicit reasons",
            )
            yield FunctionResult(
                decision,
                state.with_decision(decision),
                label="skip_reason_required",
                reason=decision.reason,
            )
            return

        if plan.counterexample_found:
            decision = ReviewDecision(
                plan.task_id,
                "counterexample_found",
                True,
                ("scenario",),
                "counterexample blocks execution until the plan changes",
            )
            yield FunctionResult(
                decision,
                state.with_decision(decision),
                label="counterexample_blocks_execution",
                reason=decision.reason,
            )
            return

        if input_obj.risky and plan.model_checks_passed:
            checks = ["scenario"]
            if "parallel_agents" in plan.risk_flags:
                checks.append("ownership")
            if "side_effect" in plan.risk_flags:
                checks.append("side_effect")
            decision = ReviewDecision(
                plan.task_id,
                "pass",
                True,
                tuple(checks),
                "required FlowGuard checks passed before execution",
            )
            yield FunctionResult(
                decision,
                state.with_decision(decision),
                label="flowguard_review_passed",
                reason=decision.reason,
            )
            return

        if input_obj.risky:
            decision = ReviewDecision(
                plan.task_id,
                "model_required",
                True,
                (),
                "risky work needs FlowGuard checks before execution",
            )
            yield FunctionResult(
                decision,
                state.with_decision(decision),
                label="model_required_before_execution",
                reason=decision.reason,
            )
            return

        decision = ReviewDecision(
            plan.task_id,
            "skip_allowed",
            False,
            (),
            "no risky state, side effects, or commitments were found",
        )
        yield FunctionResult(
            decision,
            state.with_decision(decision),
            label="skip_allowed_with_reason",
            reason=decision.reason,
        )


class ExecuteAfterReview:
    name = "ExecuteAfterReview"
    reads = ("plans", "decisions")
    writes = ("executions",)
    input_description = "ReviewDecision"
    output_description = "ExecutionRecord"
    accepted_input_type = ReviewDecision
    idempotency = "same decision records one execution outcome"

    def apply(self, input_obj: ReviewDecision, state: State) -> Iterable[FunctionResult]:
        plan = state.plan_for(input_obj.task_id)
        if plan is None:
            return
        if input_obj.status == "pass":
            if plan.completion_evidence_present:
                execution = ExecutionRecord(plan.task_id, "executed", "review passed and evidence exists")
                label = "executed_after_review"
            else:
                execution = ExecutionRecord(plan.task_id, "blocked", "completion evidence is required")
                label = "completion_evidence_required"
        elif input_obj.status == "skip_allowed":
            execution = ExecutionRecord(plan.task_id, "skipped", input_obj.reason)
            label = "execution_skipped_with_reason"
        else:
            execution = ExecutionRecord(plan.task_id, "blocked", input_obj.reason)
            label = "execution_blocked"
        yield FunctionResult(
            execution,
            state.with_execution(execution),
            label=label,
            reason=execution.reason,
        )


class BrokenHardDependencyReview(ReviewCollaborationPlan):
    def apply(self, input_obj: PlanAssessment, state: State) -> Iterable[FunctionResult]:
        plan = state.plan_for(input_obj.task_id)
        if plan is not None and input_obj.mode == "fallback":
            decision = ReviewDecision(
                plan.task_id,
                "blocked",
                False,
                (),
                "missing_upstream_tool",
            )
            yield FunctionResult(
                decision,
                state.with_decision(decision),
                label="broken_hard_dependency",
                reason=decision.reason,
            )
            return
        yield from super().apply(input_obj, state)


class BrokenLooseReview(ReviewCollaborationPlan):
    ignored_label = "broken_loose_review"
    ignored_reason = "broken review ignores missing handoff detail"

    def apply(self, input_obj: PlanAssessment, state: State) -> Iterable[FunctionResult]:
        plan = state.plan_for(input_obj.task_id)
        if plan is not None and input_obj.mode == "collaboration":
            decision = ReviewDecision(
                plan.task_id,
                "pass",
                True,
                ("scenario",),
                self.ignored_reason,
            )
            yield FunctionResult(
                decision,
                state.with_decision(decision),
                label=self.ignored_label,
                reason=decision.reason,
            )
            return
        yield from super().apply(input_obj, state)


class BrokenSkipReasonReview(ReviewCollaborationPlan):
    def apply(self, input_obj: PlanAssessment, state: State) -> Iterable[FunctionResult]:
        plan = state.plan_for(input_obj.task_id)
        if plan is not None and plan.skipped_checks:
            decision = ReviewDecision(
                plan.task_id,
                "skip_allowed",
                False,
                (),
                "broken skip accepted without reason",
            )
            yield FunctionResult(
                decision,
                state.with_decision(decision),
                label="broken_skip_without_reason",
                reason=decision.reason,
            )
            return
        yield from super().apply(input_obj, state)


class BrokenCounterexampleReview(ReviewCollaborationPlan):
    def apply(self, input_obj: PlanAssessment, state: State) -> Iterable[FunctionResult]:
        plan = state.plan_for(input_obj.task_id)
        if plan is not None and plan.counterexample_found:
            decision = ReviewDecision(
                plan.task_id,
                "pass",
                True,
                ("scenario",),
                "broken review ignores counterexample",
            )
            yield FunctionResult(
                decision,
                state.with_decision(decision),
                label="broken_counterexample_ignored",
                reason=decision.reason,
            )
            return
        yield from super().apply(input_obj, state)


class BrokenOvertriggerTrivialReview(ReviewCollaborationPlan):
    def apply(self, input_obj: PlanAssessment, state: State) -> Iterable[FunctionResult]:
        plan = state.plan_for(input_obj.task_id)
        if plan is not None and plan.trivial:
            decision = ReviewDecision(
                plan.task_id,
                "pass",
                True,
                ("scenario",),
                "broken over-trigger for trivial work",
            )
            yield FunctionResult(
                decision,
                state.with_decision(decision),
                label="broken_overtrigger_trivial",
                reason=decision.reason,
            )
            return
        yield from super().apply(input_obj, state)


class BrokenExecuteWithoutEvidence(ExecuteAfterReview):
    def apply(self, input_obj: ReviewDecision, state: State) -> Iterable[FunctionResult]:
        plan = state.plan_for(input_obj.task_id)
        if plan is not None and input_obj.status == "pass":
            execution = ExecutionRecord(plan.task_id, "executed", "broken execution ignores missing evidence")
            yield FunctionResult(
                execution,
                state.with_execution(execution),
                label="broken_missing_completion_evidence",
                reason=execution.reason,
            )
            return
        yield from super().apply(input_obj, state)


def no_hard_dependency_on_upstream_tool() -> Invariant:
    def check(state: State, _trace: object) -> InvariantResult:
        bad = []
        for plan in state.plans:
            assessment = state.assessment_for(plan.task_id)
            decision = state.decision_for(plan.task_id)
            if assessment and assessment.mode == "fallback" and decision and decision.reason == "missing_upstream_tool":
                bad.append(plan.task_id)
        if bad:
            return InvariantResult.fail(f"FlowGuard depended on missing upstream tools: {tuple(bad)!r}")
        return InvariantResult.pass_()

    return Invariant(
        "no_hard_dependency_on_upstream_tool",
        "Missing spec/SPAC tools must not make FlowGuard unusable.",
        check,
    )


def risky_upstream_plans_require_review_before_execution() -> Invariant:
    def check(state: State, _trace: object) -> InvariantResult:
        bad = []
        for plan in state.plans:
            execution = state.execution_for(plan.task_id)
            decision = state.decision_for(plan.task_id)
            if (
                plan.source == "upstream"
                and is_risky(plan)
                and execution
                and execution.status == "executed"
                and (decision is None or decision.status != "pass" or not decision.model_started)
            ):
                bad.append(plan.task_id)
        if bad:
            return InvariantResult.fail(f"risky upstream plans executed without review: {tuple(bad)!r}")
        return InvariantResult.pass_()

    return Invariant(
        "risky_upstream_plans_require_review_before_execution",
        "Risky upstream plans must have FlowGuard review evidence before execution.",
        check,
    )


def side_effects_must_be_mapped() -> Invariant:
    def check(state: State, _trace: object) -> InvariantResult:
        bad = []
        for plan in state.plans:
            execution = state.execution_for(plan.task_id)
            if "side_effect" in plan.risk_flags and execution and execution.status == "executed":
                if not plan.side_effects_mapped:
                    bad.append(plan.task_id)
        if bad:
            return InvariantResult.fail(f"side effects executed without handoff mapping: {tuple(bad)!r}")
        return InvariantResult.pass_()

    return Invariant(
        "side_effects_must_be_mapped",
        "Collaboration handoffs must map side effects before execution.",
        check,
    )


def parallel_work_needs_ownership() -> Invariant:
    def check(state: State, _trace: object) -> InvariantResult:
        bad = []
        for plan in state.plans:
            execution = state.execution_for(plan.task_id)
            if "parallel_agents" in plan.risk_flags and execution and execution.status == "executed":
                if not plan.parallel_ownership_clear:
                    bad.append(plan.task_id)
        if bad:
            return InvariantResult.fail(f"parallel work executed without ownership: {tuple(bad)!r}")
        return InvariantResult.pass_()

    return Invariant(
        "parallel_work_needs_ownership",
        "Parallel agents need explicit ownership boundaries before execution.",
        check,
    )


def skipped_checks_need_reasons() -> Invariant:
    def check(state: State, _trace: object) -> InvariantResult:
        bad = []
        for plan in state.plans:
            decision = state.decision_for(plan.task_id)
            if plan.skipped_checks and decision and decision.status in {"pass", "skip_allowed"}:
                if not plan.skip_reasons_present:
                    bad.append(plan.task_id)
        if bad:
            return InvariantResult.fail(f"skipped checks lacked reasons: {tuple(bad)!r}")
        return InvariantResult.pass_()

    return Invariant(
        "skipped_checks_need_reasons",
        "Skipped checks must stay visible and include a reason.",
        check,
    )


def counterexamples_block_execution() -> Invariant:
    def check(state: State, _trace: object) -> InvariantResult:
        bad = []
        for plan in state.plans:
            execution = state.execution_for(plan.task_id)
            if plan.counterexample_found and execution and execution.status == "executed":
                bad.append(plan.task_id)
        if bad:
            return InvariantResult.fail(f"counterexamples did not block execution: {tuple(bad)!r}")
        return InvariantResult.pass_()

    return Invariant(
        "counterexamples_block_execution",
        "A counterexample must stop execution until the plan changes.",
        check,
    )


def trivial_work_should_not_overtrigger() -> Invariant:
    def check(state: State, _trace: object) -> InvariantResult:
        bad = []
        for plan in state.plans:
            decision = state.decision_for(plan.task_id)
            if plan.trivial and not is_risky(plan) and decision and decision.model_started:
                bad.append(plan.task_id)
        if bad:
            return InvariantResult.fail(f"trivial work over-triggered FlowGuard: {tuple(bad)!r}")
        return InvariantResult.pass_()

    return Invariant(
        "trivial_work_should_not_overtrigger",
        "Trivial read-only work should skip with a reason instead of starting a model.",
        check,
    )


def completion_needs_evidence() -> Invariant:
    def check(state: State, _trace: object) -> InvariantResult:
        bad = []
        for plan in state.plans:
            execution = state.execution_for(plan.task_id)
            if is_risky(plan) and execution and execution.status == "executed":
                if not plan.completion_evidence_present:
                    bad.append(plan.task_id)
        if bad:
            return InvariantResult.fail(f"risky work completed without evidence: {tuple(bad)!r}")
        return InvariantResult.pass_()

    return Invariant(
        "completion_needs_evidence",
        "Risky work cannot be recorded complete without evidence.",
        check,
    )


INVARIANTS = (
    no_hard_dependency_on_upstream_tool(),
    risky_upstream_plans_require_review_before_execution(),
    side_effects_must_be_mapped(),
    parallel_work_needs_ownership(),
    skipped_checks_need_reasons(),
    counterexamples_block_execution(),
    trivial_work_should_not_overtrigger(),
    completion_needs_evidence(),
)


GOOD_STANDALONE = CollaborationPlan(
    "standalone-risky",
    "direct",
    ("workflow", "state"),
    model_checks_passed=True,
    completion_evidence_present=True,
)
GOOD_COLLABORATION = CollaborationPlan(
    "collaboration-good",
    "upstream",
    ("workflow", "side_effect", "parallel_agents"),
    upstream_tool_available=True,
    handoff_present=True,
    handoff_complete=True,
    side_effects_mapped=True,
    parallel_ownership_clear=True,
    skipped_checks=("full_release_suite",),
    skip_reasons_present=True,
    model_checks_passed=True,
    completion_evidence_present=True,
)
GOOD_FALLBACK = CollaborationPlan(
    "fallback-no-tool",
    "upstream",
    ("workflow", "state"),
    upstream_tool_available=False,
    model_checks_passed=True,
    completion_evidence_present=True,
)
GOOD_TRIVIAL = CollaborationPlan("trivial-read-only", "direct", trivial=True)
INCOMPLETE_HANDOFF = CollaborationPlan(
    "collaboration-missing-handoff",
    "upstream",
    ("workflow", "side_effect"),
    upstream_tool_available=True,
    handoff_present=True,
    handoff_complete=False,
    model_checks_passed=True,
)
SIDE_EFFECT_UNMAPPED = CollaborationPlan(
    "side-effect-unmapped",
    "upstream",
    ("workflow", "side_effect"),
    upstream_tool_available=True,
    handoff_present=True,
    handoff_complete=True,
    side_effects_mapped=False,
    model_checks_passed=True,
    completion_evidence_present=True,
)
PARALLEL_UNOWNED = CollaborationPlan(
    "parallel-unowned",
    "upstream",
    ("workflow", "parallel_agents"),
    upstream_tool_available=True,
    handoff_present=True,
    handoff_complete=True,
    parallel_ownership_clear=False,
    model_checks_passed=True,
    completion_evidence_present=True,
)
SKIP_WITHOUT_REASON = CollaborationPlan(
    "skip-without-reason",
    "upstream",
    ("workflow",),
    upstream_tool_available=True,
    handoff_present=True,
    handoff_complete=True,
    skipped_checks=("conformance",),
    skip_reasons_present=False,
)
COUNTEREXAMPLE_PLAN = CollaborationPlan(
    "counterexample-plan",
    "upstream",
    ("workflow", "side_effect"),
    upstream_tool_available=True,
    handoff_present=True,
    handoff_complete=True,
    side_effects_mapped=True,
    counterexample_found=True,
    completion_evidence_present=True,
)
MISSING_EVIDENCE = CollaborationPlan(
    "missing-evidence",
    "upstream",
    ("workflow", "side_effect"),
    upstream_tool_available=True,
    handoff_present=True,
    handoff_complete=True,
    side_effects_mapped=True,
    model_checks_passed=True,
    completion_evidence_present=False,
)


def build_workflow(
    *,
    review_block: object | None = None,
    execution_block: object | None = None,
) -> Workflow:
    return Workflow(
        (
            ClassifyCollaborationPlan(),
            review_block or ReviewCollaborationPlan(),
            execution_block or ExecuteAfterReview(),
        ),
        name="flowguard_skill_collaboration",
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
    plan: CollaborationPlan,
    expected: ScenarioExpectation,
    *,
    workflow: Workflow | None = None,
) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        initial_state=State(),
        external_input_sequence=(plan,),
        expected=expected,
        workflow=workflow or build_workflow(),
        invariants=INVARIANTS,
    )


def skill_collaboration_scenarios() -> tuple[Scenario, ...]:
    return (
        scenario(
            "SCS01_standalone_mode_still_works",
            "FlowGuard must work without any upstream planning skill.",
            GOOD_STANDALONE,
            _expect_ok(
                "OK; standalone risky work passed FlowGuard checks",
                labels=("mode_standalone", "flowguard_review_passed", "executed_after_review"),
            ),
        ),
        scenario(
            "SCS02_collaboration_mode_accepts_complete_handoff",
            "A complete upstream handoff can pass after FlowGuard review.",
            GOOD_COLLABORATION,
            _expect_ok(
                "OK; collaboration handoff passed FlowGuard checks",
                labels=("mode_collaboration", "flowguard_review_passed", "executed_after_review"),
            ),
        ),
        scenario(
            "SCS03_missing_upstream_tool_falls_back",
            "Missing upstream planner should not block FlowGuard itself.",
            GOOD_FALLBACK,
            _expect_ok(
                "OK; missing upstream tool fell back to FlowGuard",
                labels=("mode_fallback", "flowguard_review_passed", "executed_after_review"),
            ),
        ),
        scenario(
            "SCS04_trivial_work_skips_with_reason",
            "Trivial read-only work should skip without starting a model.",
            GOOD_TRIVIAL,
            _expect_ok(
                "OK; trivial work skipped with a reason",
                labels=("mode_standalone", "skip_allowed_with_reason", "execution_skipped_with_reason"),
            ),
        ),
        scenario(
            "SCS05_incomplete_handoff_blocks_collaboration",
            "Incomplete upstream handoff should request more information.",
            INCOMPLETE_HANDOFF,
            _expect_ok(
                "OK; incomplete handoff was blocked before execution",
                labels=("mode_collaboration", "handoff_info_required", "execution_blocked"),
            ),
        ),
        scenario(
            "SCB01_broken_hard_dependency_on_upstream_tool",
            "Broken review blocks FlowGuard just because the upstream tool is missing.",
            GOOD_FALLBACK,
            _expect_violation(
                "VIOLATION no_hard_dependency_on_upstream_tool",
                ("no_hard_dependency_on_upstream_tool",),
            ),
            workflow=build_workflow(review_block=BrokenHardDependencyReview()),
        ),
        scenario(
            "SCB02_broken_side_effects_not_mapped",
            "Broken review executes side effects without a handoff map.",
            SIDE_EFFECT_UNMAPPED,
            _expect_violation(
                "VIOLATION side_effects_must_be_mapped",
                ("side_effects_must_be_mapped",),
            ),
            workflow=build_workflow(review_block=BrokenLooseReview()),
        ),
        scenario(
            "SCB03_broken_parallel_work_without_ownership",
            "Broken review executes parallel work without ownership boundaries.",
            PARALLEL_UNOWNED,
            _expect_violation(
                "VIOLATION parallel_work_needs_ownership",
                ("parallel_work_needs_ownership",),
            ),
            workflow=build_workflow(review_block=BrokenLooseReview()),
        ),
        scenario(
            "SCB04_broken_skip_without_reason",
            "Broken review accepts skipped checks without reasons.",
            SKIP_WITHOUT_REASON,
            _expect_violation(
                "VIOLATION skipped_checks_need_reasons",
                ("skipped_checks_need_reasons",),
            ),
            workflow=build_workflow(review_block=BrokenSkipReasonReview()),
        ),
        scenario(
            "SCB05_broken_counterexample_ignored",
            "Broken review executes after a counterexample.",
            COUNTEREXAMPLE_PLAN,
            _expect_violation(
                "VIOLATION counterexamples_block_execution",
                ("counterexamples_block_execution",),
            ),
            workflow=build_workflow(review_block=BrokenCounterexampleReview()),
        ),
        scenario(
            "SCB06_broken_trivial_work_overtriggers",
            "Broken review starts a model for trivial read-only work.",
            GOOD_TRIVIAL,
            _expect_violation(
                "VIOLATION trivial_work_should_not_overtrigger",
                ("trivial_work_should_not_overtrigger",),
            ),
            workflow=build_workflow(review_block=BrokenOvertriggerTrivialReview()),
        ),
        scenario(
            "SCB07_broken_completion_without_evidence",
            "Broken execution records risky work complete without evidence.",
            MISSING_EVIDENCE,
            _expect_violation(
                "VIOLATION completion_needs_evidence",
                ("completion_needs_evidence",),
            ),
            workflow=build_workflow(execution_block=BrokenExecuteWithoutEvidence()),
        ),
    )


def run_skill_collaboration_review():
    return review_scenarios(skill_collaboration_scenarios())


__all__ = [
    "CollaborationPlan",
    "run_skill_collaboration_review",
    "skill_collaboration_scenarios",
]

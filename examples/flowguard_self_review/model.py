"""Model flowguard's own model-first adoption workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from flowguard import (
    FunctionResult,
    Invariant,
    InvariantResult,
    OracleCheckResult,
    Scenario,
    ScenarioExpectation,
    ScenarioRun,
    Workflow,
)


TaskKey = tuple[str, int]


@dataclass(frozen=True)
class ProductTask:
    task_id: str
    revision: int
    kind: str
    risk_flags: tuple[str, ...] = ()
    production_change: bool = True

    @property
    def key(self) -> TaskKey:
        return (self.task_id, self.revision)


@dataclass(frozen=True)
class ToolchainStatus:
    task: ProductTask
    connected: bool
    reason: str

    @property
    def key(self) -> TaskKey:
        return self.task.key


@dataclass(frozen=True)
class TriggerDecision:
    task_id: str
    revision: int
    action: str
    required_checks: tuple[str, ...]
    reason: str

    @property
    def key(self) -> TaskKey:
        return (self.task_id, self.revision)


@dataclass(frozen=True)
class ModelPlan:
    task_id: str
    revision: int
    model_ready: bool
    required_checks: tuple[str, ...]
    reason: str

    @property
    def key(self) -> TaskKey:
        return (self.task_id, self.revision)


@dataclass(frozen=True)
class CheckOutcome:
    task_id: str
    revision: int
    required_checks: tuple[str, ...]
    checks_run: tuple[str, ...]
    has_counterexample: bool
    reason: str

    @property
    def key(self) -> TaskKey:
        return (self.task_id, self.revision)


@dataclass(frozen=True)
class ApprovalDecision:
    task_id: str
    revision: int
    status: str
    reason: str

    @property
    def key(self) -> TaskKey:
        return (self.task_id, self.revision)


@dataclass(frozen=True)
class AdoptionOutcome:
    task_id: str
    revision: int
    logged: bool
    status: str
    reason: str


@dataclass(frozen=True)
class AdoptionStatusRecord:
    task_id: str
    revision: int
    status: str

    @property
    def key(self) -> TaskKey:
        return (self.task_id, self.revision)


@dataclass(frozen=True)
class TaskFact:
    task_id: str
    revision: int
    kind: str
    risk_flags: tuple[str, ...]
    production_change: bool

    @property
    def key(self) -> TaskKey:
        return (self.task_id, self.revision)


@dataclass(frozen=True)
class ModelArtifact:
    task_id: str
    revision: int

    @property
    def key(self) -> TaskKey:
        return (self.task_id, self.revision)


@dataclass(frozen=True)
class CheckRecord:
    task_id: str
    revision: int
    check_name: str
    status: str

    @property
    def key(self) -> TaskKey:
        return (self.task_id, self.revision)


@dataclass(frozen=True)
class SkippedStep:
    task_id: str
    revision: int
    step: str
    reason: str


@dataclass(frozen=True)
class ToolchainPreflight:
    task_id: str
    revision: int
    connected: bool
    reason: str

    @property
    def key(self) -> TaskKey:
        return (self.task_id, self.revision)


@dataclass(frozen=True)
class State:
    task_facts: tuple[TaskFact, ...] = ()
    toolchain_preflights: tuple[ToolchainPreflight, ...] = ()
    toolchain_failures: tuple[TaskKey, ...] = ()
    trigger_decisions: tuple[TriggerDecision, ...] = ()
    models: tuple[ModelArtifact, ...] = ()
    checks: tuple[CheckRecord, ...] = ()
    approvals: tuple[ApprovalDecision, ...] = ()
    adoption_logs: tuple[TaskKey, ...] = ()
    adoption_statuses: tuple[AdoptionStatusRecord, ...] = ()
    skipped_steps: tuple[SkippedStep, ...] = ()
    counterexamples: tuple[TaskKey, ...] = ()
    daily_reviews: tuple[TaskKey, ...] = ()

    def fact_for(self, key: TaskKey) -> TaskFact | None:
        return next((fact for fact in self.task_facts if fact.key == key), None)

    def with_task_fact(self, task: ProductTask) -> "State":
        fact = TaskFact(
            task.task_id,
            task.revision,
            task.kind,
            tuple(task.risk_flags),
            bool(task.production_change),
        )
        if fact in self.task_facts:
            return self
        return replace_state(self, task_facts=self.task_facts + (fact,))

    def with_toolchain_preflight(self, key: TaskKey, connected: bool, reason: str) -> "State":
        preflight = ToolchainPreflight(key[0], key[1], connected, reason)
        failures = self.toolchain_failures
        if not connected and key not in failures:
            failures = failures + (key,)
        if preflight in self.toolchain_preflights:
            return replace_state(self, toolchain_failures=failures)
        return replace_state(
            self,
            toolchain_preflights=self.toolchain_preflights + (preflight,),
            toolchain_failures=failures,
        )

    def with_trigger_decision(self, decision: TriggerDecision) -> "State":
        if decision in self.trigger_decisions:
            return self
        return replace_state(self, trigger_decisions=self.trigger_decisions + (decision,))

    def with_model(self, key: TaskKey) -> "State":
        artifact = ModelArtifact(*key)
        if artifact in self.models:
            return self
        return replace_state(self, models=self.models + (artifact,))

    def with_check(self, key: TaskKey, check_name: str, status: str = "passed") -> "State":
        record = CheckRecord(key[0], key[1], check_name, status)
        if record in self.checks:
            return self
        return replace_state(self, checks=self.checks + (record,))

    def with_approval(self, approval: ApprovalDecision) -> "State":
        if approval in self.approvals:
            return self
        return replace_state(self, approvals=self.approvals + (approval,))

    def with_adoption_log(self, key: TaskKey, status: str) -> "State":
        logs = self.adoption_logs if key in self.adoption_logs else self.adoption_logs + (key,)
        record = AdoptionStatusRecord(key[0], key[1], status)
        statuses = tuple(item for item in self.adoption_statuses if item.key != key)
        statuses = statuses + (record,)
        return replace_state(self, adoption_logs=logs, adoption_statuses=statuses)

    def with_skipped_step(self, skipped: SkippedStep) -> "State":
        if skipped in self.skipped_steps:
            return self
        return replace_state(self, skipped_steps=self.skipped_steps + (skipped,))

    def with_counterexample(self, key: TaskKey) -> "State":
        if key in self.counterexamples:
            return self
        return replace_state(self, counterexamples=self.counterexamples + (key,))

    def with_daily_review(self, key: TaskKey) -> "State":
        if key in self.daily_reviews:
            return self
        return replace_state(self, daily_reviews=self.daily_reviews + (key,))


def replace_state(state: State, **changes: object) -> State:
    values = {
        "task_facts": state.task_facts,
        "toolchain_preflights": state.toolchain_preflights,
        "toolchain_failures": state.toolchain_failures,
        "trigger_decisions": state.trigger_decisions,
        "models": state.models,
        "checks": state.checks,
        "approvals": state.approvals,
        "adoption_logs": state.adoption_logs,
        "adoption_statuses": state.adoption_statuses,
        "skipped_steps": state.skipped_steps,
        "counterexamples": state.counterexamples,
        "daily_reviews": state.daily_reviews,
    }
    values.update(changes)
    return State(**values)


def requires_flowguard(task: ProductTask | TaskFact) -> bool:
    if task.kind in {"trivial_docs", "daily_review"}:
        return False
    if task.kind in {"new_project", "major_architecture", "stateful_workflow"}:
        return True
    risky = {
        "retry",
        "dedup",
        "cache",
        "idempotency",
        "side_effect",
        "module_boundary",
        "cycle",
        "escape_cycle",
        "production_change",
    }
    return bool(set(task.risk_flags) & risky or task.production_change)


def required_checks_for(task: ProductTask | TaskFact) -> tuple[str, ...]:
    if not requires_flowguard(task):
        return ()
    checks = ["scenario"]
    flags = set(task.risk_flags)
    if task.production_change or "production_change" in flags:
        checks.append("conformance")
    if flags & {"retry", "cycle", "queue", "reprocessing"}:
        checks.append("loop")
    if flags & {"retry", "cycle", "escape_cycle", "human_review_loop"}:
        checks.append("progress")
    if "module_boundary" in flags:
        checks.append("contract")
    return tuple(dict.fromkeys(checks))


def _has_model(state: State, key: TaskKey) -> bool:
    return any(model.key == key for model in state.models)


def _checks_for(state: State, key: TaskKey) -> set[str]:
    return {
        check.check_name
        for check in state.checks
        if check.key == key and check.status == "passed"
    }


def _checks_run_for(state: State, key: TaskKey) -> set[str]:
    return {
        check.check_name
        for check in state.checks
        if check.key == key and check.status in {"passed", "failed"}
    }


def _approved_keys(state: State) -> tuple[TaskKey, ...]:
    return tuple(approval.key for approval in state.approvals if approval.status == "approved")


def _approval_for(state: State, key: TaskKey) -> ApprovalDecision | None:
    return next((approval for approval in state.approvals if approval.key == key), None)


def _nontrivial_keys(state: State) -> tuple[TaskKey, ...]:
    return tuple(fact.key for fact in state.task_facts if requires_flowguard(fact))


def _adoption_status_for(state: State, key: TaskKey) -> str | None:
    record = next((item for item in state.adoption_statuses if item.key == key), None)
    return record.status if record else None


class VerifyFlowguardToolchain:
    name = "VerifyFlowguardToolchain"
    reads = ("task_facts", "toolchain_preflights")
    writes = ("task_facts", "toolchain_preflights", "toolchain_failures")
    input_description = "ProductTask"
    output_description = "ToolchainStatus"
    idempotency = "same task revision has one toolchain preflight result"
    accepted_input_type = ProductTask

    def apply(self, input_obj: ProductTask, state: State) -> Iterable[FunctionResult]:
        state = state.with_task_fact(input_obj)
        connected = "toolchain_unavailable" not in input_obj.risk_flags
        reason = (
            "formal flowguard package import preflight passed"
            if connected
            else "formal flowguard package is not importable; do not replace it with an ad-hoc mini-framework"
        )
        new_state = state.with_toolchain_preflight(input_obj.key, connected, reason)
        yield FunctionResult(
            ToolchainStatus(input_obj, connected, reason),
            new_state,
            label="toolchain_available" if connected else "toolchain_missing",
            reason=reason,
        )


class DecideFlowguardUse:
    name = "DecideFlowguardUse"
    reads = ("task_facts", "toolchain_failures")
    writes = ("task_facts", "trigger_decisions", "skipped_steps")
    input_description = "ToolchainStatus"
    output_description = "TriggerDecision"
    idempotency = "same task revision has one trigger decision"
    accepted_input_type = ToolchainStatus

    def apply(self, input_obj: ToolchainStatus, state: State) -> Iterable[FunctionResult]:
        task = input_obj.task
        state = state.with_task_fact(task)
        required = required_checks_for(task)
        if requires_flowguard(task) and not input_obj.connected:
            decision = TriggerDecision(
                task.task_id,
                task.revision,
                "blocked_missing_toolchain",
                (),
                "formal flowguard toolchain must be connected before model-first validation can count",
            )
            new_state = state.with_trigger_decision(decision).with_skipped_step(
                SkippedStep(task.task_id, task.revision, "flowguard_toolchain", decision.reason)
            )
            yield FunctionResult(
                decision,
                new_state,
                label="flowguard_blocked_missing_toolchain",
                reason=decision.reason,
            )
            return

        if requires_flowguard(task):
            decision = TriggerDecision(
                task.task_id,
                task.revision,
                "use_flowguard",
                required,
                "non-trivial product workflow requires executable model-first validation",
            )
            yield FunctionResult(
                decision,
                state.with_trigger_decision(decision),
                label="flowguard_required",
                reason=decision.reason,
            )
            return

        decision = TriggerDecision(
            task.task_id,
            task.revision,
            "skip_flowguard",
            (),
            "task is trivial or a review-only pass",
        )
        new_state = state.with_trigger_decision(decision).with_skipped_step(
            SkippedStep(task.task_id, task.revision, "flowguard_model", decision.reason)
        )
        yield FunctionResult(
            decision,
            new_state,
            label="flowguard_skipped_with_reason",
            reason=decision.reason,
        )


class BuildOrUpdateFlowguardModel:
    name = "BuildOrUpdateFlowguardModel"
    reads = ("models",)
    writes = ("models",)
    input_description = "TriggerDecision"
    output_description = "ModelPlan"
    idempotency = "same task revision has at most one model artifact"
    accepted_input_type = TriggerDecision

    def apply(self, input_obj: TriggerDecision, state: State) -> Iterable[FunctionResult]:
        key = input_obj.key
        if input_obj.action != "use_flowguard":
            yield FunctionResult(
                ModelPlan(input_obj.task_id, input_obj.revision, False, (), "model not required"),
                state,
                label="model_not_required",
                reason="flowguard was explicitly skipped with reason",
            )
            return

        already = _has_model(state, key)
        new_state = state.with_model(key)
        label = "model_reused" if already else "model_created"
        yield FunctionResult(
            ModelPlan(
                input_obj.task_id,
                input_obj.revision,
                True,
                input_obj.required_checks,
                "flowguard model is ready for this task revision",
            ),
            new_state,
            label=label,
            reason="model exists for the exact task revision",
        )


class RunRelevantChecks:
    name = "RunRelevantChecks"
    reads = ("checks", "counterexamples")
    writes = ("checks", "counterexamples")
    input_description = "ModelPlan"
    output_description = "CheckOutcome"
    idempotency = "same check is recorded once per task revision"
    accepted_input_type = ModelPlan

    def apply(self, input_obj: ModelPlan, state: State) -> Iterable[FunctionResult]:
        key = input_obj.key
        if not input_obj.model_ready:
            yield FunctionResult(
                CheckOutcome(input_obj.task_id, input_obj.revision, (), (), False, "no model checks required"),
                state,
                label="checks_not_required",
                reason="no model is required for this task",
            )
            return

        new_state = state
        status = "failed" if _fact_has_flag(state, key, "counterexample") else "passed"
        for check_name in input_obj.required_checks:
            new_state = new_state.with_check(key, check_name, status)
        has_counterexample = status == "failed"
        if has_counterexample:
            new_state = new_state.with_counterexample(key)
        yield FunctionResult(
            CheckOutcome(
                input_obj.task_id,
                input_obj.revision,
                input_obj.required_checks,
                input_obj.required_checks,
                has_counterexample,
                "all relevant checks ran" if not has_counterexample else "checks exposed a counterexample",
            ),
            new_state,
            label="checks_failed_with_counterexample" if has_counterexample else "checks_passed",
            reason="ran relevant executable flowguard checks",
        )


def _fact_has_flag(state: State, key: TaskKey, flag: str) -> bool:
    fact = state.fact_for(key)
    return bool(fact and flag in fact.risk_flags)


class GateProductionChange:
    name = "GateProductionChange"
    reads = ("checks", "counterexamples")
    writes = ("approvals",)
    input_description = "CheckOutcome"
    output_description = "ApprovalDecision"
    idempotency = "same task revision has one approval status"
    accepted_input_type = CheckOutcome

    def apply(self, input_obj: CheckOutcome, state: State) -> Iterable[FunctionResult]:
        key = input_obj.key
        fact = state.fact_for(key)
        if fact is None or not requires_flowguard(fact):
            approval = ApprovalDecision(input_obj.task_id, input_obj.revision, "approved", "no model gate required")
            yield FunctionResult(
                approval,
                state.with_approval(approval),
                label="production_approved_trivial",
                reason=approval.reason,
            )
            return
        if key in state.counterexamples:
            approval = ApprovalDecision(
                input_obj.task_id,
                input_obj.revision,
                "blocked",
                "counterexample must be resolved before production work",
            )
            yield FunctionResult(
                approval,
                state.with_approval(approval),
                label="production_blocked_counterexample",
                reason=approval.reason,
            )
            return
        required = set(required_checks_for(fact))
        observed = _checks_for(state, key)
        if not _has_model(state, key) or not required.issubset(observed):
            approval = ApprovalDecision(
                input_obj.task_id,
                input_obj.revision,
                "blocked",
                "formal flowguard model and required checks are missing",
            )
            yield FunctionResult(
                approval,
                state.with_approval(approval),
                label="production_blocked_missing_model_or_checks",
                reason=approval.reason,
            )
            return
        approval = ApprovalDecision(
            input_obj.task_id,
            input_obj.revision,
            "approved",
            "required model checks passed",
        )
        yield FunctionResult(
            approval,
            state.with_approval(approval),
            label="production_approved_after_checks",
            reason=approval.reason,
        )


class RecordAdoptionEvidence:
    name = "RecordAdoptionEvidence"
    reads = ("adoption_logs", "adoption_statuses")
    writes = ("adoption_logs", "adoption_statuses")
    input_description = "ApprovalDecision"
    output_description = "AdoptionOutcome"
    idempotency = "same task revision has at most one adoption log"
    accepted_input_type = ApprovalDecision

    def apply(self, input_obj: ApprovalDecision, state: State) -> Iterable[FunctionResult]:
        key = input_obj.key
        fact = state.fact_for(key)
        if fact and requires_flowguard(fact):
            status = "completed" if input_obj.status == "approved" else "blocked"
            yield FunctionResult(
                AdoptionOutcome(
                    input_obj.task_id,
                    input_obj.revision,
                    True,
                    status,
                    f"adoption log recorded as {status}",
                ),
                state.with_adoption_log(key, status),
                label="adoption_logged",
                reason=f"model-first usage leaves reviewable {status} evidence",
            )
            return
        yield FunctionResult(
            AdoptionOutcome(
                input_obj.task_id,
                input_obj.revision,
                False,
                "skipped_with_reason",
                "no adoption log required",
            ),
            state,
            label="adoption_log_not_required",
            reason="trivial or review-only task",
        )


class BrokenTriggerSkipsArchitecture(DecideFlowguardUse):
    name = "DecideFlowguardUse"

    def apply(self, input_obj: ToolchainStatus, state: State) -> Iterable[FunctionResult]:
        task = input_obj.task
        state = state.with_task_fact(task)
        decision = TriggerDecision(task.task_id, task.revision, "skip_flowguard", (), "broken trigger skipped")
        yield FunctionResult(
            decision,
            state.with_trigger_decision(decision),
            label="flowguard_skipped_broken",
            reason="broken trigger skips model-first validation",
        )


class BrokenVerifyToolchainAllowsSubstitute(VerifyFlowguardToolchain):
    name = "VerifyFlowguardToolchain"

    def apply(self, input_obj: ProductTask, state: State) -> Iterable[FunctionResult]:
        state = state.with_task_fact(input_obj)
        yield FunctionResult(
            ToolchainStatus(input_obj, True, "broken preflight accepted an ad-hoc substitute"),
            state.with_toolchain_preflight(input_obj.key, True, "broken substitute accepted"),
            label="toolchain_substitute_used",
            reason="broken preflight hides missing formal flowguard package",
        )


class BrokenBuildModelIgnoresRevision(BuildOrUpdateFlowguardModel):
    name = "BuildOrUpdateFlowguardModel"

    def apply(self, input_obj: TriggerDecision, state: State) -> Iterable[FunctionResult]:
        if input_obj.action != "use_flowguard":
            yield from super().apply(input_obj, state)
            return
        stale_key = (input_obj.task_id, 1)
        new_state = state.with_model(stale_key)
        yield FunctionResult(
            ModelPlan(input_obj.task_id, input_obj.revision, True, input_obj.required_checks, "stale model reused"),
            new_state,
            label="model_stale_revision_reused",
            reason="broken block reuses revision 1 model for later architecture change",
        )


class BrokenRunChecksMissingConformance(RunRelevantChecks):
    name = "RunRelevantChecks"

    def apply(self, input_obj: ModelPlan, state: State) -> Iterable[FunctionResult]:
        if not input_obj.model_ready:
            yield from super().apply(input_obj, state)
            return
        key = input_obj.key
        checks = tuple(check for check in input_obj.required_checks if check != "conformance")
        new_state = state
        for check_name in checks:
            new_state = new_state.with_check(key, check_name, "passed")
        yield FunctionResult(
            CheckOutcome(input_obj.task_id, input_obj.revision, input_obj.required_checks, checks, False, "missing conformance"),
            new_state,
            label="checks_missing_conformance",
            reason="broken block omits conformance replay",
        )


class BrokenRunChecksDailyReviewOnly(RunRelevantChecks):
    name = "RunRelevantChecks"

    def apply(self, input_obj: ModelPlan, state: State) -> Iterable[FunctionResult]:
        key = input_obj.key
        new_state = state.with_daily_review(key).with_check(key, "daily_review", "passed")
        yield FunctionResult(
            CheckOutcome(input_obj.task_id, input_obj.revision, input_obj.required_checks, ("daily_review",), False, "daily review only"),
            new_state,
            label="daily_review_used_as_validation",
            reason="broken block treats daily review as executable validation",
        )


class BrokenGateApprovesCounterexample(GateProductionChange):
    name = "GateProductionChange"

    def apply(self, input_obj: CheckOutcome, state: State) -> Iterable[FunctionResult]:
        approval = ApprovalDecision(input_obj.task_id, input_obj.revision, "approved", "broken approval ignores counterexample")
        yield FunctionResult(
            approval,
            state.with_approval(approval),
            label="production_approved_with_counterexample",
            reason=approval.reason,
        )


class BrokenRecordNoAdoptionLog(RecordAdoptionEvidence):
    name = "RecordAdoptionEvidence"

    def apply(self, input_obj: ApprovalDecision, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(
            AdoptionOutcome(input_obj.task_id, input_obj.revision, False, "failed", "broken missing adoption log"),
            state,
            label="adoption_log_missing",
            reason="broken block does not record real usage evidence",
        )


class BrokenRecordInProgressAsFinal(RecordAdoptionEvidence):
    name = "RecordAdoptionEvidence"

    def apply(self, input_obj: ApprovalDecision, state: State) -> Iterable[FunctionResult]:
        key = input_obj.key
        fact = state.fact_for(key)
        if fact and requires_flowguard(fact):
            yield FunctionResult(
                AdoptionOutcome(
                    input_obj.task_id,
                    input_obj.revision,
                    True,
                    "in_progress",
                    "broken final report leaves adoption status in_progress",
                ),
                state.with_adoption_log(key, "in_progress"),
                label="adoption_logged_in_progress",
                reason="broken block records unfinished adoption evidence as if the task were ready",
            )
            return
        yield from super().apply(input_obj, state)


def nontrivial_task_must_trigger_flowguard_or_toolchain_block() -> Invariant:
    def predicate(state: State, _trace: object) -> InvariantResult:
        bad = []
        for key in _nontrivial_keys(state):
            decisions = [decision for decision in state.trigger_decisions if decision.key == key]
            if not any(decision.action in {"use_flowguard", "blocked_missing_toolchain"} for decision in decisions):
                bad.append(key)
        if bad:
            return InvariantResult.fail(f"non-trivial task revisions were not routed to flowguard or toolchain block: {tuple(bad)!r}")
        return InvariantResult.pass_()

    return Invariant(
        "nontrivial_task_must_trigger_flowguard_or_toolchain_block",
        "Non-trivial work must either use flowguard or explicitly block on missing formal toolchain.",
        predicate,
    )


def model_artifact_must_match_task_revision() -> Invariant:
    def predicate(state: State, _trace: object) -> InvariantResult:
        bad = tuple(
            decision.key
            for decision in state.trigger_decisions
            if decision.action == "use_flowguard" and not _has_model(state, decision.key)
        )
        if bad:
            return InvariantResult.fail(f"flowguard use decisions lack exact model artifact: {bad!r}")
        return InvariantResult.pass_()

    return Invariant(
        "model_artifact_must_match_task_revision",
        "A model-first task must create or reuse the model for the exact task revision.",
        predicate,
    )


def formal_toolchain_required_for_full_adoption() -> Invariant:
    def predicate(state: State, _trace: object) -> InvariantResult:
        bad = tuple(
            fact.key
            for fact in state.task_facts
            if "toolchain_unavailable" in fact.risk_flags and fact.key not in state.toolchain_failures
        )
        if bad:
            return InvariantResult.fail(f"missing formal flowguard toolchain was hidden by substitute implementation: {bad!r}")
        return InvariantResult.pass_()

    return Invariant(
        "formal_toolchain_required_for_full_adoption",
        "A target repository cannot claim full flowguard adoption when the formal package is unavailable.",
        predicate,
    )


def flowguard_model_required_before_approval() -> Invariant:
    def predicate(state: State, _trace: object) -> InvariantResult:
        missing = []
        for key in _approved_keys(state):
            fact = state.fact_for(key)
            if fact and requires_flowguard(fact) and not _has_model(state, key):
                missing.append(key)
        if missing:
            return InvariantResult.fail(f"approved task revisions lack flowguard model: {tuple(missing)!r}")
        return InvariantResult.pass_()

    return Invariant(
        "flowguard_model_required_before_approval",
        "Non-trivial production work must have a model for the exact task revision.",
        predicate,
    )


def required_checks_must_run_before_approval() -> Invariant:
    def predicate(state: State, _trace: object) -> InvariantResult:
        missing = []
        triggered_keys = tuple(
            decision.key for decision in state.trigger_decisions if decision.action == "use_flowguard"
        )
        keys = tuple(dict.fromkeys(_approved_keys(state) + triggered_keys))
        for key in keys:
            fact = state.fact_for(key)
            if not fact or not requires_flowguard(fact):
                continue
            required = set(required_checks_for(fact))
            observed = _checks_run_for(state, key)
            absent = tuple(sorted(required - observed))
            if absent:
                missing.append((key, absent))
        if missing:
            return InvariantResult.fail(f"model-first task revisions miss required checks: {tuple(missing)!r}")
        return InvariantResult.pass_()

    return Invariant(
        "required_checks_must_run_before_approval",
        "Model-first work must run every relevant executable check before it can count as validated.",
        predicate,
    )


def adoption_log_required_for_model_first_task() -> Invariant:
    def predicate(state: State, _trace: object) -> InvariantResult:
        missing = tuple(key for key in _nontrivial_keys(state) if key not in state.adoption_logs)
        if missing:
            return InvariantResult.fail(f"non-trivial task revisions lack adoption log: {missing!r}")
        return InvariantResult.pass_()

    return Invariant(
        "adoption_log_required_for_model_first_task",
        "Real model-first usage must leave adoption evidence.",
        predicate,
    )


def adoption_log_status_must_match_task_outcome() -> Invariant:
    allowed = {"in_progress", "completed", "blocked", "skipped_with_reason", "failed"}

    def predicate(state: State, _trace: object) -> InvariantResult:
        bad = []
        for key in _nontrivial_keys(state):
            if key not in state.adoption_logs:
                continue
            status = _adoption_status_for(state, key)
            approval = _approval_for(state, key)
            if status not in allowed:
                bad.append((key, status, "unknown adoption status"))
                continue
            if approval and approval.status == "approved" and status != "completed":
                bad.append((key, status, "approved work must have completed adoption evidence"))
            if approval and approval.status == "blocked" and status not in {"blocked", "failed"}:
                bad.append((key, status, "blocked work must not be recorded as completed or in-progress"))
        if bad:
            return InvariantResult.fail(f"adoption log status mismatch: {tuple(bad)!r}")
        return InvariantResult.pass_()

    return Invariant(
        "adoption_log_status_must_match_task_outcome",
        "Adoption status must distinguish in-progress, completed, blocked, skipped, and failed evidence.",
        predicate,
    )


def unresolved_counterexample_blocks_approval() -> Invariant:
    def predicate(state: State, _trace: object) -> InvariantResult:
        bad = tuple(key for key in _approved_keys(state) if key in state.counterexamples)
        if bad:
            return InvariantResult.fail(f"counterexample task revisions were approved: {bad!r}")
        return InvariantResult.pass_()

    return Invariant(
        "unresolved_counterexample_blocks_approval",
        "Production work cannot be approved while a counterexample is unresolved.",
        predicate,
    )


def daily_review_cannot_replace_executable_checks() -> Invariant:
    def predicate(state: State, _trace: object) -> InvariantResult:
        bad = []
        for key in _nontrivial_keys(state):
            fact = state.fact_for(key)
            if not fact or not requires_flowguard(fact):
                continue
            observed = _checks_run_for(state, key)
            required = set(required_checks_for(fact))
            if "daily_review" in observed and not required.issubset(observed):
                bad.append(key)
        if bad:
            return InvariantResult.fail(f"daily review used as validation for: {tuple(bad)!r}")
        return InvariantResult.pass_()

    return Invariant(
        "daily_review_cannot_replace_executable_checks",
        "Daily review is an observation loop, not a substitute for model checks.",
        predicate,
    )


def no_duplicate_adoption_log_per_task_revision() -> Invariant:
    def predicate(state: State, _trace: object) -> InvariantResult:
        duplicates = tuple(sorted({key for key in state.adoption_logs if state.adoption_logs.count(key) > 1}))
        if duplicates:
            return InvariantResult.fail(f"duplicate adoption logs: {duplicates!r}")
        return InvariantResult.pass_()

    return Invariant(
        "no_duplicate_adoption_log_per_task_revision",
        "Repeated inputs should not duplicate adoption side effects.",
        predicate,
    )


INVARIANTS = (
    nontrivial_task_must_trigger_flowguard_or_toolchain_block(),
    model_artifact_must_match_task_revision(),
    formal_toolchain_required_for_full_adoption(),
    flowguard_model_required_before_approval(),
    required_checks_must_run_before_approval(),
    adoption_log_required_for_model_first_task(),
    adoption_log_status_must_match_task_outcome(),
    unresolved_counterexample_blocks_approval(),
    daily_review_cannot_replace_executable_checks(),
    no_duplicate_adoption_log_per_task_revision(),
)


def build_workflow(
    *,
    toolchain_block: object | None = None,
    trigger_block: object | None = None,
    model_block: object | None = None,
    check_block: object | None = None,
    gate_block: object | None = None,
    adoption_block: object | None = None,
) -> Workflow:
    return Workflow(
        (
            toolchain_block or VerifyFlowguardToolchain(),
            trigger_block or DecideFlowguardUse(),
            model_block or BuildOrUpdateFlowguardModel(),
            check_block or RunRelevantChecks(),
            gate_block or GateProductionChange(),
            adoption_block or RecordAdoptionEvidence(),
        ),
        name="flowguard_self_review",
    )


def _expect_ok(summary: str, labels: Sequence[str] = ()) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="ok",
        required_trace_labels=tuple(labels),
        summary=summary,
    )


def _expect_violation(summary: str, names: Sequence[str]) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="violation",
        expected_violation_names=tuple(names),
        summary=summary,
    )


def _all_final_states_have_check(check_name: str) -> object:
    def check(run: ScenarioRun) -> OracleCheckResult:
        bad = [
            state
            for state in run.final_states
            if any(requires_flowguard(fact) for fact in state.task_facts)
            and not any(record.check_name == check_name for record in state.checks)
        ]
        return OracleCheckResult(
            ok=not bad,
            message=f"missing check {check_name}",
            evidence=(f"{check_name} check observed when required",),
            violation_name=f"missing_{check_name}_check",
        )

    return check


TASK_NEW_ARCH = ProductTask(
    "flowguard-new-project",
    1,
    "new_project",
    ("architecture", "module_boundary", "production_change"),
)
TASK_RETRY_DEDUP = ProductTask(
    "flowguard-retry-dedup",
    1,
    "stateful_workflow",
    ("retry", "dedup", "idempotency", "side_effect"),
)
TASK_MODULE_PRODUCTION = ProductTask(
    "flowguard-conformance",
    1,
    "major_architecture",
    ("module_boundary", "production_change"),
)
TASK_REVISION_1 = ProductTask(
    "flowguard-major-redesign",
    1,
    "major_architecture",
    ("architecture", "cache", "production_change"),
)
TASK_REVISION_2 = ProductTask(
    "flowguard-major-redesign",
    2,
    "major_architecture",
    ("architecture", "cache", "production_change"),
)
TASK_COUNTEREXAMPLE = ProductTask(
    "flowguard-counterexample",
    1,
    "major_architecture",
    ("architecture", "counterexample", "production_change"),
)
TASK_TOOLCHAIN_MISSING = ProductTask(
    "flowguard-toolchain-missing",
    1,
    "new_project",
    ("architecture", "production_change", "toolchain_unavailable"),
)
TASK_TRIVIAL_DOC = ProductTask("flowguard-doc-copyedit", 1, "trivial_docs", (), False)


def scenario(
    name: str,
    description: str,
    sequence: Sequence[ProductTask],
    expected: ScenarioExpectation,
    *,
    workflow: Workflow | None = None,
) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        initial_state=State(),
        external_input_sequence=tuple(sequence),
        expected=expected,
        workflow=workflow or build_workflow(),
        invariants=INVARIANTS,
    )


def self_review_scenarios() -> tuple[Scenario, ...]:
    return (
        scenario(
            "FGS01_new_project_architecture_requires_model",
            "A new non-trivial product architecture should trigger model-first validation.",
            (TASK_NEW_ARCH,),
            ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("flowguard_required", "model_created", "checks_passed", "adoption_logged"),
                custom_checks=(_all_final_states_have_check("contract"),),
                summary="OK; new architecture uses model, checks, and adoption log",
            ),
        ),
        scenario(
            "FGS02_retry_dedup_workflow_runs_progress_checks",
            "Retry/dedup/idempotency work should run scenario, loop, and progress checks.",
            (TASK_RETRY_DEDUP,),
            ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("flowguard_required", "checks_passed", "adoption_logged"),
                custom_checks=(
                    _all_final_states_have_check("scenario"),
                    _all_final_states_have_check("loop"),
                    _all_final_states_have_check("progress"),
                ),
                summary="OK; retry/dedup work runs relevant checks",
            ),
        ),
        scenario(
            "FGS03_production_change_runs_conformance",
            "Production-facing architecture change should run conformance replay.",
            (TASK_MODULE_PRODUCTION,),
            ScenarioExpectation(
                expected_status="ok",
                required_trace_labels=("production_approved_after_checks", "adoption_logged"),
                custom_checks=(_all_final_states_have_check("conformance"),),
                summary="OK; production change includes conformance replay",
            ),
        ),
        scenario(
            "FGS04_architecture_revision_reruns_model_checks",
            "A second major revision must return to the model and rerun checks.",
            (TASK_REVISION_1, TASK_REVISION_2),
            _expect_ok(
                "OK; revision 2 has its own model and checks",
                labels=("model_created", "checks_passed", "adoption_logged"),
            ),
        ),
        scenario(
            "FGS05_counterexample_blocks_production",
            "Counterexample should block production approval while still logging adoption evidence.",
            (TASK_COUNTEREXAMPLE,),
            _expect_ok(
                "OK; counterexample blocks production instead of being ignored",
                labels=("checks_failed_with_counterexample", "production_blocked_counterexample", "adoption_logged"),
            ),
        ),
        scenario(
            "FGS06_trivial_docs_can_skip_with_reason",
            "Trivial copy edits can skip flowguard if the skip is explicit.",
            (TASK_TRIVIAL_DOC,),
            _expect_ok(
                "OK; trivial task skips model with recorded reason",
                labels=("flowguard_skipped_with_reason", "production_approved_trivial"),
            ),
        ),
        scenario(
            "FGS07_missing_toolchain_blocks_full_adoption",
            "A target repository cannot use a temporary mini-framework as full flowguard adoption.",
            (TASK_TOOLCHAIN_MISSING,),
            _expect_ok(
                "OK; missing formal toolchain is explicit and blocks production approval",
                labels=(
                    "toolchain_missing",
                    "flowguard_blocked_missing_toolchain",
                    "production_blocked_missing_model_or_checks",
                    "adoption_logged",
                ),
            ),
        ),
        scenario(
            "FGB01_broken_trigger_skips_architecture",
            "Broken trigger skips flowguard for a major architecture task.",
            (TASK_NEW_ARCH,),
            _expect_violation(
                "VIOLATION nontrivial_task_must_trigger_flowguard_or_toolchain_block",
                ("nontrivial_task_must_trigger_flowguard_or_toolchain_block",),
            ),
            workflow=build_workflow(trigger_block=BrokenTriggerSkipsArchitecture()),
        ),
        scenario(
            "FGB02_broken_missing_conformance",
            "Broken check runner omits conformance replay for production-facing change.",
            (TASK_MODULE_PRODUCTION,),
            _expect_violation(
                "VIOLATION required_checks_must_run_before_approval",
                ("required_checks_must_run_before_approval",),
            ),
            workflow=build_workflow(check_block=BrokenRunChecksMissingConformance()),
        ),
        scenario(
            "FGB03_broken_missing_adoption_log",
            "Broken adoption recorder loses real usage evidence.",
            (TASK_RETRY_DEDUP,),
            _expect_violation(
                "VIOLATION adoption_log_required_for_model_first_task",
                ("adoption_log_required_for_model_first_task",),
            ),
            workflow=build_workflow(adoption_block=BrokenRecordNoAdoptionLog()),
        ),
        scenario(
            "FGB04_broken_no_rerun_for_architecture_revision",
            "Broken model builder reuses stale model across a major revision.",
            (TASK_REVISION_1, TASK_REVISION_2),
            _expect_violation(
                "VIOLATION model_artifact_must_match_task_revision",
                ("model_artifact_must_match_task_revision",),
            ),
            workflow=build_workflow(model_block=BrokenBuildModelIgnoresRevision()),
        ),
        scenario(
            "FGB05_broken_approves_counterexample",
            "Broken gate approves production despite unresolved counterexample.",
            (TASK_COUNTEREXAMPLE,),
            _expect_violation(
                "VIOLATION unresolved_counterexample_blocks_approval",
                ("unresolved_counterexample_blocks_approval",),
            ),
            workflow=build_workflow(gate_block=BrokenGateApprovesCounterexample()),
        ),
        scenario(
            "FGB06_broken_daily_review_replaces_checks",
            "Broken runner treats daily adoption review as executable validation.",
            (TASK_MODULE_PRODUCTION,),
            _expect_violation(
                "VIOLATION daily_review_cannot_replace_executable_checks",
                (
                    "required_checks_must_run_before_approval",
                    "daily_review_cannot_replace_executable_checks",
                ),
            ),
            workflow=build_workflow(check_block=BrokenRunChecksDailyReviewOnly()),
        ),
        scenario(
            "FGB07_broken_toolchain_substitute_claims_full_adoption",
            "Broken preflight accepts an ad-hoc mini-framework when the formal package is unavailable.",
            (TASK_TOOLCHAIN_MISSING,),
            _expect_violation(
                "VIOLATION formal_toolchain_required_for_full_adoption",
                ("formal_toolchain_required_for_full_adoption",),
            ),
            workflow=build_workflow(toolchain_block=BrokenVerifyToolchainAllowsSubstitute()),
        ),
        scenario(
            "FGB08_broken_in_progress_adoption_treated_as_final",
            "Broken adoption recorder leaves an approved model-first task marked in_progress.",
            (TASK_MODULE_PRODUCTION,),
            _expect_violation(
                "VIOLATION adoption_log_status_must_match_task_outcome",
                ("adoption_log_status_must_match_task_outcome",),
            ),
            workflow=build_workflow(adoption_block=BrokenRecordInProgressAsFinal()),
        ),
    )


def run_self_review():
    from flowguard.review import review_scenarios

    return review_scenarios(self_review_scenarios())


__all__ = [
    "INVARIANTS",
    "ProductTask",
    "State",
    "build_workflow",
    "run_self_review",
    "self_review_scenarios",
]

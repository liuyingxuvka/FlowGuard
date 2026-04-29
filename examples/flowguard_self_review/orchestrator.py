"""Mock production orchestrators for flowguard self-review conformance."""

from __future__ import annotations

from .model import (
    AdoptionOutcome,
    ApprovalDecision,
    CheckOutcome,
    CheckRecord,
    ModelPlan,
    ProductTask,
    SkippedStep,
    State,
    ToolchainStatus,
    TriggerDecision,
    required_checks_for,
    requires_flowguard,
)


def _has_model(state: State, key: tuple[str, int]) -> bool:
    return any(model.key == key for model in state.models)


def _checks_for(state: State, key: tuple[str, int]) -> set[str]:
    return {
        check.check_name
        for check in state.checks
        if check.key == key and check.status == "passed"
    }


def _fact_has_flag(state: State, key: tuple[str, int], flag: str) -> bool:
    fact = state.fact_for(key)
    return bool(fact and flag in fact.risk_flags)


class CorrectFlowguardOrchestrator:
    """Small production-like orchestrator that should conform to the model."""

    def __init__(self) -> None:
        self.state = State()
        self.last_output = None
        self.last_label = ""
        self.last_reason = ""

    def reset(self, initial_state: State) -> None:
        self.state = initial_state
        self.last_output = None
        self.last_label = ""
        self.last_reason = ""

    def _record(self, output, label: str, reason: str) -> None:
        self.last_output = output
        self.last_label = label
        self.last_reason = reason

    def verify_flowguard_toolchain(self, task: ProductTask) -> ToolchainStatus:
        connected = "toolchain_unavailable" not in task.risk_flags
        reason = (
            "formal flowguard package import preflight passed"
            if connected
            else "formal flowguard package is not importable; do not replace it with an ad-hoc mini-framework"
        )
        self.state = self.state.with_task_fact(task).with_toolchain_preflight(
            task.key,
            connected,
            reason,
        )
        output = ToolchainStatus(task, connected, reason)
        self._record(output, "toolchain_available" if connected else "toolchain_missing", reason)
        return output

    def decide_flowguard_use(self, status: ToolchainStatus) -> TriggerDecision:
        task = status.task
        self.state = self.state.with_task_fact(task)
        required = required_checks_for(task)
        if requires_flowguard(task) and not status.connected:
            decision = TriggerDecision(
                task.task_id,
                task.revision,
                "blocked_missing_toolchain",
                (),
                "formal flowguard toolchain must be connected before model-first validation can count",
            )
            self.state = self.state.with_trigger_decision(decision).with_skipped_step(
                SkippedStep(task.task_id, task.revision, "flowguard_toolchain", decision.reason)
            )
            self._record(decision, "flowguard_blocked_missing_toolchain", decision.reason)
            return decision

        if requires_flowguard(task):
            decision = TriggerDecision(
                task.task_id,
                task.revision,
                "use_flowguard",
                required,
                "non-trivial product workflow requires executable model-first validation",
            )
            self.state = self.state.with_trigger_decision(decision)
            self._record(decision, "flowguard_required", decision.reason)
            return decision

        decision = TriggerDecision(
            task.task_id,
            task.revision,
            "skip_flowguard",
            (),
            "task is trivial or a review-only pass",
        )
        self.state = self.state.with_trigger_decision(decision).with_skipped_step(
            SkippedStep(task.task_id, task.revision, "flowguard_model", decision.reason)
        )
        self._record(decision, "flowguard_skipped_with_reason", decision.reason)
        return decision

    def build_or_update_flowguard_model(self, decision: TriggerDecision) -> ModelPlan:
        key = decision.key
        if decision.action != "use_flowguard":
            output = ModelPlan(decision.task_id, decision.revision, False, (), "model not required")
            self._record(output, "model_not_required", "flowguard was explicitly skipped with reason")
            return output

        already = _has_model(self.state, key)
        self.state = self.state.with_model(key)
        output = ModelPlan(
            decision.task_id,
            decision.revision,
            True,
            decision.required_checks,
            "flowguard model is ready for this task revision",
        )
        self._record(
            output,
            "model_reused" if already else "model_created",
            "model exists for the exact task revision",
        )
        return output

    def run_relevant_checks(self, plan: ModelPlan) -> CheckOutcome:
        key = plan.key
        if not plan.model_ready:
            output = CheckOutcome(plan.task_id, plan.revision, (), (), False, "no model checks required")
            self._record(output, "checks_not_required", "no model is required for this task")
            return output

        status = "failed" if _fact_has_flag(self.state, key, "counterexample") else "passed"
        for check_name in plan.required_checks:
            self.state = self.state.with_check(key, check_name, status)
        has_counterexample = status == "failed"
        if has_counterexample:
            self.state = self.state.with_counterexample(key)
        output = CheckOutcome(
            plan.task_id,
            plan.revision,
            plan.required_checks,
            plan.required_checks,
            has_counterexample,
            "all relevant checks ran" if not has_counterexample else "checks exposed a counterexample",
        )
        self._record(
            output,
            "checks_failed_with_counterexample" if has_counterexample else "checks_passed",
            "ran relevant executable flowguard checks",
        )
        return output

    def gate_production_change(self, outcome: CheckOutcome) -> ApprovalDecision:
        key = outcome.key
        fact = self.state.fact_for(key)
        if fact is None or not requires_flowguard(fact):
            approval = ApprovalDecision(outcome.task_id, outcome.revision, "approved", "no model gate required")
            self.state = self.state.with_approval(approval)
            self._record(approval, "production_approved_trivial", approval.reason)
            return approval

        if key in self.state.counterexamples:
            approval = ApprovalDecision(
                outcome.task_id,
                outcome.revision,
                "blocked",
                "counterexample must be resolved before production work",
            )
            self.state = self.state.with_approval(approval)
            self._record(approval, "production_blocked_counterexample", approval.reason)
            return approval

        required = set(required_checks_for(fact))
        observed = _checks_for(self.state, key)
        if not _has_model(self.state, key) or not required.issubset(observed):
            approval = ApprovalDecision(
                outcome.task_id,
                outcome.revision,
                "blocked",
                "formal flowguard model and required checks are missing",
            )
            self.state = self.state.with_approval(approval)
            self._record(approval, "production_blocked_missing_model_or_checks", approval.reason)
            return approval

        approval = ApprovalDecision(outcome.task_id, outcome.revision, "approved", "required model checks passed")
        self.state = self.state.with_approval(approval)
        self._record(approval, "production_approved_after_checks", approval.reason)
        return approval

    def record_adoption_evidence(self, approval: ApprovalDecision) -> AdoptionOutcome:
        key = approval.key
        fact = self.state.fact_for(key)
        if fact and requires_flowguard(fact):
            status = "completed" if approval.status == "approved" else "blocked"
            self.state = self.state.with_adoption_log(key, status)
            output = AdoptionOutcome(
                approval.task_id,
                approval.revision,
                True,
                status,
                f"adoption log recorded as {status}",
            )
            self._record(output, "adoption_logged", f"model-first usage leaves reviewable {status} evidence")
            return output
        output = AdoptionOutcome(
            approval.task_id,
            approval.revision,
            False,
            "skipped_with_reason",
            "no adoption log required",
        )
        self._record(output, "adoption_log_not_required", "trivial or review-only task")
        return output

    def project_state(self) -> State:
        return self.state


class BrokenNoConformanceOrchestrator(CorrectFlowguardOrchestrator):
    """Broken orchestrator that skips conformance checks."""

    def run_relevant_checks(self, plan: ModelPlan) -> CheckOutcome:
        if not plan.model_ready:
            return super().run_relevant_checks(plan)
        key = plan.key
        checks = tuple(check for check in plan.required_checks if check != "conformance")
        for check_name in checks:
            self.state = self.state.with_check(key, check_name, "passed")
        output = CheckOutcome(plan.task_id, plan.revision, plan.required_checks, checks, False, "missing conformance")
        self._record(output, "checks_missing_conformance", "broken orchestrator omits conformance replay")
        return output


class BrokenToolchainSubstituteOrchestrator(CorrectFlowguardOrchestrator):
    """Broken orchestrator that hides missing formal package with a substitute."""

    def verify_flowguard_toolchain(self, task: ProductTask) -> ToolchainStatus:
        self.state = self.state.with_task_fact(task).with_toolchain_preflight(
            task.key,
            True,
            "broken substitute accepted",
        )
        output = ToolchainStatus(task, True, "broken preflight accepted an ad-hoc substitute")
        self._record(output, "toolchain_substitute_used", "broken preflight hides missing formal flowguard package")
        return output


__all__ = [
    "BrokenNoConformanceOrchestrator",
    "BrokenToolchainSubstituteOrchestrator",
    "CorrectFlowguardOrchestrator",
]

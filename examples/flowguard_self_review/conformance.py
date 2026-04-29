"""Conformance replay for flowguard's own adoption workflow."""

from __future__ import annotations

from typing import Iterable, Sequence

from flowguard import ConformanceReport, ReplayObservation, Trace, TraceStep, replay_trace
from flowguard.review import review_scenario

from .model import (
    ApprovalDecision,
    CheckOutcome,
    ModelPlan,
    ProductTask,
    ToolchainStatus,
    TriggerDecision,
    self_review_scenarios,
)
from .orchestrator import CorrectFlowguardOrchestrator


class FlowguardSelfReviewReplayAdapter:
    """Map abstract self-review trace steps to a production-like orchestrator."""

    def __init__(self, orchestrator: CorrectFlowguardOrchestrator) -> None:
        self.orchestrator = orchestrator

    def reset(self, initial_state) -> None:
        self.orchestrator.reset(initial_state)

    def apply_step(self, step: TraceStep) -> ReplayObservation:
        if step.function_name == "VerifyFlowguardToolchain":
            if not isinstance(step.function_input, ProductTask):
                raise TypeError("VerifyFlowguardToolchain expects ProductTask")
            self.orchestrator.verify_flowguard_toolchain(step.function_input)
        elif step.function_name == "DecideFlowguardUse":
            if not isinstance(step.function_input, ToolchainStatus):
                raise TypeError("DecideFlowguardUse expects ToolchainStatus")
            self.orchestrator.decide_flowguard_use(step.function_input)
        elif step.function_name == "BuildOrUpdateFlowguardModel":
            if not isinstance(step.function_input, TriggerDecision):
                raise TypeError("BuildOrUpdateFlowguardModel expects TriggerDecision")
            self.orchestrator.build_or_update_flowguard_model(step.function_input)
        elif step.function_name == "RunRelevantChecks":
            if not isinstance(step.function_input, ModelPlan):
                raise TypeError("RunRelevantChecks expects ModelPlan")
            self.orchestrator.run_relevant_checks(step.function_input)
        elif step.function_name == "GateProductionChange":
            if not isinstance(step.function_input, CheckOutcome):
                raise TypeError("GateProductionChange expects CheckOutcome")
            self.orchestrator.gate_production_change(step.function_input)
        elif step.function_name == "RecordAdoptionEvidence":
            if not isinstance(step.function_input, ApprovalDecision):
                raise TypeError("RecordAdoptionEvidence expects ApprovalDecision")
            self.orchestrator.record_adoption_evidence(step.function_input)
        else:
            raise ValueError(f"unsupported self-review step: {step.function_name}")

        return ReplayObservation(
            function_name=step.function_name,
            observed_output=self.observe_output(),
            observed_state=self.observe_state(),
            label=self.orchestrator.last_label,
            reason=self.orchestrator.last_reason,
        )

    def observe_state(self):
        return self.orchestrator.project_state()

    def observe_output(self):
        return self.orchestrator.last_output


def _scenario_by_name(name: str):
    for scenario in self_review_scenarios():
        if scenario.name == name:
            return scenario
    raise KeyError(name)


def trace_for_self_review_scenario(name: str) -> Trace:
    result = review_scenario(_scenario_by_name(name))
    if result.status != "pass":
        raise RuntimeError(result.scenario_run.model_report.format_text() if result.scenario_run else result.status)
    if result.scenario_run is None or not result.scenario_run.traces:
        raise RuntimeError(f"scenario {name!r} produced no traces")
    return result.scenario_run.traces[0]


def generate_self_review_representative_traces() -> tuple[Trace, ...]:
    """Select traces that exercise conformance, missing toolchain, and revision paths."""

    names = (
        "FGS03_production_change_runs_conformance",
        "FGS04_architecture_revision_reruns_model_checks",
        "FGS07_missing_toolchain_blocks_full_adoption",
    )
    return tuple(trace_for_self_review_scenario(name) for name in names)


def replay_self_review_trace(
    trace: Trace,
    orchestrator: CorrectFlowguardOrchestrator,
) -> ConformanceReport:
    return replay_trace(
        trace=trace,
        adapter=FlowguardSelfReviewReplayAdapter(orchestrator),
    )


def replay_self_review_traces(
    traces: Iterable[Trace],
    orchestrator: CorrectFlowguardOrchestrator,
) -> tuple[ConformanceReport, ...]:
    return tuple(replay_self_review_trace(trace, orchestrator) for trace in traces)


def all_reports_ok(reports: Sequence[ConformanceReport]) -> bool:
    return all(report.ok for report in reports)


__all__ = [
    "FlowguardSelfReviewReplayAdapter",
    "all_reports_ok",
    "generate_self_review_representative_traces",
    "replay_self_review_trace",
    "replay_self_review_traces",
    "trace_for_self_review_scenario",
]

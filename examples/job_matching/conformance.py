"""Conformance replay adapter for the job-matching example."""

from __future__ import annotations

from typing import Iterable, Sequence

from flowguard import ConformanceReport, ReplayObservation, Trace, TraceStep, replay_trace

from .model import (
    Decision,
    INVARIANTS,
    Job,
    RecordResult,
    ScoredJob,
    check_job_matching_model,
)
from .production import CorrectJobMatchingSystem


class JobMatchingReplayAdapter:
    """Map abstract job-matching trace steps to production system calls."""

    def __init__(self, system: CorrectJobMatchingSystem) -> None:
        self.system = system

    def reset(self, initial_state) -> None:
        self.system.reset(initial_state)

    def apply_step(self, step: TraceStep) -> ReplayObservation:
        if step.function_name != "ScoreJob" and step.function_name != "RecordScoredJob" and step.function_name != "DecideNextAction":
            raise ValueError(f"unsupported function step: {step.function_name}")

        if step.function_name == "ScoreJob":
            assert isinstance(step.function_input, Job)
            expected_bucket = None
            if isinstance(step.function_output, ScoredJob):
                expected_bucket = step.function_output.score_bucket
            self.system.score_job(step.function_input, expected_score_bucket=expected_bucket)
        elif step.function_name == "RecordScoredJob":
            assert isinstance(step.function_input, ScoredJob)
            self.system.record_scored_job(step.function_input)
        elif step.function_name == "DecideNextAction":
            assert isinstance(step.function_input, RecordResult)
            expected_action = None
            if isinstance(step.function_output, Decision):
                expected_action = step.function_output.action
            self.system.decide_next_action(step.function_input, expected_action=expected_action)

        return ReplayObservation(
            function_name=step.function_name,
            observed_output=self.observe_output(),
            observed_state=self.observe_state(),
            label=self.system.last_label,
            reason=self.system.last_reason,
        )

    def observe_state(self):
        return self.system.project_state()

    def observe_output(self):
        return self.system.last_output


def has_repeated_external_input(trace: Trace) -> bool:
    return len(trace.external_inputs) != len(set(trace.external_inputs))


def select_representative_traces(traces: Sequence[Trace]) -> tuple[Trace, ...]:
    selected: list[Trace] = []

    requirements = (
        lambda trace: has_repeated_external_input(trace)
        and trace.has_label("record_added")
        and trace.has_label("record_already_exists"),
        lambda trace: trace.has_label("record_skipped"),
        lambda trace: trace.has_label("decision_apply"),
    )

    for requirement in requirements:
        for trace in traces:
            if requirement(trace) and trace not in selected:
                selected.append(trace)
                break

    return tuple(selected)


def generate_representative_traces() -> tuple[Trace, ...]:
    report = check_job_matching_model(max_sequence_length=2)
    if not report.ok:
        raise RuntimeError(report.format_text())
    return select_representative_traces(report.traces)


def replay_job_matching_trace(trace: Trace, system: CorrectJobMatchingSystem) -> ConformanceReport:
    return replay_trace(
        trace=trace,
        adapter=JobMatchingReplayAdapter(system),
        invariants=INVARIANTS,
    )


def replay_job_matching_traces(
    traces: Iterable[Trace],
    system: CorrectJobMatchingSystem,
) -> tuple[ConformanceReport, ...]:
    return tuple(replay_job_matching_trace(trace, system) for trace in traces)


__all__ = [
    "JobMatchingReplayAdapter",
    "generate_representative_traces",
    "has_repeated_external_input",
    "replay_job_matching_trace",
    "replay_job_matching_traces",
    "select_representative_traces",
]

"""Job-matching model used by the flowguard MVP.

The model is intentionally abstract. It does not search real jobs and does not
call an LLM. It models a bounded function flow:

    Job -> ScoreJob -> RecordScoredJob -> DecideNextAction
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Iterable, Sequence

from flowguard import (
    Explorer,
    FunctionResult,
    Invariant,
    InvariantResult,
    Workflow,
)


ScoreBucket = str


@dataclass(frozen=True)
class Job:
    job_id: str
    domain_match_bucket: str
    location_bucket: str
    seniority_bucket: str


@dataclass(frozen=True)
class ScoredJob:
    job_id: str
    score_bucket: ScoreBucket


@dataclass(frozen=True)
class RecordResult:
    job_id: str
    status: str


@dataclass(frozen=True)
class Decision:
    job_id: str
    action: str


@dataclass(frozen=True)
class ScoreCacheEntry:
    job_id: str
    score_bucket: ScoreBucket


@dataclass(frozen=True)
class State:
    score_cache: tuple[ScoreCacheEntry, ...] = ()
    score_attempts: tuple[str, ...] = ()
    application_records: tuple[str, ...] = ()
    decisions: tuple[Decision, ...] = ()

    def cached_score(self, job_id: str) -> ScoreBucket | None:
        for entry in self.score_cache:
            if entry.job_id == job_id:
                return entry.score_bucket
        return None

    def has_application_record(self, job_id: str) -> bool:
        return job_id in self.application_records

    def with_score(self, job_id: str, score_bucket: ScoreBucket) -> "State":
        if self.cached_score(job_id) is not None:
            return self
        return replace(
            self,
            score_cache=self.score_cache + (ScoreCacheEntry(job_id, score_bucket),),
        )

    def with_score_attempt(self, job_id: str) -> "State":
        return replace(self, score_attempts=self.score_attempts + (job_id,))

    def with_application_record(self, job_id: str) -> "State":
        return replace(self, application_records=self.application_records + (job_id,))

    def with_decision(self, decision: Decision) -> "State":
        return replace(self, decisions=self.decisions + (decision,))


INITIAL_STATE = State()


class ScoreJob:
    name = "ScoreJob"
    reads = ("score_cache",)
    writes = ("score_cache", "score_attempts")
    accepted_input_type = Job
    input_description = "abstract Job"
    output_description = "ScoredJob with low/medium/high score_bucket"
    idempotency = "Cached jobs return the cached score without a new scoring attempt."

    def apply(self, input_obj: Job, state: State) -> Iterable[FunctionResult]:
        cached = state.cached_score(input_obj.job_id)
        if cached is not None:
            yield FunctionResult(
                output=ScoredJob(input_obj.job_id, cached),
                new_state=state,
                label="score_cached",
                reason="job_id already exists in score_cache",
            )
            return

        for score_bucket in possible_score_buckets(input_obj):
            new_state = state.with_score(input_obj.job_id, score_bucket).with_score_attempt(
                input_obj.job_id
            )
            yield FunctionResult(
                output=ScoredJob(input_obj.job_id, score_bucket),
                new_state=new_state,
                label=f"score_{score_bucket}",
                reason="new abstract score computed and cached",
            )


class BrokenScoreJob(ScoreJob):
    name = "BrokenScoreJob"
    idempotency = "Broken: ignores score_cache and scores the same job repeatedly."

    def apply(self, input_obj: Job, state: State) -> Iterable[FunctionResult]:
        for score_bucket in possible_score_buckets(input_obj):
            cached = state.cached_score(input_obj.job_id)
            new_state = state
            if cached is None:
                new_state = new_state.with_score(input_obj.job_id, score_bucket)
            new_state = new_state.with_score_attempt(input_obj.job_id)
            yield FunctionResult(
                output=ScoredJob(input_obj.job_id, score_bucket),
                new_state=new_state,
                label=f"score_again_{score_bucket}" if cached is not None else f"score_{score_bucket}",
                reason="broken block recomputes scoring even when cache exists",
            )


class RecordScoredJob:
    name = "RecordScoredJob"
    reads = ("application_records", "score_cache")
    writes = ("application_records",)
    accepted_input_type = ScoredJob
    input_description = "ScoredJob"
    output_description = "RecordResult"
    idempotency = "The same ScoredJob can be repeated without creating duplicate records."

    def apply(self, input_obj: ScoredJob, state: State) -> Iterable[FunctionResult]:
        if state.has_application_record(input_obj.job_id):
            yield FunctionResult(
                output=RecordResult(input_obj.job_id, "already_exists"),
                new_state=state,
                label="record_already_exists",
                reason="application_records already contains job_id",
            )
            return

        if input_obj.score_bucket == "low":
            yield FunctionResult(
                output=RecordResult(input_obj.job_id, "skipped"),
                new_state=state,
                label="record_skipped",
                reason="low score is not recorded",
            )
            return

        yield FunctionResult(
            output=RecordResult(input_obj.job_id, "added"),
            new_state=state.with_application_record(input_obj.job_id),
            label="record_added",
            reason="medium/high score is recorded once",
        )


class BrokenRecordScoredJob(RecordScoredJob):
    name = "BrokenRecordScoredJob"
    idempotency = "Broken: appends the job_id every time and never deduplicates."

    def apply(self, input_obj: ScoredJob, state: State) -> Iterable[FunctionResult]:
        yield FunctionResult(
            output=RecordResult(input_obj.job_id, "added"),
            new_state=state.with_application_record(input_obj.job_id),
            label="record_added_without_dedup",
            reason="broken block appends job_id without checking existing records",
        )


class DecideNextAction:
    name = "DecideNextAction"
    reads = ("application_records", "decisions")
    writes = ("decisions",)
    accepted_input_type = RecordResult
    input_description = "RecordResult"
    output_description = "Decision"
    idempotency = "Does not create contradictory apply/ignore decisions for the same job."

    def apply(self, input_obj: RecordResult, state: State) -> Iterable[FunctionResult]:
        if input_obj.status == "added":
            actions = ("apply", "save")
        elif input_obj.status == "already_exists":
            actions = ("save", "ask_human")
        elif input_obj.status == "skipped":
            actions = ("ignore",)
        else:
            return

        for action in actions:
            decision = Decision(input_obj.job_id, action)
            yield FunctionResult(
                output=decision,
                new_state=state.with_decision(decision),
                label=f"decision_{action}",
                reason=f"record status {input_obj.status!r} maps to {action!r}",
            )


def possible_score_buckets(job: Job) -> tuple[ScoreBucket, ...]:
    if job.domain_match_bucket == "low":
        return ("low",)
    if job.domain_match_bucket == "high" and job.seniority_bucket == "high":
        return ("medium", "high")
    return ("low", "medium", "high")


def build_workflow(
    score_block: Any | None = None,
    record_block: Any | None = None,
    decision_block: Any | None = None,
) -> Workflow:
    return Workflow(
        (
            score_block if score_block is not None else ScoreJob(),
            record_block if record_block is not None else RecordScoredJob(),
            decision_block if decision_block is not None else DecideNextAction(),
        ),
        name="job_matching",
    )


def duplicate_values(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return tuple(duplicates)


def no_duplicate_application_records(state: State, trace: Any) -> InvariantResult:
    del trace
    duplicates = duplicate_values(state.application_records)
    if duplicates:
        return InvariantResult.fail(f"duplicate application_records: {duplicates!r}")
    return InvariantResult.pass_()


def no_repeated_scoring_without_refresh(state: State, trace: Any) -> InvariantResult:
    del trace
    duplicates = duplicate_values(state.score_attempts)
    if duplicates:
        return InvariantResult.fail(f"repeated scoring without refresh: {duplicates!r}")
    return InvariantResult.pass_()


def every_application_record_has_score(state: State, trace: Any) -> InvariantResult:
    del trace
    scored_job_ids = {entry.job_id for entry in state.score_cache}
    missing = tuple(job_id for job_id in state.application_records if job_id not in scored_job_ids)
    if missing:
        return InvariantResult.fail(f"application record without score: {missing!r}")
    return InvariantResult.pass_()


def no_contradictory_final_decisions(state: State, trace: Any) -> InvariantResult:
    del trace
    actions_by_job: dict[str, set[str]] = {}
    for decision in state.decisions:
        actions_by_job.setdefault(decision.job_id, set()).add(decision.action)
    contradictory = tuple(
        job_id
        for job_id, actions in actions_by_job.items()
        if "apply" in actions and "ignore" in actions
    )
    if contradictory:
        return InvariantResult.fail(f"same job has both apply and ignore: {contradictory!r}")
    return InvariantResult.pass_()


def record_scored_job_is_idempotent(state: State, trace: Any) -> InvariantResult:
    del trace
    duplicates = duplicate_values(state.application_records)
    if duplicates:
        return InvariantResult.fail(
            f"RecordScoredJob is not idempotent for job_ids: {duplicates!r}"
        )
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant(
        name="no_duplicate_application_records",
        description="application_records contains each job_id at most once",
        predicate=no_duplicate_application_records,
    ),
    Invariant(
        name="no_repeated_scoring_without_refresh",
        description="score_attempts contains each job_id at most once",
        predicate=no_repeated_scoring_without_refresh,
    ),
    Invariant(
        name="every_application_record_has_score",
        description="recorded jobs must have an entry in score_cache",
        predicate=every_application_record_has_score,
    ),
    Invariant(
        name="no_contradictory_final_decisions",
        description="a job cannot be both applied and ignored",
        predicate=no_contradictory_final_decisions,
    ),
    Invariant(
        name="record_scored_job_is_idempotent",
        description="repeating the same ScoredJob cannot create duplicate records",
        predicate=record_scored_job_is_idempotent,
    ),
)


DEFAULT_INPUTS = (
    Job("job_high", "high", "good", "high"),
    Job("job_low", "low", "ok", "medium"),
    Job("job_mixed", "medium", "ok", "medium"),
)


def build_explorer(
    workflow: Workflow | None = None,
    external_inputs: Sequence[Job] = DEFAULT_INPUTS,
    max_sequence_length: int = 2,
    required_labels: Sequence[str] = ("decision_apply", "record_skipped"),
) -> Explorer:
    return Explorer(
        workflow=workflow or build_workflow(),
        initial_states=(INITIAL_STATE,),
        external_inputs=tuple(external_inputs),
        invariants=INVARIANTS,
        max_sequence_length=max_sequence_length,
        required_labels=tuple(required_labels),
    )


def check_job_matching_model(
    workflow: Workflow | None = None,
    external_inputs: Sequence[Job] = DEFAULT_INPUTS,
    max_sequence_length: int = 2,
    required_labels: Sequence[str] = ("decision_apply", "record_skipped"),
):
    return build_explorer(
        workflow=workflow,
        external_inputs=external_inputs,
        max_sequence_length=max_sequence_length,
        required_labels=required_labels,
    ).explore()


def format_report(report: Any) -> str:
    return report.format_text()


__all__ = [
    "BrokenRecordScoredJob",
    "BrokenScoreJob",
    "DEFAULT_INPUTS",
    "INITIAL_STATE",
    "INVARIANTS",
    "DecideNextAction",
    "Decision",
    "Job",
    "RecordResult",
    "RecordScoredJob",
    "ScoreCacheEntry",
    "ScoreJob",
    "ScoredJob",
    "State",
    "build_explorer",
    "build_workflow",
    "check_job_matching_model",
    "format_report",
    "possible_score_buckets",
]

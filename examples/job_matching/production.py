"""Simulated production implementations for job-matching conformance replay."""

from __future__ import annotations

from typing import Any

from .model import (
    Decision,
    Job,
    RecordResult,
    ScoreCacheEntry,
    ScoredJob,
    State,
    possible_score_buckets,
)


class CorrectJobMatchingSystem:
    """Small stateful implementation that should conform to the abstract model."""

    def __init__(self) -> None:
        self.score_cache: dict[str, str] = {}
        self.score_attempts: list[str] = []
        self.application_records: list[str] = []
        self.decisions: list[Decision] = []
        self.last_output: Any = None
        self.last_label = ""
        self.last_reason = ""

    def reset(self, initial_state: State | None = None) -> None:
        state = initial_state or State()
        self.score_cache = {
            entry.job_id: entry.score_bucket
            for entry in state.score_cache
        }
        self.score_attempts = list(state.score_attempts)
        self.application_records = list(state.application_records)
        self.decisions = list(state.decisions)
        self.last_output = None
        self.last_label = ""
        self.last_reason = ""

    def project_state(self) -> State:
        return State(
            score_cache=tuple(
                ScoreCacheEntry(job_id, score)
                for job_id, score in self.score_cache.items()
            ),
            score_attempts=tuple(self.score_attempts),
            application_records=tuple(self.application_records),
            decisions=tuple(self.decisions),
        )

    def score_job(self, job: Job, expected_score_bucket: str | None = None) -> ScoredJob:
        cached = self.score_cache.get(job.job_id)
        if cached is not None:
            output = ScoredJob(job.job_id, cached)
            self._remember(output, "score_cached", "job_id already exists in score_cache")
            return output

        possible = possible_score_buckets(job)
        score_bucket = expected_score_bucket if expected_score_bucket in possible else possible[0]
        self.score_cache[job.job_id] = score_bucket
        self.score_attempts.append(job.job_id)
        output = ScoredJob(job.job_id, score_bucket)
        self._remember(output, f"score_{score_bucket}", "new abstract score computed and cached")
        return output

    def record_scored_job(self, scored_job: ScoredJob) -> RecordResult:
        if scored_job.job_id in self.application_records:
            output = RecordResult(scored_job.job_id, "already_exists")
            self._remember(output, "record_already_exists", "application_records already contains job_id")
            return output

        if scored_job.score_bucket == "low":
            output = RecordResult(scored_job.job_id, "skipped")
            self._remember(output, "record_skipped", "low score is not recorded")
            return output

        self.application_records.append(scored_job.job_id)
        output = RecordResult(scored_job.job_id, "added")
        self._remember(output, "record_added", "medium/high score is recorded once")
        return output

    def decide_next_action(
        self,
        record_result: RecordResult,
        expected_action: str | None = None,
    ) -> Decision:
        if record_result.status == "added":
            actions = ("apply", "save")
        elif record_result.status == "already_exists":
            actions = ("save", "ask_human")
        elif record_result.status == "skipped":
            actions = ("ignore",)
        else:
            actions = ("ask_human",)

        action = expected_action if expected_action in actions else actions[0]
        output = Decision(record_result.job_id, action)
        self.decisions.append(output)
        self._remember(output, f"decision_{action}", f"record status {record_result.status!r} maps to {action!r}")
        return output

    def _remember(self, output: Any, label: str, reason: str) -> None:
        self.last_output = output
        self.last_label = label
        self.last_reason = reason


class BrokenDuplicateRecordSystem(CorrectJobMatchingSystem):
    """Broken implementation that appends duplicate application records."""

    def record_scored_job(self, scored_job: ScoredJob) -> RecordResult:
        if scored_job.score_bucket == "low":
            output = RecordResult(scored_job.job_id, "skipped")
            self._remember(output, "record_skipped", "low score is not recorded")
            return output

        self.application_records.append(scored_job.job_id)
        output = RecordResult(scored_job.job_id, "added")
        self._remember(
            output,
            "record_added",
            "broken implementation appends without checking existing records",
        )
        return output


class BrokenRepeatedScoringSystem(CorrectJobMatchingSystem):
    """Broken implementation that scores again even when a cache entry exists."""

    def score_job(self, job: Job, expected_score_bucket: str | None = None) -> ScoredJob:
        cached = self.score_cache.get(job.job_id)
        possible = possible_score_buckets(job)
        score_bucket = (
            expected_score_bucket
            if expected_score_bucket in possible
            else cached or possible[0]
        )
        if cached is None:
            self.score_cache[job.job_id] = score_bucket
        self.score_attempts.append(job.job_id)
        output = ScoredJob(job.job_id, score_bucket)
        label = f"score_again_{score_bucket}" if cached is not None else f"score_{score_bucket}"
        self._remember(
            output,
            label,
            "broken implementation recomputes scoring even when cache exists",
        )
        return output


__all__ = [
    "BrokenDuplicateRecordSystem",
    "BrokenRepeatedScoringSystem",
    "CorrectJobMatchingSystem",
]

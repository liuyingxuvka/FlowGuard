"""Scenario catalog for job-matching expected-vs-observed review."""

from __future__ import annotations

from typing import Any, Callable, Iterable, Sequence

from flowguard import FunctionResult, Workflow
from flowguard.scenario import (
    OracleCheckResult,
    Scenario,
    ScenarioExpectation,
    ScenarioRun,
)

from .model import (
    INITIAL_STATE,
    INVARIANTS,
    BrokenRecordScoredJob,
    BrokenScoreJob,
    DecideNextAction,
    Decision,
    Job,
    RecordResult,
    RecordScoredJob,
    ScoreCacheEntry,
    ScoreJob,
    ScoredJob,
    State,
    build_workflow,
    possible_score_buckets,
)


job_high_A = Job("job_high_A", "high", "good", "high")
job_high_B = Job("job_high_B", "high", "good", "high")
job_low_A = Job("job_low_A", "low", "bad", "low")
job_medium_A = Job("job_medium_A", "medium", "ok", "medium")
job_medium_B = Job("job_medium_B", "medium", "ok", "medium")
job_conflict_A_low = Job("job_high_A", "low", "bad", "low")


def _count(values: Sequence[str], item: str) -> int:
    return sum(1 for value in values if value == item)


def _score_attempt_count_ok(job_id: str, expected_count: int) -> Callable[[ScenarioRun], OracleCheckResult]:
    def check(run: ScenarioRun) -> OracleCheckResult:
        bad = [
            state
            for state in run.final_states
            if _count(state.score_attempts, job_id) != expected_count
        ]
        return OracleCheckResult(
            ok=not bad,
            message=f"score_attempts[{job_id}] != {expected_count}",
            evidence=(f"score_attempts[{job_id}] == {expected_count}",),
            violation_name="score_attempt_count_mismatch",
        )

    return check


def _score_attempt_at_most(job_id: str, max_count: int = 1) -> Callable[[ScenarioRun], OracleCheckResult]:
    def check(run: ScenarioRun) -> OracleCheckResult:
        bad = [
            state
            for state in run.final_states
            if _count(state.score_attempts, job_id) > max_count
        ]
        return OracleCheckResult(
            ok=not bad,
            message=f"score_attempts[{job_id}] exceeded {max_count}",
            evidence=(f"score_attempts[{job_id}] <= {max_count}",),
            violation_name="score_attempt_count_mismatch",
        )

    return check


def _record_count_ok(job_id: str, expected_count: int) -> Callable[[ScenarioRun], OracleCheckResult]:
    def check(run: ScenarioRun) -> OracleCheckResult:
        bad = [
            state
            for state in run.final_states
            if _count(state.application_records, job_id) != expected_count
        ]
        return OracleCheckResult(
            ok=not bad,
            message=f"application_records[{job_id}] != {expected_count}",
            evidence=(f"application_records[{job_id}] == {expected_count}",),
            violation_name="application_record_count_mismatch",
        )

    return check


def _record_at_most(job_id: str, max_count: int = 1) -> Callable[[ScenarioRun], OracleCheckResult]:
    def check(run: ScenarioRun) -> OracleCheckResult:
        bad = [
            state
            for state in run.final_states
            if _count(state.application_records, job_id) > max_count
        ]
        return OracleCheckResult(
            ok=not bad,
            message=f"application_records[{job_id}] exceeded {max_count}",
            evidence=(f"application_records[{job_id}] <= {max_count}",),
            violation_name="application_record_count_mismatch",
        )

    return check


def _cache_contains(job_id: str) -> Callable[[ScenarioRun], OracleCheckResult]:
    def check(run: ScenarioRun) -> OracleCheckResult:
        bad = [state for state in run.final_states if state.cached_score(job_id) is None]
        return OracleCheckResult(
            ok=not bad,
            message=f"score_cache lacks {job_id}",
            evidence=(f"score_cache contains {job_id}",),
            violation_name="score_cache_missing",
        )

    return check


def _decision_actions_only(job_id: str, allowed: set[str]) -> Callable[[ScenarioRun], OracleCheckResult]:
    def check(run: ScenarioRun) -> OracleCheckResult:
        bad_actions = sorted(
            {
                decision.action
                for state in run.final_states
                for decision in state.decisions
                if decision.job_id == job_id and decision.action not in allowed
            }
        )
        return OracleCheckResult(
            ok=not bad_actions,
            message=f"unexpected decisions for {job_id}: {bad_actions!r}",
            evidence=(f"decisions[{job_id}] only in {sorted(allowed)!r}",),
            violation_name="unexpected_decision",
        )

    return check


def _any_path_label(label: str) -> Callable[[ScenarioRun], OracleCheckResult]:
    def check(run: ScenarioRun) -> OracleCheckResult:
        found = any(trace.has_label(label) for trace in run.traces)
        return OracleCheckResult(
            ok=found,
            message=f"missing path label {label}",
            evidence=(f"at least one path has label {label}",),
            violation_name="missing_required_path",
        )

    return check


def _conflicting_identity_evidence(run: ScenarioRun) -> OracleCheckResult:
    ids = [item.job_id for item in run.scenario.external_input_sequence if isinstance(item, Job)]
    repeated = sorted({job_id for job_id in ids if ids.count(job_id) > 1})
    return OracleCheckResult(
        ok=True,
        evidence=(f"conflicting identity encountered: {tuple(repeated)!r}",),
        violation_name="conflicting_identity",
    )


def _low_score_should_not_create_record(job_id: str) -> Callable[[ScenarioRun], OracleCheckResult]:
    def check(run: ScenarioRun) -> OracleCheckResult:
        bad = [
            state
            for state in run.final_states
            if job_id in state.application_records
        ]
        return OracleCheckResult(
            ok=not bad,
            message=f"low score created application record for {job_id}",
            evidence=(f"low-score job {job_id} must not be in application_records",),
            violation_name="low_score_should_not_create_application_record",
        )

    return check


def _every_recorded_job_has_decision(run: ScenarioRun) -> OracleCheckResult:
    bad_states = []
    for state in run.final_states:
        decided = {decision.job_id for decision in state.decisions}
        missing = [job_id for job_id in state.application_records if job_id not in decided]
        if missing:
            bad_states.append(tuple(missing))
    return OracleCheckResult(
        ok=not bad_states,
        message=f"recorded jobs without decisions: {bad_states!r}",
        evidence=("every recorded job should have a decision",),
        violation_name="every_recorded_job_should_have_decision",
    )


def _score_output_must_match_cache(run: ScenarioRun) -> OracleCheckResult:
    mismatches = []
    for trace in run.traces:
        for step in trace.steps:
            if step.function_name != "ScoreJob" or not isinstance(step.function_output, ScoredJob):
                continue
            cached = step.new_state.cached_score(step.function_output.job_id)
            if cached != step.function_output.score_bucket:
                mismatches.append((step.function_output.job_id, step.function_output.score_bucket, cached))
    return OracleCheckResult(
        ok=not mismatches,
        message=f"score output/cache mismatch: {mismatches!r}",
        evidence=("ScoredJob.score_bucket must match score_cache[job_id]",),
        violation_name="score_output_must_match_cache",
    )


def _score_job_must_not_write_application_records(run: ScenarioRun) -> OracleCheckResult:
    bad_steps = []
    for trace in run.traces:
        for step in trace.steps:
            if (
                step.function_name == "ScoreJob"
                and step.old_state.application_records != step.new_state.application_records
            ):
                bad_steps.append(step.function_output.job_id if isinstance(step.function_output, ScoredJob) else "?")
    return OracleCheckResult(
        ok=not bad_steps,
        message=f"ScoreJob wrote application_records: {bad_steps!r}",
        evidence=("ScoreJob must not change application_records",),
        violation_name="score_job_must_not_change_application_records",
    )


def _no_duplicate_final_decision_per_job(run: ScenarioRun) -> OracleCheckResult:
    duplicates = []
    for state in run.final_states:
        seen: set[tuple[str, str]] = set()
        for decision in state.decisions:
            key = (decision.job_id, decision.action)
            if key in seen:
                duplicates.append(key)
            seen.add(key)
    return OracleCheckResult(
        ok=not duplicates,
        message=f"duplicate final decisions: {tuple(duplicates)!r}",
        evidence=("no duplicate final decision per job/action",),
        violation_name="no_duplicate_final_decision_per_job",
    )


class BrokenRecordLowScoreJob(RecordScoredJob):
    name = "RecordScoredJob"

    def apply(self, input_obj: ScoredJob, state: State):
        yield FunctionResult(
            output=RecordResult(input_obj.job_id, "added"),
            new_state=state.with_application_record(input_obj.job_id),
            label="record_added_low_score_bug",
            reason="broken block records low-score jobs",
        )


class BrokenDecisionConflictBlock(DecideNextAction):
    name = "DecideNextAction"

    def apply(self, input_obj: RecordResult, state: State):
        if input_obj.status == "skipped":
            decision = Decision(input_obj.job_id, "ignore")
            yield FunctionResult(decision, state.with_decision(decision), "decision_ignore")
            return
        apply = Decision(input_obj.job_id, "apply")
        ignore = Decision(input_obj.job_id, "ignore")
        yield FunctionResult(
            output=apply,
            new_state=state.with_decision(apply).with_decision(ignore),
            label="decision_conflict",
            reason="broken block creates apply and ignore in one state",
        )


class BrokenMissingDecisionBlock(DecideNextAction):
    name = "DecideNextAction"

    def apply(self, input_obj: RecordResult, state: State):
        if input_obj.status == "added":
            return ()
        yield from super().apply(input_obj, state)


class BrokenWrongOutputRecordBlock(RecordScoredJob):
    name = "RecordScoredJob"

    def apply(self, input_obj: ScoredJob, state: State):
        yield FunctionResult(
            output=("unexpected", input_obj.job_id),
            new_state=state.with_application_record(input_obj.job_id),
            label="record_wrong_output",
            reason="broken block emits output that DecideNextAction cannot consume",
        )


class BrokenScoreNoCacheUpdate(ScoreJob):
    name = "ScoreJob"

    def apply(self, input_obj: Job, state: State):
        score_bucket = possible_score_buckets(input_obj)[-1]
        yield FunctionResult(
            output=ScoredJob(input_obj.job_id, score_bucket),
            new_state=state.with_score_attempt(input_obj.job_id),
            label=f"score_{score_bucket}_without_cache",
            reason="broken block scores without updating score_cache",
        )


class BrokenScoreCacheMismatch(ScoreJob):
    name = "ScoreJob"

    def apply(self, input_obj: Job, state: State):
        yield FunctionResult(
            output=ScoredJob(input_obj.job_id, "high"),
            new_state=state.with_score(input_obj.job_id, "low").with_score_attempt(input_obj.job_id),
            label="score_cache_mismatch",
            reason="broken block stores a different score than it outputs",
        )


class BrokenScoreWritesApplicationRecord(ScoreJob):
    name = "ScoreJob"

    def apply(self, input_obj: Job, state: State):
        score_bucket = possible_score_buckets(input_obj)[-1]
        new_state = (
            state.with_score(input_obj.job_id, score_bucket)
            .with_score_attempt(input_obj.job_id)
            .with_application_record(input_obj.job_id)
        )
        yield FunctionResult(
            output=ScoredJob(input_obj.job_id, score_bucket),
            new_state=new_state,
            label="score_wrong_state_owner",
            reason="broken block writes application_records",
        )


class BrokenDecisionDuplicate(DecideNextAction):
    name = "DecideNextAction"

    def apply(self, input_obj: RecordResult, state: State):
        action = "apply" if input_obj.status == "added" else "save"
        decision = Decision(input_obj.job_id, action)
        yield FunctionResult(
            output=decision,
            new_state=state.with_decision(decision).with_decision(decision),
            label=f"decision_duplicate_{action}",
            reason="broken block writes duplicate identical decisions",
        )


class BrokenRepeatDecisionConflict(DecideNextAction):
    name = "DecideNextAction"

    def apply(self, input_obj: RecordResult, state: State):
        action = "ignore" if input_obj.status == "already_exists" else "apply"
        decision = Decision(input_obj.job_id, action)
        yield FunctionResult(
            output=decision,
            new_state=state.with_decision(decision),
            label=f"decision_{action}",
            reason="broken repeat decision creates conflict",
        )


class BrokenRecordWithoutSourceScore(RecordScoredJob):
    name = "RecordScoredJob"

    def apply(self, input_obj: ScoredJob, state: State):
        ghost_job_id = input_obj.job_id + "_ghost"
        yield FunctionResult(
            output=RecordResult(ghost_job_id, "added"),
            new_state=state.with_application_record(ghost_job_id),
            label="record_without_source_score",
            reason="broken block records a job_id that was not scored",
        )


def _expect_ok(summary: str, labels: Sequence[str] = (), checks: Sequence[Callable[[ScenarioRun], OracleCheckResult]] = ()) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="ok",
        required_trace_labels=tuple(labels),
        custom_checks=tuple(checks),
        summary=summary,
    )


def _expect_violation(summary: str, names: Sequence[str], checks: Sequence[Callable[[ScenarioRun], OracleCheckResult]] = ()) -> ScenarioExpectation:
    return ScenarioExpectation(
        expected_status="violation",
        expected_violation_names=tuple(names),
        custom_checks=tuple(checks),
        summary=summary,
    )


def scenario(
    name: str,
    description: str,
    sequence: Sequence[Job],
    expected: ScenarioExpectation,
    workflow: Workflow | None = None,
    initial_state: State = INITIAL_STATE,
    tags: Sequence[str] = (),
    notes: str = "",
) -> Scenario:
    return Scenario(
        name=name,
        description=description,
        initial_state=initial_state,
        external_input_sequence=tuple(sequence),
        tags=tuple(tags),
        expected=expected,
        notes=notes,
        workflow=workflow or build_workflow(),
        invariants=INVARIANTS,
    )


def correct_model_scenarios() -> tuple[Scenario, ...]:
    return (
        scenario(
            "S01_high_single_first_time",
            "High match first-time job branches to medium/high and may be recorded.",
            (job_high_A,),
            _expect_ok(
                "OK; high job scored once and record path exists",
                labels=("record_added", "decision_apply"),
                checks=(
                    _cache_contains("job_high_A"),
                    _score_attempt_count_ok("job_high_A", 1),
                    _record_at_most("job_high_A"),
                ),
            ),
        ),
        scenario(
            "S02_low_single_first_time",
            "Low match should be skipped and ignored.",
            (job_low_A,),
            _expect_ok(
                "OK; low job skipped and ignored",
                labels=("record_skipped", "decision_ignore"),
                checks=(
                    _cache_contains("job_low_A"),
                    _score_attempt_count_ok("job_low_A", 1),
                    _record_count_ok("job_low_A", 0),
                    _decision_actions_only("job_low_A", {"ignore"}),
                ),
            ),
        ),
        scenario(
            "S03_medium_single_ambiguous",
            "Medium job branches into low/medium/high outcomes.",
            (job_medium_A,),
            _expect_ok(
                "OK; medium job has skip and add branches",
                labels=("record_skipped", "decision_ignore", "record_added", "decision_apply"),
                checks=(
                    _score_attempt_count_ok("job_medium_A", 1),
                    _record_at_most("job_medium_A"),
                ),
            ),
        ),
        scenario(
            "S04_high_same_job_twice",
            "Repeated high job should use cache and avoid duplicate records.",
            (job_high_A, job_high_A),
            _expect_ok(
                "OK; no duplicate record or repeated scoring",
                labels=("score_cached", "record_already_exists"),
                checks=(
                    _score_attempt_count_ok("job_high_A", 1),
                    _record_at_most("job_high_A"),
                ),
            ),
        ),
        scenario(
            "S05_low_same_job_twice",
            "Repeated low job should use cache and remain ignored.",
            (job_low_A, job_low_A),
            _expect_ok(
                "OK; repeated low job still skipped",
                labels=("score_cached", "record_skipped", "decision_ignore"),
                checks=(
                    _score_attempt_count_ok("job_low_A", 1),
                    _record_count_ok("job_low_A", 0),
                    _decision_actions_only("job_low_A", {"ignore"}),
                ),
            ),
        ),
        scenario(
            "S06_medium_same_job_twice",
            "Repeated medium job handles cached low/medium/high branches.",
            (job_medium_A, job_medium_A),
            _expect_ok(
                "OK; repeated medium job remains idempotent",
                labels=("score_cached", "record_skipped", "record_already_exists"),
                checks=(
                    _score_attempt_count_ok("job_medium_A", 1),
                    _record_at_most("job_medium_A"),
                ),
            ),
        ),
        scenario(
            "S07_high_A_B_A",
            "Two high jobs with first repeated.",
            (job_high_A, job_high_B, job_high_A),
            _expect_ok(
                "OK; each job scored once and records deduped",
                labels=("score_cached", "record_already_exists"),
                checks=(
                    _score_attempt_count_ok("job_high_A", 1),
                    _score_attempt_count_ok("job_high_B", 1),
                    _record_at_most("job_high_A"),
                    _record_at_most("job_high_B"),
                ),
            ),
        ),
        scenario(
            "S08_high_A_low_B_A",
            "High job, low job, then high job again.",
            (job_high_A, job_low_A, job_high_A),
            _expect_ok(
                "OK; low job never records and high repeat is idempotent",
                labels=("record_skipped", "score_cached"),
                checks=(
                    _score_attempt_count_ok("job_high_A", 1),
                    _score_attempt_count_ok("job_low_A", 1),
                    _record_at_most("job_high_A"),
                    _record_count_ok("job_low_A", 0),
                ),
            ),
        ),
        scenario(
            "S09_existing_score_cache_high",
            "Existing score cache should be used without a new attempt.",
            (job_high_A,),
            _expect_ok(
                "OK; cached score avoids new score_attempt",
                labels=("score_cached", "record_added"),
                checks=(
                    _score_attempt_count_ok("job_high_A", 0),
                    _record_at_most("job_high_A"),
                ),
            ),
            initial_state=State(score_cache=(ScoreCacheEntry("job_high_A", "high"),)),
        ),
        scenario(
            "S10_existing_application_record",
            "Existing application record remains single.",
            (job_high_A,),
            _expect_ok(
                "OK; existing record returns already_exists",
                labels=("score_cached", "record_already_exists"),
                checks=(_record_count_ok("job_high_A", 1),),
            ),
            initial_state=State(
                score_cache=(ScoreCacheEntry("job_high_A", "high"),),
                application_records=("job_high_A",),
            ),
        ),
        scenario(
            "S11_inconsistent_initial_record_without_score",
            "Invalid starting state has a record without source score.",
            (job_high_A,),
            _expect_violation(
                "VIOLATION every_application_record_has_score",
                ("every_application_record_has_score",),
            ),
            initial_state=State(application_records=("job_high_A",)),
        ),
        scenario(
            "S12_high_same_job_three_times",
            "Triple repeated high job remains idempotent.",
            (job_high_A, job_high_A, job_high_A),
            _expect_ok(
                "OK; triple repeat does not duplicate side effects",
                labels=("score_cached", "record_already_exists"),
                checks=(
                    _score_attempt_count_ok("job_high_A", 1),
                    _record_at_most("job_high_A"),
                ),
            ),
        ),
        scenario(
            "S13_same_job_id_conflicting_features",
            "Same job_id appears with conflicting abstract features.",
            (job_high_A, job_conflict_A_low),
            ScenarioExpectation(
                expected_status="needs_human_review",
                custom_checks=(
                    _score_attempt_count_ok("job_high_A", 1),
                    _record_at_most("job_high_A"),
                    _conflicting_identity_evidence,
                ),
                summary="NEEDS_HUMAN_REVIEW; identity conflict has no explicit policy yet",
            ),
            notes="Current model treats job_id as identity and has no explicit conflict tracking.",
        ),
        scenario(
            "S14_two_medium_jobs_then_repeat_first",
            "Two ambiguous jobs then repeat first.",
            (job_medium_A, job_medium_B, job_medium_A),
            _expect_ok(
                "OK; each individual trace satisfies invariants",
                labels=("score_cached",),
                checks=(
                    _score_attempt_count_ok("job_medium_A", 1),
                    _score_attempt_count_ok("job_medium_B", 1),
                    _record_at_most("job_medium_A"),
                    _record_at_most("job_medium_B"),
                ),
            ),
        ),
        scenario(
            "S15_empty_or_noop_sequence",
            "Empty input sequence should leave state unchanged.",
            (),
            _expect_ok(
                "OK; no state change",
                checks=(
                    lambda run: OracleCheckResult(
                        ok=run.final_states == (INITIAL_STATE,),
                        message="empty sequence changed state",
                        evidence=("empty sequence leaves state unchanged",),
                        violation_name="empty_sequence_changed_state",
                    ),
                ),
            ),
        ),
    )


def broken_model_scenarios() -> tuple[Scenario, ...]:
    return (
        scenario(
            "B01_broken_duplicate_record_repeated_high",
            "Broken record block duplicates repeated high job.",
            (job_high_A, job_high_A),
            _expect_violation(
                "VIOLATION no_duplicate_application_records",
                ("no_duplicate_application_records", "record_scored_job_is_idempotent"),
            ),
            workflow=build_workflow(record_block=BrokenRecordScoredJob()),
        ),
        scenario(
            "B02_broken_duplicate_record_triple_high",
            "Broken record block gets worse under triple repeat.",
            (job_high_A, job_high_A, job_high_A),
            _expect_violation(
                "VIOLATION no_duplicate_application_records",
                ("no_duplicate_application_records",),
            ),
            workflow=build_workflow(record_block=BrokenRecordScoredJob()),
        ),
        scenario(
            "B03_broken_repeated_scoring_high_twice",
            "Broken score block recomputes repeated high job.",
            (job_high_A, job_high_A),
            _expect_violation(
                "VIOLATION no_repeated_scoring_without_refresh",
                ("no_repeated_scoring_without_refresh",),
            ),
            workflow=build_workflow(score_block=BrokenScoreJob()),
        ),
        scenario(
            "B04_broken_repeated_scoring_mixed_A_B_A",
            "Broken score block recomputes A in A/B/A sequence.",
            (job_high_A, job_high_B, job_high_A),
            _expect_violation(
                "VIOLATION no_repeated_scoring_without_refresh",
                ("no_repeated_scoring_without_refresh",),
            ),
            workflow=build_workflow(score_block=BrokenScoreJob()),
        ),
        scenario(
            "B05_broken_low_score_recorded",
            "Broken record block records low score.",
            (job_low_A,),
            _expect_violation(
                "VIOLATION low_score_should_not_create_application_record",
                ("low_score_should_not_create_application_record",),
                checks=(_low_score_should_not_create_record("job_low_A"),),
            ),
            workflow=build_workflow(record_block=BrokenRecordLowScoreJob()),
        ),
        scenario(
            "B06_broken_decision_conflict",
            "Broken decision block creates apply and ignore in one final state.",
            (job_high_A,),
            _expect_violation(
                "VIOLATION no_contradictory_final_decisions",
                ("no_contradictory_final_decisions",),
            ),
            workflow=build_workflow(decision_block=BrokenDecisionConflictBlock()),
        ),
        scenario(
            "B07_broken_missing_decision_after_record",
            "Broken decision block returns no result after record.",
            (job_high_A,),
            _expect_violation(
                "VIOLATION dead_branch/every_recorded_job_should_have_decision",
                ("dead_branch",),
                checks=(_every_recorded_job_has_decision,),
            ),
            workflow=build_workflow(decision_block=BrokenMissingDecisionBlock()),
        ),
        scenario(
            "B08_broken_downstream_non_consumable_output",
            "Broken record block emits an output that decision block cannot consume.",
            (job_high_A,),
            _expect_violation(
                "VIOLATION dead_branch non-consumable output",
                ("dead_branch",),
            ),
            workflow=build_workflow(record_block=BrokenWrongOutputRecordBlock()),
        ),
        scenario(
            "B09_broken_score_does_not_update_cache",
            "Broken score block does not update score_cache.",
            (job_high_A,),
            _expect_violation(
                "VIOLATION every_application_record_has_score",
                ("every_application_record_has_score",),
            ),
            workflow=build_workflow(score_block=BrokenScoreNoCacheUpdate()),
        ),
        scenario(
            "B10_broken_cache_mismatch",
            "Broken score block outputs high but stores low.",
            (job_high_A,),
            _expect_violation(
                "VIOLATION score_output_must_match_cache",
                ("score_output_must_match_cache",),
                checks=(_score_output_must_match_cache,),
            ),
            workflow=build_workflow(score_block=BrokenScoreCacheMismatch()),
        ),
        scenario(
            "B11_broken_wrong_state_owner",
            "Broken ScoreJob writes application_records.",
            (job_high_A,),
            _expect_violation(
                "VIOLATION score_job_must_not_change_application_records",
                ("score_job_must_not_change_application_records",),
                checks=(_score_job_must_not_write_application_records,),
            ),
            workflow=build_workflow(score_block=BrokenScoreWritesApplicationRecord()),
        ),
        scenario(
            "B12_broken_duplicate_decisions",
            "Broken decision block writes duplicate identical decisions.",
            (job_high_A, job_high_A),
            _expect_violation(
                "VIOLATION no_duplicate_final_decision_per_job",
                ("no_duplicate_final_decision_per_job",),
                checks=(_no_duplicate_final_decision_per_job,),
            ),
            workflow=build_workflow(decision_block=BrokenDecisionDuplicate()),
        ),
        scenario(
            "B13_broken_ignore_after_apply_on_repeat",
            "Broken repeated decision creates apply/ignore conflict.",
            (job_high_A, job_high_A),
            _expect_violation(
                "VIOLATION no_contradictory_final_decisions",
                ("no_contradictory_final_decisions",),
            ),
            workflow=build_workflow(decision_block=BrokenRepeatDecisionConflict()),
        ),
        scenario(
            "B14_broken_record_without_source_score",
            "Broken record block writes a different unscored job_id.",
            (job_high_A,),
            _expect_violation(
                "VIOLATION every_application_record_has_score",
                ("every_application_record_has_score",),
            ),
            workflow=build_workflow(record_block=BrokenRecordWithoutSourceScore()),
        ),
        scenario(
            "B15_broken_idempotency_hidden_by_projection",
            "Projection anti-pattern documentation scenario.",
            (),
            ScenarioExpectation(
                expected_status="needs_human_review",
                summary="NEEDS_HUMAN_REVIEW; bad projection can hide duplicates and must be reviewed",
                custom_checks=(
                    lambda run: OracleCheckResult(
                        ok=True,
                        evidence=("adapter projection must not silently deduplicate raw side effects",),
                        violation_name="projection_can_hide_bug",
                    ),
                ),
            ),
            notes="Documentation-only meta-scenario for adapter/oracle correctness.",
        ),
    )


def all_job_matching_scenarios() -> tuple[Scenario, ...]:
    return correct_model_scenarios() + broken_model_scenarios()


__all__ = [
    "all_job_matching_scenarios",
    "broken_model_scenarios",
    "correct_model_scenarios",
    "job_conflict_A_low",
    "job_high_A",
    "job_high_B",
    "job_low_A",
    "job_medium_A",
    "job_medium_B",
]

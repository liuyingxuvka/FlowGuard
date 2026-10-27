"""The job-matching example scores, records and decides each job once; its broken systems fail replay.

The rules are the example's own five invariants (examples/job_matching/model.py).
Conformance replays the example's representative traces on the production code
(CorrectJobMatchingSystem) and requires the two broken production systems to fail
that replay, which is what the example teaches.
"""
from typing import Iterable

from flowguard import FunctionResult, Invariant
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact

from examples.job_matching.model import (DEFAULT_INPUTS, INITIAL_STATE, BrokenRecordScoredJob, BrokenScoreJob,
                                         DecideNextAction, Decision, RecordResult, RecordScoredJob, build_workflow,
                                         every_application_record_has_score, no_contradictory_final_decisions,
                                         no_duplicate_application_records, no_repeated_scoring_without_refresh,
                                         record_scored_job_is_idempotent)

MODEL_ID = "job_matching_example"
PARENT = "examples"
IMPLEMENTED_BY = {
    "Reset": "examples/job_matching/production.py:CorrectJobMatchingSystem.reset",
    "Score": "examples/job_matching/production.py:CorrectJobMatchingSystem.score_job",
    "Record": "examples/job_matching/production.py:CorrectJobMatchingSystem.record_scored_job",
    "Decide": "examples/job_matching/production.py:CorrectJobMatchingSystem.decide_next_action",
    "Remember": "examples/job_matching/production.py:CorrectJobMatchingSystem._remember",
    "BrokenRecord": "examples/job_matching/production.py:BrokenDuplicateRecordSystem.record_scored_job",
    "BrokenScore": "examples/job_matching/production.py:BrokenRepeatedScoringSystem.score_job",
}
USES = {
    'CorrectJobMatchingSystem': 'examples/job_matching/production.py:CorrectJobMatchingSystem',
    'GenerateRepresentativeTraces': 'examples/job_matching/conformance.py:generate_representative_traces',
    'ReplayJobMatchingTrace': 'examples/job_matching/conformance.py:replay_job_matching_trace',
}
NOT_MODELED = {}
TESTED_BY = {
    "no_duplicate_application_records": [
        "tests/test_conformance_replay_duplicate_record_failure.py:"
        "ConformanceReplayDuplicateRecordFailureTests.test_broken_duplicate_record_system_fails_replay",
    ],
    "record_scored_job_is_idempotent": [
        "tests/test_conformance_replay_duplicate_record_failure.py:"
        "ConformanceReplayDuplicateRecordFailureTests.test_broken_duplicate_record_system_fails_replay",
    ],
    "no_repeated_scoring_without_refresh": [
        "tests/test_conformance_replay_repeated_scoring_failure.py:"
        "ConformanceReplayRepeatedScoringFailureTests.test_broken_repeated_scoring_system_fails_replay",
    ],
    "every_application_record_has_score": [
        "tests/test_conformance_replay_success.py:ConformanceReplaySuccessTests.test_correct_production_replays_representative_trace",
    ],
    "no_contradictory_final_decisions": [
        "tests/test_job_matching_example.py:test_production_systems_score_record_decide_and_reset",
    ],
}

INVARIANTS = (
    Invariant("no_duplicate_application_records", "application_records contains each job_id at most once",
              no_duplicate_application_records),
    Invariant("no_repeated_scoring_without_refresh", "score_attempts contains each job_id at most once",
              no_repeated_scoring_without_refresh),
    Invariant("every_application_record_has_score", "recorded jobs must have an entry in score_cache",
              every_application_record_has_score),
    Invariant("no_contradictory_final_decisions", "a job cannot be both applied and ignored",
              no_contradictory_final_decisions),
    Invariant("record_scored_job_is_idempotent", "repeating the same ScoredJob cannot create duplicate records",
              record_scored_job_is_idempotent),
)


class RecordUnscoredJob(RecordScoredJob):
    """Known-bad: records a job id that was never scored."""

    def apply(self, input_obj, state) -> Iterable[FunctionResult]:
        unscored = input_obj.job_id + "-unscored"
        yield FunctionResult(output=RecordResult(unscored, "added"), new_state=state.with_application_record(unscored),
                             label="record_added", reason="records an id without a score")


class ApplyAndIgnore(DecideNextAction):
    """Known-bad: an added record is both applied and ignored."""

    def apply(self, input_obj, state) -> Iterable[FunctionResult]:
        if input_obj.status != "added":
            yield from super().apply(input_obj, state)
            return
        decided = state.with_decision(Decision(input_obj.job_id, "apply")).with_decision(Decision(input_obj.job_id, "ignore"))
        yield FunctionResult(output=Decision(input_obj.job_id, "apply"), new_state=decided, label="decision_apply",
                             reason="applies and ignores the same job")


def _explorer(**blocks):
    return Explorer(workflow=build_workflow(**blocks), initial_states=(INITIAL_STATE,), external_inputs=DEFAULT_INPUTS,
                    invariants=INVARIANTS, max_sequence_length=2, progress_steps=0)


def build_explorer():
    return _explorer()


def broken_variants():
    return {"repeated_scoring": _explorer(score_block=BrokenScoreJob()),
            "duplicate_record": _explorer(record_block=BrokenRecordScoredJob()),
            "record_unscored_job": _explorer(record_block=RecordUnscoredJob()),
            "apply_and_ignore": _explorer(decision_block=ApplyAndIgnore())}


def conformance():
    from examples.job_matching.conformance import generate_representative_traces, replay_job_matching_trace
    from examples.job_matching.production import (BrokenDuplicateRecordSystem, BrokenRepeatedScoringSystem,
                                                  CorrectJobMatchingSystem)
    traces = generate_representative_traces()
    facts = []
    for index, trace in enumerate(traces):
        report = replay_job_matching_trace(trace, CorrectJobMatchingSystem())
        facts.append(Fact(f"correct_system_replays_trace_{index}", report.ok, report.format_text()[:400]))
    for name, system in (("duplicate_record", BrokenDuplicateRecordSystem), ("repeated_scoring", BrokenRepeatedScoringSystem)):
        failed = [index for index, trace in enumerate(traces) if not replay_job_matching_trace(trace, system()).ok]
        facts.append(Fact(f"{name}_system_fails_replay", bool(failed), f"failing traces: {failed}"))
    return CodeFactsReport(tuple(facts))

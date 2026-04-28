"""Job-matching example model for flowguard."""

from .model import (
    BrokenRecordScoredJob,
    BrokenScoreJob,
    DecideNextAction,
    Decision,
    Job,
    RecordResult,
    RecordScoredJob,
    ScoreJob,
    ScoredJob,
    State,
    build_explorer,
    build_workflow,
    check_job_matching_model,
)

__all__ = [
    "BrokenRecordScoredJob",
    "BrokenScoreJob",
    "DecideNextAction",
    "Decision",
    "Job",
    "RecordResult",
    "RecordScoredJob",
    "ScoreJob",
    "ScoredJob",
    "State",
    "build_explorer",
    "build_workflow",
    "check_job_matching_model",
]

import unittest

from examples.job_matching.model import (
    INITIAL_STATE,
    Job,
    State,
    build_workflow,
    check_job_matching_model,
)
from flowguard import Workflow


class JobMatchingExampleTests(unittest.TestCase):
    def test_correct_model_passes(self):
        report = check_job_matching_model(max_sequence_length=2)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(0, len(report.violations))
        self.assertEqual(0, len(report.dead_branches))
        self.assertGreater(len(report.traces), 0)

    def test_high_match_branches_to_medium_or_high_score(self):
        job = Job("job_branch", "high", "good", "high")
        run = build_workflow().execute(INITIAL_STATE, job)

        self.assertEqual(4, len(run.completed_paths))
        labels = {label for path in run.completed_paths for label in path.trace.labels}
        self.assertIn("score_medium", labels)
        self.assertIn("score_high", labels)
        self.assertIn("decision_apply", labels)
        self.assertIn("decision_save", labels)

    def test_wrong_downstream_input_reports_dead_branch(self):
        class EmitsWrongType:
            name = "EmitsWrongType"
            accepted_input_type = Job

            def apply(self, input_obj, state):
                from flowguard import FunctionResult

                return (FunctionResult(output="not a ScoredJob", new_state=state),)

        workflow = Workflow((EmitsWrongType(),))
        # Composing this bad output into the real RecordScoredJob proves
        # non-consumable branches are visible instead of silently skipped.
        from examples.job_matching.model import RecordScoredJob

        workflow = Workflow((EmitsWrongType(), RecordScoredJob()))
        run = workflow.execute(State(), Job("job_dead", "high", "good", "high"))

        self.assertEqual(0, len(run.completed_paths))
        self.assertEqual(1, len(run.dead_branches))
        self.assertIn("cannot consume", run.dead_branches[0].reason)


if __name__ == "__main__":
    unittest.main()


def test_production_systems_score_record_decide_and_reset():
    """The simulated production systems behave as the abstract model expects (and the broken ones do not)."""
    from examples.job_matching.model import Job, State
    from examples.job_matching.production import (BrokenDuplicateRecordSystem, BrokenRepeatedScoringSystem,
                                                  CorrectJobMatchingSystem)

    job = Job("j1", "high", "near", "high")
    system = CorrectJobMatchingSystem()
    system.reset(State())
    scored = system.score_job(job)
    assert scored.score_bucket == "medium" and system.score_job(job) == scored
    assert system.score_attempts == ["j1"] and system.last_label == "score_cached"
    recorded = system.record_scored_job(scored)
    assert recorded.status == "added" and system.record_scored_job(scored).status == "already_exists"
    assert system.decide_next_action(recorded).action == "apply"
    system.reset(State())
    assert system.project_state() == State()
    duplicate = BrokenDuplicateRecordSystem()
    duplicate.record_scored_job(scored)
    duplicate.record_scored_job(scored)
    assert duplicate.application_records == ["j1", "j1"]
    repeated = BrokenRepeatedScoringSystem()
    repeated.score_job(job)
    repeated.score_job(job)
    assert repeated.score_attempts == ["j1", "j1"]

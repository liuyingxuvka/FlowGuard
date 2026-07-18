import inspect
import unittest

from examples.job_matching.production import CorrectJobMatchingSystem
from flowguard.conformance import replay_prediction
from flowguard.replay import ReplayInput, ReplayObservation
from flowguard.task_local_model import (
    REVISION_ACCEPTED,
    REVISION_REJECTED,
    REVISION_ROLLED_BACK,
    TaskModelRevision,
    TaskModelRevisionError,
    TaskModelVersion,
    TaskPredictionSnapshot,
    TaskReplayEvidence,
)
from flowguard.trace import Trace, TraceStep


MODEL_V1_SHA = "sha256:" + ("1" * 64)
MODEL_V2_SHA = "sha256:" + ("2" * 64)


def expected_trace():
    return Trace(
        steps=(
            TraceStep(
                external_input="request-1",
                function_name="Submit",
                function_input="request-1",
                function_output="accepted",
                old_state=(),
                new_state=("done",),
                label="accepted",
            ),
        ),
        initial_state=(),
        external_inputs=("request-1",),
    )


def prediction():
    return TaskPredictionSnapshot(
        prediction_id="prediction:submit:v1",
        task_id="task:submit",
        model_id="model:submit",
        scenario_id="scenario:submit",
        model_version=TaskModelVersion("v1", MODEL_V1_SHA, "model-v1.yaml"),
        expected_trace=expected_trace(),
        falsifier="production returns anything other than accepted in done state",
        observation_boundary_id="before:production-replay:1",
    )


def candidate_prediction(replay_id):
    return TaskPredictionSnapshot(
        prediction_id=f"prediction:{replay_id}:v2",
        task_id="task:submit",
        model_id="model:submit",
        scenario_id=f"scenario:{replay_id}",
        model_version=TaskModelVersion("v2", MODEL_V2_SHA, "model-v2.yaml"),
        expected_trace=expected_trace(),
        falsifier="candidate replay differs from the modeled accepted path",
        observation_boundary_id=f"before:{replay_id}",
    )


class IndependentAdapter:
    def __init__(self):
        self.last_input = None

    def reset(self, initial_state):
        self.last_input = None

    def apply_step(self, step):
        self.last_input = step
        if hasattr(step, "function_output") or hasattr(step, "new_state"):
            raise AssertionError("adapter received prediction oracle fields")
        return ReplayObservation(
            function_name=step.function_name,
            observed_output="accepted",
            observed_state=("done",),
            label="accepted",
        )


def passing_replay_evidence(replay_id):
    snapshot = candidate_prediction(replay_id)
    report = replay_prediction(snapshot, IndependentAdapter())
    return TaskReplayEvidence.from_conformance_report(replay_id, snapshot, report)


class TaskLocalPredictionReplayTests(unittest.TestCase):
    def test_prediction_fingerprint_is_deterministic_and_report_is_bound(self):
        first = prediction()
        second = prediction()
        adapter = IndependentAdapter()

        report = replay_prediction(first, adapter)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(first.trace_fingerprint, second.trace_fingerprint)
        self.assertEqual(first.prediction_fingerprint, second.prediction_fingerprint)
        self.assertEqual(first.prediction_id, report.prediction_id)
        self.assertEqual(first.prediction_fingerprint, report.prediction_fingerprint)
        self.assertEqual(MODEL_V1_SHA, report.model_fingerprint)
        self.assertEqual("before:production-replay:1", report.observation_boundary_id)
        self.assertIsInstance(adapter.last_input, ReplayInput)
        self.assertFalse(hasattr(adapter.last_input, "function_output"))

    def test_candidate_accept_requires_all_replays_and_rollback_restores_base(self):
        base = TaskModelVersion("v1", MODEL_V1_SHA)
        candidate = TaskModelVersion("v2", MODEL_V2_SHA)
        revision = TaskModelRevision(
            revision_id="revision:submit:v2",
            task_id="task:submit",
            model_id="model:submit",
            base_model=base,
            candidate_model=candidate,
            prediction_id="prediction:submit:v1",
            mismatch_summary="production replay exposed one missing retry state",
            changed_model_elements=("state:retry",),
            required_replay_ids=("replay:new-failure", "replay:old-normal"),
        )

        with self.assertRaises(TaskModelRevisionError):
            revision.accept((passing_replay_evidence("replay:new-failure"),))

        accepted = revision.accept(
            (
                passing_replay_evidence("replay:old-normal"),
                passing_replay_evidence("replay:new-failure"),
            )
        )
        rolled_back = accepted.rollback("holdout replay later regressed")

        self.assertEqual(REVISION_ACCEPTED, accepted.status)
        self.assertEqual(candidate, accepted.active_model)
        self.assertEqual(REVISION_ROLLED_BACK, rolled_back.status)
        self.assertEqual(base, rolled_back.active_model)

    def test_candidate_accept_rejects_ids_or_reports_bound_to_another_model(self):
        revision = TaskModelRevision(
            revision_id="revision:submit:v2",
            task_id="task:submit",
            model_id="model:submit",
            base_model=TaskModelVersion("v1", MODEL_V1_SHA),
            candidate_model=TaskModelVersion("v2", MODEL_V2_SHA),
            prediction_id="prediction:submit:v1",
            mismatch_summary="production replay exposed one missing retry state",
            changed_model_elements=("state:retry",),
            required_replay_ids=("replay:new-failure",),
        )
        with self.assertRaisesRegex(
            TaskModelRevisionError, "TaskReplayEvidence"
        ):
            revision.accept(("replay:new-failure",))

        baseline_snapshot = prediction()
        baseline_report = replay_prediction(baseline_snapshot, IndependentAdapter())
        baseline_evidence = TaskReplayEvidence.from_conformance_report(
            "replay:new-failure",
            baseline_snapshot,
            baseline_report,
        )
        with self.assertRaisesRegex(
            TaskModelRevisionError, "not bound to candidate"
        ):
            revision.accept((baseline_evidence,))

    def test_rejected_candidate_keeps_base_model_active(self):
        base = TaskModelVersion("v1", MODEL_V1_SHA)
        candidate = TaskModelVersion("v2", MODEL_V2_SHA)
        revision = TaskModelRevision(
            revision_id="revision:submit:v2",
            task_id="task:submit",
            model_id="model:submit",
            base_model=base,
            candidate_model=candidate,
            prediction_id="prediction:submit:v1",
            mismatch_summary="candidate fixes one trace but breaks a normal trace",
            changed_model_elements=("transition:submit-retry",),
            required_replay_ids=("replay:new-failure", "replay:old-normal"),
        )

        rejected = revision.reject("old normal replay failed")

        self.assertEqual(REVISION_REJECTED, rejected.status)
        self.assertEqual(base, rejected.active_model)

    def test_job_matching_production_methods_do_not_accept_expected_outputs(self):
        score_parameters = inspect.signature(
            CorrectJobMatchingSystem.score_job
        ).parameters
        decision_parameters = inspect.signature(
            CorrectJobMatchingSystem.decide_next_action
        ).parameters

        self.assertNotIn("expected_score_bucket", score_parameters)
        self.assertNotIn("expected_action", decision_parameters)


if __name__ == "__main__":
    unittest.main()

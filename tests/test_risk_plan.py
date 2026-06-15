import json
import unittest

from flowguard import Workflow
from flowguard.plan import FlowGuardCheckPlan, ScenarioMatrixConfig
from flowguard.risk import RiskIntent, RiskProfile, SkippedCheck


class Block:
    name = "Block"

    def apply(self, input_obj, state):
        return ()


class RiskPlanTests(unittest.TestCase):
    def test_risk_intent_serializes_failure_mode_brief(self):
        intent = RiskIntent(
            failure_modes=("duplicate side effect",),
            protected_error_classes=("duplicate_side_effect",),
            protected_harms=("double user notification",),
            must_model_state=("sent_notifications",),
            must_model_side_effects=("send_notification",),
            completion_evidence=("provider_receipt",),
            adversarial_inputs=("same request twice",),
            hard_invariants=("at most one notification per request",),
            known_bad_cases=("retry_sends_twice",),
            used_template_ids=("side_effect_at_most_once",),
            blindspots=("real email provider retries are not replayed",),
        )

        payload = intent.to_dict()

        self.assertEqual(["duplicate side effect"], payload["failure_modes"])
        self.assertEqual(["duplicate_side_effect"], payload["protected_error_classes"])
        self.assertEqual(["provider_receipt"], payload["completion_evidence"])
        self.assertEqual(["retry_sends_twice"], payload["known_bad_cases"])
        self.assertEqual(["side_effect_at_most_once"], payload["used_template_ids"])
        self.assertEqual([], payload["validation_warnings"])
        self.assertIn("duplicate side effect", intent.format_text())

    def test_risk_profile_accepts_risk_intent_mapping(self):
        profile = RiskProfile.from_dict(
            {
                "modeled_boundary": "publish handoff",
                "risk_classes": ["side_effect"],
                "risk_intent": {
                    "failure_modes": ["published before approval"],
                    "protected_error_classes": ["premature_publish"],
                    "protected_harms": ["public release with unreviewed artifact"],
                    "must_model_state": ["approval_status", "published_artifacts"],
                    "must_model_side_effects": ["publish_artifact"],
                    "completion_evidence": ["published_artifact_url"],
                    "adversarial_inputs": ["retry after partial publish"],
                    "hard_invariants": ["no publish without approval"],
                    "known_bad_cases": ["publish_without_approval"],
                    "used_template_ids": ["completion_requires_evidence"],
                    "blindspots": ["external host availability is not modeled"],
                },
            }
        )

        self.assertIsInstance(profile.risk_intent, RiskIntent)
        self.assertEqual([], list(profile.validation_warnings))
        self.assertIn("published before approval", profile.format_text())
        self.assertEqual(
            ["published before approval"],
            profile.to_dict()["risk_intent"]["failure_modes"],
        )
        self.assertEqual(
            ["publish_without_approval"],
            profile.to_dict()["risk_intent"]["known_bad_cases"],
        )

    def test_risk_profile_keeps_unknown_risks_as_warning(self):
        profile = RiskProfile(
            modeled_boundary="job matching",
            risk_classes=("deduplication", "custom_policy"),
            skipped_checks=(SkippedCheck("conformance", "no production code yet"),),
            notes="model-level only",
        )

        self.assertEqual(("custom_policy",), profile.unknown_risk_classes)
        self.assertTrue(any("unknown risk_classes" in item for item in profile.validation_warnings))
        self.assertIn("custom_policy", profile.format_text())
        self.assertEqual("job matching", json.loads(profile.to_json_text())["modeled_boundary"])

    def test_risk_profile_from_dict_accepts_skipped_check_dicts(self):
        profile = RiskProfile.from_dict(
            {
                "modeled_boundary": "cache refresh",
                "risk_classes": ["cache"],
                "confidence_goal": "production_conformance",
                "skipped_checks": [
                    {"name": "replay", "reason": "adapter not written", "status": "not_feasible"}
                ],
            }
        )

        self.assertEqual("production_conformance", profile.confidence_goal)
        self.assertEqual("not_feasible", profile.skipped_checks[0].status)

    def test_check_plan_formats_minimal_model_run(self):
        plan = FlowGuardCheckPlan(
            workflow=Workflow((Block(),), name="tiny"),
            initial_states=("empty",),
            external_inputs=("input",),
            risk_profile={
                "modeled_boundary": "tiny flow",
                "risk_classes": ("deduplication",),
            },
            scenario_matrix_config={"max_scenarios": 4},
            template_reuse_review={
                "used_template_ids": ("side_effect_at_most_once",),
                "searched_layers": ("public", "local"),
            },
            template_harvest_review={
                "disposition": "duplicate_linked",
                "linked_template_ids": ("side_effect_at_most_once",),
            },
            minimum_model_contract={
                "protected_error_classes": ("duplicate_side_effect",),
                "modeled_state": ("records",),
                "modeled_side_effects": ("write",),
                "completion_evidence": ("receipt",),
                "known_bad_cases": ("retry_writes_twice",),
            },
            known_bad_proofs=(
                {
                    "case_id": "retry_writes_twice",
                    "protected_error_class": "duplicate_side_effect",
                    "method": "broken_workflow",
                    "expected_failure": "failed",
                    "observed_status": "failed",
                    "observed_failure": "duplicate write invariant failed",
                    "evidence_id": "model:retry_writes_twice",
                },
            ),
        )

        self.assertEqual(1, plan.max_sequence_length)
        self.assertEqual("tiny flow", plan.risk_profile.modeled_boundary)
        self.assertIsInstance(plan.scenario_matrix_config, ScenarioMatrixConfig)
        self.assertEqual(("side_effect_at_most_once",), plan.template_reuse_review.used_template_ids)
        self.assertEqual("duplicate_linked", plan.template_harvest_review.disposition)
        self.assertEqual(("retry_writes_twice",), plan.minimum_model_contract.known_bad_cases)
        self.assertEqual(("retry_writes_twice",), tuple(proof.case_id for proof in plan.known_bad_proofs))
        self.assertIn("workflow: tiny", plan.format_text())
        self.assertIn("template_harvest_review: provided", plan.format_text())
        self.assertIn("known_bad_proofs: 1", plan.format_text())
        self.assertEqual("tiny", plan.to_dict()["workflow"])
        self.assertEqual(
            ["side_effect_at_most_once"],
            plan.to_dict()["template_harvest_review"]["linked_template_ids"],
        )
        self.assertEqual("retry_writes_twice", plan.to_dict()["known_bad_proofs"][0]["case_id"])


if __name__ == "__main__":
    unittest.main()

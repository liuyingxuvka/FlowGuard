import json
import unittest

from flowguard import Workflow
from flowguard.plan import FlowGuardCheckPlan, ScenarioMatrixConfig
from flowguard.risk import RiskProfile, SkippedCheck


class Block:
    name = "Block"

    def apply(self, input_obj, state):
        return ()


class RiskPlanTests(unittest.TestCase):
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
        )

        self.assertEqual(1, plan.max_sequence_length)
        self.assertEqual("tiny flow", plan.risk_profile.modeled_boundary)
        self.assertIsInstance(plan.scenario_matrix_config, ScenarioMatrixConfig)
        self.assertIn("workflow: tiny", plan.format_text())
        self.assertEqual("tiny", plan.to_dict()["workflow"])


if __name__ == "__main__":
    unittest.main()

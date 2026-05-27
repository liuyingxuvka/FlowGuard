import unittest

from flowguard import (
    MATURITY_ACTION_ADD_MODEL_OBLIGATION,
    MATURITY_ACTION_ADD_SAME_CLASS_SCENARIO,
    MATURITY_ACTION_ADD_STATE_FIELD,
    MATURITY_ACTION_DOWNGRADE_CLAIM,
    MATURITY_ACTION_NO_CHANGE,
    MATURITY_ACTION_REATTACH_PARENT_MODEL,
    MATURITY_ACTION_SPLIT_CHILD_MODEL,
    MODEL_MATURATION_DECISION_BLOCKED,
    MODEL_MATURATION_DECISION_CURRENT,
    MODEL_MATURATION_DECISION_SCOPED,
    MODEL_MATURATION_DECISION_UPGRADE_REQUIRED,
    MODEL_MATURATION_SIGNAL_CHILD_BOUNDARY_CHANGED,
    MODEL_MATURATION_SIGNAL_DUPLICATE_PRIMARY_EDGE_PATH,
    MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION,
    MODEL_MATURATION_SIGNAL_SAME_CLASS_MISSING,
    MODEL_MATURATION_SIGNAL_STATE_TOO_COARSE,
    ModelMaturationPlan,
    ModelMaturationSignal,
    review_model_maturation_loop,
)


class ModelMaturationTests(unittest.TestCase):
    def test_no_open_signals_supports_current_model(self):
        report = review_model_maturation_loop(
            ModelMaturationPlan(plan_id="maturity-green", model_id="checkout")
        )

        self.assertTrue(report.ok)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_CURRENT)
        self.assertEqual(report.confidence, "full")
        self.assertEqual(report.recommended_actions, (MATURITY_ACTION_NO_CHANGE,))
        self.assertFalse(report.findings)

    def test_state_too_coarse_requires_model_upgrade_for_routine_claim(self):
        report = review_model_maturation_loop(
            ModelMaturationPlan(
                plan_id="maturity-state",
                model_id="checkout",
                risk_id="risk-state",
                signals=(
                    ModelMaturationSignal(
                        signal_id="sig-state",
                        signal_type=MODEL_MATURATION_SIGNAL_STATE_TOO_COARSE,
                        source_route="model_miss_review",
                        description="runtime evidence used a state branch the model did not represent",
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_UPGRADE_REQUIRED)
        self.assertIn(MATURITY_ACTION_ADD_STATE_FIELD, report.recommended_actions)
        self.assertEqual(report.findings[0].signal_id, "sig-state")
        self.assertEqual(report.findings[0].action, MATURITY_ACTION_ADD_STATE_FIELD)

    def test_full_claim_can_be_scoped_when_model_upgrade_is_still_open(self):
        report = review_model_maturation_loop(
            ModelMaturationPlan(
                plan_id="maturity-scoped",
                model_id="checkout",
                risk_id="risk-same-class",
                require_full_closure=True,
                allow_scoped_claim=True,
                signals=(
                    ModelMaturationSignal(
                        signal_id="sig-same-class",
                        signal_type=MODEL_MATURATION_SIGNAL_SAME_CLASS_MISSING,
                        source_route="model_miss_review",
                    ),
                ),
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_SCOPED)
        self.assertEqual(report.confidence, "scoped")
        self.assertIn("sig-same-class", report.scoped_signal_ids)
        self.assertIn(MATURITY_ACTION_ADD_SAME_CLASS_SCENARIO, report.recommended_actions)
        self.assertIn(MATURITY_ACTION_DOWNGRADE_CLAIM, report.recommended_actions)

    def test_full_claim_blocks_when_scoped_claim_is_not_allowed(self):
        report = review_model_maturation_loop(
            ModelMaturationPlan(
                plan_id="maturity-blocked",
                model_id="checkout",
                require_full_closure=True,
                allow_scoped_claim=False,
                signals=(
                    ModelMaturationSignal(
                        signal_id="sig-same-class",
                        signal_type=MODEL_MATURATION_SIGNAL_SAME_CLASS_MISSING,
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(report.decision, MODEL_MATURATION_DECISION_BLOCKED)
        self.assertEqual(report.confidence, "blocked")

    def test_mesh_signals_route_to_parent_and_child_model_actions(self):
        report = review_model_maturation_loop(
            ModelMaturationPlan(
                plan_id="maturity-mesh",
                model_id="parent",
                signals=(
                    ModelMaturationSignal(
                        signal_id="sig-child-boundary",
                        signal_type=MODEL_MATURATION_SIGNAL_CHILD_BOUNDARY_CHANGED,
                        source_route="model_mesh",
                    ),
                    ModelMaturationSignal(
                        signal_id="sig-duplicate-edge",
                        signal_type=MODEL_MATURATION_SIGNAL_DUPLICATE_PRIMARY_EDGE_PATH,
                        source_route="model_test_alignment",
                    ),
                ),
            )
        )

        self.assertIn(MATURITY_ACTION_REATTACH_PARENT_MODEL, report.recommended_actions)
        self.assertIn(MATURITY_ACTION_SPLIT_CHILD_MODEL, report.recommended_actions)

    def test_missing_model_obligation_points_back_to_model_before_tests(self):
        report = review_model_maturation_loop(
            ModelMaturationPlan(
                plan_id="maturity-obligation",
                model_id="checkout",
                signals=(
                    ModelMaturationSignal(
                        signal_id="sig-obligation",
                        signal_type=MODEL_MATURATION_SIGNAL_MISSING_MODEL_OBLIGATION,
                        source_route="model_test_alignment",
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn(MATURITY_ACTION_ADD_MODEL_OBLIGATION, report.recommended_actions)
        self.assertNotIn(MATURITY_ACTION_DOWNGRADE_CLAIM, report.recommended_actions)

    def test_signal_can_override_default_action(self):
        report = review_model_maturation_loop(
            ModelMaturationPlan(
                plan_id="maturity-override",
                model_id="checkout",
                signals=(
                    ModelMaturationSignal(
                        signal_id="sig-custom",
                        signal_type=MODEL_MATURATION_SIGNAL_STATE_TOO_COARSE,
                        suggested_actions=(MATURITY_ACTION_ADD_MODEL_OBLIGATION,),
                    ),
                ),
            )
        )

        self.assertIn(MATURITY_ACTION_ADD_MODEL_OBLIGATION, report.recommended_actions)
        self.assertNotIn(MATURITY_ACTION_ADD_STATE_FIELD, report.recommended_actions)

    def test_report_formats_human_readable_summary(self):
        report = review_model_maturation_loop(
            ModelMaturationPlan(
                plan_id="maturity-text",
                model_id="checkout",
                signals=(
                    ModelMaturationSignal(
                        signal_id="sig-state",
                        signal_type=MODEL_MATURATION_SIGNAL_STATE_TOO_COARSE,
                    ),
                ),
            )
        )

        text = report.format_text()
        self.assertIn("FlowGuard model maturation loop", text)
        self.assertIn(MATURITY_ACTION_ADD_STATE_FIELD, text)
        self.assertIn("model_upgrade_required", text)


if __name__ == "__main__":
    unittest.main()

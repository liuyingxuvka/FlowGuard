import json
import unittest

from flowguard import (
    MODEL_ANGLE_ACTION_ADD_CHILD_MODEL,
    MODEL_ANGLE_ACTION_EXTEND_EXISTING,
    MODEL_ANGLE_ACTION_NEEDS_HUMAN_REVIEW,
    MODEL_ANGLE_ACTION_REUSE_EXISTING,
    MODEL_ANGLE_CONFIDENCE_BLOCKED,
    MODEL_ANGLE_CONFIDENCE_FULL,
    MODEL_ANGLE_CONFIDENCE_SCOPED,
    MODEL_ANGLE_DECISION_BLOCKED,
    MODEL_ANGLE_DECISION_READY,
    MODEL_ANGLE_DECISION_SCOPED,
    MODEL_ANGLE_ROUTE_AGENT_WORKFLOW_REHEARSAL,
    MODEL_ANGLE_ROUTE_MODEL_MESH,
    MODEL_ANGLE_ROUTE_MODEL_MATURATION,
    ModelAngleDeliberation,
    review_model_angle_deliberations,
)


def resolved_angle(**overrides):
    values = {
        "angle_id": "angle:route",
        "angle_name": "Route ownership",
        "trigger_observation": "Existing modeled system with ambiguous owner route.",
        "current_model_sees": "Existing preflight sees the route owner.",
        "current_model_misses": "It may miss whether a new model angle is needed.",
        "failure_if_ignored": "The final claim can hide a missing model boundary.",
        "candidate_action": MODEL_ANGLE_ACTION_EXTEND_EXISTING,
        "existing_model_ids": ("existing_model_preflight",),
        "proposed_model_boundary": "Add open-ended model-angle rows to the preflight.",
        "owner_route_hint": MODEL_ANGLE_ROUTE_MODEL_MATURATION,
        "evidence_needed": ("unit:test_model_angle",),
        "resolved": True,
    }
    values.update(overrides)
    return ModelAngleDeliberation(**values)


def finding_codes(report):
    return {finding.code for finding in report.findings}


class ModelAngleDeliberationTests(unittest.TestCase):
    def test_resolved_model_angle_supports_full_confidence(self):
        report = review_model_angle_deliberations(
            "review:resolved",
            (resolved_angle(),),
            require_review=True,
            broad_claim=True,
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(MODEL_ANGLE_DECISION_READY, report.decision)
        self.assertEqual(MODEL_ANGLE_CONFIDENCE_FULL, report.confidence)
        self.assertTrue(report.supports_full_confidence())
        self.assertIn("model_angle_review_report", json.loads(report.to_json_text())["artifact_type"])

    def test_missing_required_review_blocks_broad_claim(self):
        report = review_model_angle_deliberations(
            "review:missing",
            (),
            require_review=True,
            broad_claim=True,
        )

        self.assertFalse(report.ok)
        self.assertEqual(MODEL_ANGLE_DECISION_BLOCKED, report.decision)
        self.assertEqual(MODEL_ANGLE_CONFIDENCE_BLOCKED, report.confidence)
        self.assertIn("missing_model_angle_review", finding_codes(report))

    def test_unresolved_required_angle_is_scoped_until_broad_claim(self):
        light = review_model_angle_deliberations(
            "review:light",
            (resolved_angle(resolved=False),),
            require_review=True,
            broad_claim=False,
        )
        broad = review_model_angle_deliberations(
            "review:broad",
            (resolved_angle(resolved=False),),
            require_review=True,
            broad_claim=True,
        )

        self.assertTrue(light.ok, light.format_text())
        self.assertEqual(MODEL_ANGLE_DECISION_SCOPED, light.decision)
        self.assertEqual(MODEL_ANGLE_CONFIDENCE_SCOPED, light.confidence)
        self.assertFalse(broad.ok)
        self.assertEqual(("angle:route",), broad.unresolved_angle_ids)
        self.assertIn("unresolved_required_model_angle", finding_codes(broad))

    def test_candidate_actions_choose_owner_routes(self):
        child = resolved_angle(
            angle_id="angle:child",
            candidate_action=MODEL_ANGLE_ACTION_ADD_CHILD_MODEL,
            owner_route_hint="",
        )
        human = resolved_angle(
            angle_id="angle:human",
            candidate_action=MODEL_ANGLE_ACTION_NEEDS_HUMAN_REVIEW,
            owner_route_hint="",
            open_questions=("Which product policy owns this behavior?",),
        )
        reuse = resolved_angle(
            angle_id="angle:reuse",
            candidate_action=MODEL_ANGLE_ACTION_REUSE_EXISTING,
            owner_route_hint="",
        )

        self.assertEqual(MODEL_ANGLE_ROUTE_MODEL_MESH, child.owner_route())
        self.assertEqual(MODEL_ANGLE_ROUTE_AGENT_WORKFLOW_REHEARSAL, human.owner_route())
        self.assertEqual(MODEL_ANGLE_ROUTE_MODEL_MATURATION, reuse.owner_route())

    def test_invalid_or_underexplained_rows_are_visible(self):
        report = review_model_angle_deliberations(
            "review:broken",
            (
                ModelAngleDeliberation(
                    "angle:broken",
                    "",
                    candidate_action="invented_action",
                ),
            ),
            require_review=True,
            broad_claim=True,
        )

        codes = finding_codes(report)
        self.assertFalse(report.ok)
        self.assertIn("missing_angle_name", codes)
        self.assertIn("invalid_model_angle_action", codes)
        self.assertIn("missing_current_model_sees", codes)
        self.assertIn("missing_current_model_misses", codes)
        self.assertIn("missing_failure_if_ignored", codes)


if __name__ == "__main__":
    unittest.main()

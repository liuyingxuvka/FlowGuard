import unittest

from flowguard import (
    CodeStructureRecommendation,
    TargetModuleRecommendation,
    review_code_structure_recommendation,
)


def module(module_id: str, **kwargs) -> TargetModuleRecommendation:
    defaults = {
        "rationale": f"{module_id} owns a cohesive model-derived boundary",
        "validation_boundaries": ("focused test",),
    }
    defaults.update(kwargs)
    return TargetModuleRecommendation(module_id, **defaults)


class CodeStructureRecommendationTests(unittest.TestCase):
    def test_complete_recommendation_can_continue(self):
        recommendation = CodeStructureRecommendation(
            "checkout-structure",
            source_model_id="checkout-functional-model",
            source_model_path=".flowguard/checkout/model.py",
            parent_module_id="checkout",
            target_modules=(
                module("orchestrator", owns_function_blocks=("RouteCheckout",)),
                module(
                    "effects",
                    owns_function_blocks=("PersistOrder",),
                    owns_state=("orders",),
                    owns_side_effects=("write_order",),
                ),
            ),
            function_block_map=(
                ("RouteCheckout", "orchestrator"),
                ("PersistOrder", "effects"),
            ),
            state_owner_map=(("orders", "effects"),),
            side_effect_owner_map=(("write_order", "effects"),),
            validation_boundaries=("model scenario replay",),
            rationale="the functional model separates routing from durable effects",
        )

        report = review_code_structure_recommendation(recommendation)

        self.assertTrue(report.ok)
        self.assertEqual(0, report.blocker_count())

    def test_missing_model_source_blocks(self):
        recommendation = CodeStructureRecommendation(
            "checkout-structure",
            source_model_id="",
            parent_module_id="checkout",
            target_modules=(module("effects"),),
            function_block_map=(("PersistOrder", "effects"),),
            validation_boundaries=("model scenario replay",),
            rationale="effects own durable writes",
        )

        report = review_code_structure_recommendation(recommendation)

        self.assertFalse(report.ok)
        self.assertIn("missing_source_model", [finding.code for finding in report.findings])

    def test_unregistered_and_duplicate_owners_block(self):
        recommendation = CodeStructureRecommendation(
            "checkout-structure",
            source_model_id="checkout-functional-model",
            parent_module_id="checkout",
            target_modules=(module("effects"),),
            function_block_map=(
                ("PersistOrder", "effects"),
                ("PersistOrder", "other"),
            ),
            state_owner_map=(("orders", "other"),),
            side_effect_owner_map=(("write_order", "other"),),
            validation_boundaries=("model scenario replay",),
            rationale="effects own durable writes",
        )

        report = review_code_structure_recommendation(recommendation)
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertIn("function_block_owner_not_registered", codes)
        self.assertIn("duplicate_function_block_owner", codes)
        self.assertIn("state_owner_not_registered", codes)
        self.assertIn("side_effect_owner_not_registered", codes)

    def test_missing_rationale_and_validation_plan_block(self):
        recommendation = CodeStructureRecommendation(
            "checkout-structure",
            source_model_id="checkout-functional-model",
            parent_module_id="checkout",
            target_modules=(TargetModuleRecommendation("effects"),),
            function_block_map=(("PersistOrder", "effects"),),
        )

        report = review_code_structure_recommendation(recommendation)
        codes = {finding.code for finding in report.findings}

        self.assertFalse(report.ok)
        self.assertIn("missing_validation_plan", codes)
        self.assertIn("missing_structure_rationale", codes)
        self.assertIn("missing_module_rationale", codes)


if __name__ == "__main__":
    unittest.main()

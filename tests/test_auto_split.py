import unittest

from flowguard import (
    AUTO_SPLIT_DECISION_FULL,
    AUTO_SPLIT_DECISION_MODEL_REQUIRED,
    AUTO_SPLIT_DECISION_NOT_REQUIRED,
    AUTO_SPLIT_DECISION_SCOPED,
    AUTO_SPLIT_DECISION_TARGET_REQUIRED,
    AUTO_SPLIT_DECISION_TEST_REQUIRED,
    AUTO_SPLIT_TARGET_MODEL,
    AUTO_SPLIT_TARGET_TEST,
    AutoSplitCandidate,
    AutoSplitPlan,
    AutoSplitPolicy,
    review_auto_mesh_splits,
)


def codes(report):
    return {finding.code for finding in report.findings}


class AutoSplitTests(unittest.TestCase):
    def test_small_direct_evidence_does_not_require_mesh(self):
        report = review_auto_mesh_splits(
            AutoSplitPlan(
                "small",
                candidates=(
                    AutoSplitCandidate(
                        "small-model",
                        AUTO_SPLIT_TARGET_MODEL,
                        observed_state_count=25,
                    ),
                ),
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(AUTO_SPLIT_DECISION_NOT_REQUIRED, report.decision)

    def test_oversized_model_requires_model_mesh_and_derivation(self):
        report = review_auto_mesh_splits(
            AutoSplitPlan(
                "large-model",
                candidates=(
                    AutoSplitCandidate(
                        "checkout-model",
                        AUTO_SPLIT_TARGET_MODEL,
                        source_model_id="checkout",
                        observed_state_count=10_001,
                        suggested_child_ids=("payment", "fulfillment"),
                        covered_partition_item_ids=("pay", "ship"),
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(AUTO_SPLIT_DECISION_MODEL_REQUIRED, report.decision)
        self.assertIn("auto_model_split_not_current", codes(report))
        self.assertEqual(("checkout-model",), report.required_model_candidate_ids)
        self.assertEqual("checkout", report.model_target_split_derivations[0].source_model_id)

    def test_pending_budgeted_model_requires_model_mesh(self):
        report = review_auto_mesh_splits(
            AutoSplitPlan(
                "pending-model",
                candidates=(
                    AutoSplitCandidate(
                        "budgeted",
                        AUTO_SPLIT_TARGET_MODEL,
                        processed_state_count=10_000,
                        pending_state_count=1,
                        suggested_child_ids=("child",),
                        covered_partition_item_ids=("branch",),
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("auto_model_split_not_current", codes(report))

    def test_slow_or_broad_test_requires_test_mesh_and_derivation(self):
        report = review_auto_mesh_splits(
            AutoSplitPlan(
                "slow-test",
                candidates=(
                    AutoSplitCandidate(
                        "full-pytest",
                        AUTO_SPLIT_TARGET_TEST,
                        duration_seconds=301,
                        covered_obligation_count=6,
                        suggested_child_ids=("unit", "integration"),
                        covered_partition_item_ids=("fast", "slow"),
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(AUTO_SPLIT_DECISION_TEST_REQUIRED, report.decision)
        self.assertIn("auto_test_split_not_current", codes(report))
        self.assertEqual(("full-pytest",), report.required_test_candidate_ids)
        self.assertEqual(("unit", "integration"), report.test_target_split_derivations[0].target_suite_ids)

    def test_progress_only_background_test_requires_test_mesh(self):
        report = review_auto_mesh_splits(
            AutoSplitPlan(
                "progress",
                candidates=(
                    AutoSplitCandidate(
                        "background",
                        AUTO_SPLIT_TARGET_TEST,
                        background=True,
                        progress_only=True,
                        suggested_child_ids=("unit",),
                        covered_partition_item_ids=("unit",),
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(AUTO_SPLIT_DECISION_TEST_REQUIRED, report.decision)

    def test_missing_target_derivation_blocks_before_parent_confidence(self):
        report = review_auto_mesh_splits(
            AutoSplitPlan(
                "missing-target",
                candidates=(AutoSplitCandidate("big", AUTO_SPLIT_TARGET_MODEL, observed_state_count=20_000),),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(AUTO_SPLIT_DECISION_TARGET_REQUIRED, report.decision)
        self.assertIn("missing_auto_split_target_derivation", codes(report))

    def test_current_scoped_split_downgrades_without_blocking(self):
        report = review_auto_mesh_splits(
            AutoSplitPlan(
                "scoped",
                candidates=(
                    AutoSplitCandidate(
                        "full-suite",
                        AUTO_SPLIT_TARGET_TEST,
                        test_count=800,
                        suggested_child_ids=("unit", "release"),
                        covered_partition_item_ids=("unit", "release"),
                        split_review_current=True,
                        split_confidence="scoped",
                        scoped_reasons=("release shard deferred",),
                    ),
                ),
            )
        )

        self.assertTrue(report.ok)
        self.assertEqual(AUTO_SPLIT_DECISION_SCOPED, report.decision)
        self.assertIn("auto_test_split_scoped_confidence", codes(report))

    def test_thresholds_are_configurable(self):
        report = review_auto_mesh_splits(
            AutoSplitPlan(
                "custom",
                policy=AutoSplitPolicy(model_state_threshold=100),
                candidates=(AutoSplitCandidate("model", AUTO_SPLIT_TARGET_MODEL, observed_state_count=101),),
            )
        )

        self.assertFalse(report.ok)
        self.assertEqual(AUTO_SPLIT_DECISION_TARGET_REQUIRED, report.decision)


if __name__ == "__main__":
    unittest.main()

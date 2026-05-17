import unittest

from flowguard import (
    EVIDENCE_ABSTRACT_GREEN,
    EVIDENCE_CONFORMANCE_GREEN,
    TestMeshPlan,
    TestPartitionItem,
    TestSuiteEvidence,
    TestTargetSplitDerivation,
    review_test_mesh,
)


def suite(suite_id, **kwargs):
    defaults = {
        "result_status": "passed",
        "evidence_tier": EVIDENCE_ABSTRACT_GREEN,
        "test_count": 1,
        "selected_count": 1,
    }
    defaults.update(kwargs)
    return TestSuiteEvidence(suite_id, **defaults)


def target(source_model_id, suite_ids, item_ids, *, state=False, side_effect=False):
    return TestTargetSplitDerivation(
        source_model_id,
        target_suite_ids=tuple(suite_ids),
        covered_partition_item_ids=tuple(item_ids),
        state_owner_fields=("state_owner_map",) if state else (),
        side_effect_owner_fields=("side_effect_owner_map",) if side_effect else (),
        rationale="derived from parent FlowGuard validation structure model",
    )


class TestMeshTests(unittest.TestCase):
    def test_complete_test_mesh_can_continue(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(
                TestPartitionItem("controller", owner_suite_id="controller"),
                TestPartitionItem("packets", owner_suite_id="packets"),
            ),
            child_suites=(suite("controller"), suite("packets")),
            target_split_derivation=target(
                "router-runtime-validation",
                ("controller", "packets"),
                ("controller", "packets"),
            ),
        )

        report = review_test_mesh(plan)

        self.assertTrue(report.ok)
        self.assertEqual("test_mesh_green_can_continue", report.decision)
        self.assertEqual([], report.to_dict()["findings"])
        self.assertIn("flowguard test mesh", report.format_text())

    def test_missing_partition_owner_blocks_parent_green(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(TestPartitionItem("startup", owner_suite_id=""),),
            child_suites=(suite("controller"),),
            target_split_derivation=target("router-runtime-validation", ("controller",), ("startup",)),
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("coverage_gap_blocked", report.decision)
        self.assertIn("coverage_gap", [finding.code for finding in report.findings])

    def test_unregistered_partition_owner_blocks_parent_green(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(TestPartitionItem("startup", owner_suite_id="startup-daemon"),),
            child_suites=(suite("controller"),),
            target_split_derivation=target("router-runtime-validation", ("controller",), ("startup",)),
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("coverage_gap_blocked", report.decision)

    def test_duplicate_partition_state_and_side_effect_ownership_block(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(
                TestPartitionItem("route-state", owner_suite_id="route-a"),
                TestPartitionItem("route-state", owner_suite_id="route-b"),
            ),
            child_suites=(
                suite("route-a", owns_state=("run_state",), owns_side_effects=("write_ledger",)),
                suite("route-b", owns_state=("run_state",), owns_side_effects=("write_ledger",)),
            ),
            target_split_derivation=target(
                "router-runtime-validation",
                ("route-a", "route-b"),
                ("route-state",),
                state=True,
                side_effect=True,
            ),
        )

        report = review_test_mesh(plan)
        codes = [finding.code for finding in report.findings]

        self.assertFalse(report.ok)
        self.assertEqual("ownership_conflict", report.decision)
        self.assertIn("duplicate_partition_owner", codes)
        self.assertIn("duplicate_state_owner", codes)
        self.assertIn("duplicate_side_effect_owner", codes)

    def test_background_progress_without_exit_artifact_is_incomplete(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(TestPartitionItem("startup", owner_suite_id="startup"),),
            child_suites=(
                suite(
                    "startup",
                    background=True,
                    has_exit_artifact=False,
                    has_result_artifact=False,
                    progress_only=True,
                ),
            ),
            target_split_derivation=target("router-runtime-validation", ("startup",), ("startup",)),
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("background_incomplete", report.decision)
        self.assertIn("background_incomplete", [finding.code for finding in report.findings])

    def test_failed_timeout_and_stale_suites_are_not_parent_green(self):
        for status, decision in (("failed", "test_failure_blocked"), ("timeout", "test_timeout_blocked")):
            with self.subTest(status=status):
                plan = TestMeshPlan(
                    parent_suite_id="router-runtime",
                    partition_items=(TestPartitionItem(status, owner_suite_id=status),),
                    child_suites=(suite(status, result_status=status),),
                    target_split_derivation=target("router-runtime-validation", (status,), (status,)),
                )
                self.assertEqual(decision, review_test_mesh(plan).decision)

        stale = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(TestPartitionItem("controller", owner_suite_id="controller"),),
            child_suites=(suite("controller", evidence_current=False, stale_reasons=("source_changed",)),),
            target_split_derivation=target("router-runtime-validation", ("controller",), ("controller",)),
        )
        self.assertEqual("stale_test_evidence", review_test_mesh(stale).decision)

    def test_hidden_skipped_tests_are_not_accepted(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(TestPartitionItem("cards", owner_suite_id="cards"),),
            child_suites=(suite("cards", skipped_count=2, skipped_visible=False),),
            target_split_derivation=target("router-runtime-validation", ("cards",), ("cards",)),
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("hidden_skipped_tests", report.decision)

    def test_evidence_tier_below_required_is_visible(self):
        plan = TestMeshPlan(
            parent_suite_id="release",
            required_evidence_tier=EVIDENCE_CONFORMANCE_GREEN,
            partition_items=(TestPartitionItem("publish", owner_suite_id="publish"),),
            child_suites=(suite("publish", evidence_tier=EVIDENCE_ABSTRACT_GREEN),),
            target_split_derivation=target("release-validation", ("publish",), ("publish",)),
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("insufficient_evidence", report.decision)
        self.assertIn("insufficient_evidence_tier", [finding.code for finding in report.findings])

    def test_routine_scope_can_defer_release_only_suite(self):
        plan = TestMeshPlan(
            parent_suite_id="validation",
            decision_scope="routine",
            partition_items=(TestPartitionItem("unit", owner_suite_id="unit"),),
            child_suites=(
                suite("unit"),
                suite("full-release", layer="release", release_required=True, result_status="not_run"),
            ),
            target_split_derivation=target("validation-model", ("unit", "full-release"), ("unit",)),
        )

        report = review_test_mesh(plan)

        self.assertTrue(report.ok)
        self.assertEqual("test_mesh_green_can_continue", report.decision)
        self.assertEqual(("full-release",), report.release_obligations)
        self.assertIn("release_suite_deferred", [finding.code for finding in report.findings])

    def test_release_scope_requires_release_suite_current(self):
        plan = TestMeshPlan(
            parent_suite_id="validation",
            decision_scope="release",
            partition_items=(TestPartitionItem("unit", owner_suite_id="unit"),),
            child_suites=(
                suite("unit"),
                suite("full-release", layer="release", release_required=True, result_status="not_run"),
            ),
            target_split_derivation=target("validation-model", ("unit", "full-release"), ("unit",)),
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("missing_release_evidence", report.decision)
        self.assertIn("release_suite_not_current", [finding.code for finding in report.findings])

    def test_missing_target_split_derivation_blocks_parent_green(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(TestPartitionItem("controller", owner_suite_id="controller"),),
            child_suites=(suite("controller"),),
        )

        report = review_test_mesh(plan)

        self.assertFalse(report.ok)
        self.assertEqual("target_split_derivation_required", report.decision)
        self.assertIn("missing_target_split_derivation", [finding.code for finding in report.findings])

    def test_incomplete_target_split_derivation_blocks_parent_green(self):
        plan = TestMeshPlan(
            parent_suite_id="router-runtime",
            partition_items=(
                TestPartitionItem("controller", owner_suite_id="controller"),
                TestPartitionItem("packets", owner_suite_id="packets"),
            ),
            child_suites=(suite("controller"), suite("packets")),
            target_split_derivation=TestTargetSplitDerivation(
                "router-runtime-validation",
                target_suite_ids=("controller", "unknown"),
                covered_partition_item_ids=("controller",),
                rationale="derived from a partial validation model",
            ),
        )

        report = review_test_mesh(plan)
        codes = [finding.code for finding in report.findings]

        self.assertFalse(report.ok)
        self.assertEqual("target_split_derivation_required", report.decision)
        self.assertIn("unknown_target_suite", codes)
        self.assertIn("incomplete_target_suites", codes)
        self.assertIn("incomplete_target_split_coverage", codes)


if __name__ == "__main__":
    unittest.main()

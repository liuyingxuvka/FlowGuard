import unittest

from flowguard import (
    EVIDENCE_ABSTRACT_GREEN,
    TEST_LAYER_CONTRACT_COMBINATION_SHARD,
    TestMeshPlan,
    TestPartitionItem,
    TestSuiteEvidence,
    TestTargetSplitDerivation,
    review_test_mesh,
)


class PrimaryPathAuthorityReleaseGateMatrixTests(unittest.TestCase):
    def test_test_mesh_consumes_primary_path_shard(self):
        shard_id = "contract_shard:primary_path_authority:core_no_fallback"
        report = review_test_mesh(
            TestMeshPlan(
                parent_suite_id="primary-path-authority",
                partition_items=(
                    TestPartitionItem(shard_id, item_type="contract_coverage_shard", owner_suite_id="ppa-shards"),
                ),
                child_suites=(
                    TestSuiteEvidence(
                        "ppa-shards",
                        layer=TEST_LAYER_CONTRACT_COMBINATION_SHARD,
                        result_status="passed",
                        evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                        test_count=1,
                        selected_count=1,
                        owned_coverage_shard_ids=(shard_id,),
                    ),
                ),
                target_split_derivation=TestTargetSplitDerivation(
                    "primary-path-authority-model",
                    target_suite_ids=("ppa-shards",),
                    covered_partition_item_ids=(shard_id,),
                    rationale="derived from primary path authority coverage universe",
                ),
                required_coverage_shard_ids=(shard_id,),
            )
        )

        self.assertTrue(report.ok, report.format_text())

if __name__ == "__main__":
    unittest.main()

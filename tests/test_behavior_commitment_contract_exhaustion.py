import unittest

from flowguard import (
    BEHAVIOR_COMMITMENT_ORACLE_ID,
    behavior_commitment_contract_exhaustion_plan,
    default_behavior_commitment_axes,
    default_behavior_commitment_interaction_groups,
    contract_exhaustion_to_coverage_receipt_ids,
    contract_exhaustion_to_test_mesh_shard_ids,
    review_contract_exhaustion,
)


class BehaviorCommitmentContractExhaustionTests(unittest.TestCase):
    def test_default_universe_generates_cases_shards_and_receipts(self):
        report = review_contract_exhaustion(
            behavior_commitment_contract_exhaustion_plan(max_combinations=50000)
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertIn("contract_coverage:behavior_commitment_ledger", contract_exhaustion_to_coverage_receipt_ids(report))
        self.assertIn(
            "contract_shard:behavior_commitment_ledger:full_inventory_mapping",
            contract_exhaustion_to_test_mesh_shard_ids(report),
        )
        self.assertTrue(any("path_sensitive_ppa_handoff" in case.case_id for case in report.generated_cases))
        self.assertTrue(all(case.oracle_id == BEHAVIOR_COMMITMENT_ORACLE_ID for case in report.generated_cases))

    def test_change_mode_source_freshness_model_sync_and_miss_axes_are_declared(self):
        axis_ids = {axis.axis_id for axis in default_behavior_commitment_axes()}
        self.assertIn("change_mode", axis_ids)
        self.assertIn("source_freshness_state", axis_ids)
        self.assertIn("replacement_state", axis_ids)
        self.assertIn("model_sync_state", axis_ids)
        self.assertIn("test_mesh_state", axis_ids)
        self.assertIn("miss_origin_state", axis_ids)

    def test_dcar_groups_include_change_freshness_replacement_and_model_miss_backfeed(self):
        group_ids = {group.group_id for group in default_behavior_commitment_interaction_groups()}
        self.assertIn("change_mode_source_freshness", group_ids)
        self.assertIn("replacement_model_sync", group_ids)
        self.assertIn("model_miss_backfeed", group_ids)


if __name__ == "__main__":
    unittest.main()

import unittest

from flowguard import (
    contract_exhaustion_to_coverage_receipt_ids,
    contract_exhaustion_to_test_mesh_shard_ids,
    PPA_CONTRACT_ORACLE_PRIMARY_FAILURE,
    default_primary_path_authority_axes,
    default_primary_path_authority_interaction_groups,
    primary_path_authority_contract_exhaustion_plan,
    review_contract_exhaustion,
)


class PrimaryPathAuthorityContractExhaustionTests(unittest.TestCase):
    def test_identity_inventory_path_selection_and_proof_axes_are_declared(self):
        axis_ids = {axis.axis_id for axis in default_primary_path_authority_axes()}
        self.assertIn("business_intent_identity", axis_ids)
        self.assertIn("primary_path_selection", axis_ids)
        self.assertIn("candidate_inventory_state", axis_ids)
        self.assertIn("runtime_proof_state", axis_ids)

        group_ids = {
            group.group_id for group in default_primary_path_authority_interaction_groups()
        }
        self.assertIn("stable_intent_authority", group_ids)
        self.assertIn("material_runtime_proof", group_ids)
        self.assertIn("parallel_success_and_omission", group_ids)

    def test_default_universe_generates_cases_shards_and_receipts(self):
        report = review_contract_exhaustion(
            primary_path_authority_contract_exhaustion_plan(max_combinations=50000)
        )

        self.assertTrue(report.ok, report.format_text())
        self.assertIn("contract_coverage:primary_path_authority", contract_exhaustion_to_coverage_receipt_ids(report))
        self.assertIn(
            "contract_shard:primary_path_authority:core_no_fallback",
            contract_exhaustion_to_test_mesh_shard_ids(report),
        )
        self.assertTrue(any("core_no_fallback" in case.case_id for case in report.generated_cases))
        self.assertTrue(all(case.oracle_id == PPA_CONTRACT_ORACLE_PRIMARY_FAILURE for case in report.generated_cases))


if __name__ == "__main__":
    unittest.main()

import unittest

from flowguard import (
    BEHAVIOR_COMMITMENT_ORACLE_ID,
    behavior_commitment_contract_exhaustion_plan,
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


if __name__ == "__main__":
    unittest.main()

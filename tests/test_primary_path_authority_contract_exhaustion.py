import unittest

from flowguard import (
    contract_exhaustion_to_coverage_receipt_ids,
    contract_exhaustion_to_test_mesh_shard_ids,
    PPA_CONTRACT_ORACLE_PRIMARY_FAILURE,
    primary_path_authority_contract_exhaustion_plan,
    review_contract_exhaustion,
)


class PrimaryPathAuthorityContractExhaustionTests(unittest.TestCase):
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

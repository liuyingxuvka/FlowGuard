import unittest

from flowguard import RuntimePathAlignmentPlan, review_runtime_path_alignment
from tests.test_runtime_path_evidence import contract, finding_codes, observation


class PrimaryPathAuthorityRuntimeMatrixTests(unittest.TestCase):
    def test_runtime_silent_fallback_blocks(self):
        report = review_runtime_path_alignment(
            RuntimePathAlignmentPlan(
                "runtime-silent-fallback",
                node_contracts=(
                    contract("validate_order", primary_path_id="submit_order", require_no_fallback=True),
                ),
                observations=(
                    observation(
                        "validate_order",
                        primary_path_id="submit_order",
                        fallback_path_id="legacy_submit_order",
                        primary_failure_id="exception:submit_order",
                        fallback_invoked=True,
                        fallback_returned_success=True,
                    ),
                ),
            )
        )

        codes = finding_codes(report)
        self.assertFalse(report.ok)
        self.assertIn("runtime_path_silent_fallback", codes)
        self.assertIn("runtime_path_fallback_invoked", codes)


if __name__ == "__main__":
    unittest.main()

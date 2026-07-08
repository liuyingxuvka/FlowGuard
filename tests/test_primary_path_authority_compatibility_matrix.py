import unittest

from flowguard import (
    FallbackPathCandidate,
    PrimaryPathAuthorityPlan,
    PPA_CANDIDATE_ALIAS,
    PPA_DISPOSITION_UNKNOWN,
    review_primary_path_authority,
)
from tests.test_primary_path_authority import finding_codes, primary


class PrimaryPathAuthorityCompatibilityMatrixTests(unittest.TestCase):
    def test_unknown_alias_disposition_blocks(self):
        report = review_primary_path_authority(
            PrimaryPathAuthorityPlan(
                "unknown-alias",
                primary_paths=(primary(),),
                fallback_candidates=(
                    FallbackPathCandidate(
                        "orders.submit.alias",
                        fallback_for_path_id="submit_order",
                        candidate_surface=PPA_CANDIDATE_ALIAS,
                        disposition=PPA_DISPOSITION_UNKNOWN,
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("fallback_candidate_unknown_disposition", finding_codes(report))


if __name__ == "__main__":
    unittest.main()

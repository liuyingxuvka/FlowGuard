import unittest

from flowguard import (
    FallbackPathCandidate,
    PrimaryPathAuthorityPlan,
    PPA_BEHAVIOR_RETURN_SUCCESS,
    PPA_CANDIDATE_LEGACY_PATH,
    PPA_DISPOSITION_BLOCK,
    PPA_TRIGGER_PRIMARY_FAILURE,
    review_primary_path_authority,
)
from tests.test_primary_path_authority import finding_codes, primary


class PrimaryPathAuthorityCoreMatrixTests(unittest.TestCase):
    def test_a_failed_b_success_is_rejected(self):
        report = review_primary_path_authority(
            PrimaryPathAuthorityPlan(
                "a-failed-b-success",
                primary_paths=(primary(),),
                fallback_candidates=(
                    FallbackPathCandidate(
                        "orders.submit.legacy-fallback",
                        fallback_for_path_id="submit_order",
                        business_intent="submit order",
                        candidate_surface=PPA_CANDIDATE_LEGACY_PATH,
                        candidate_trigger=PPA_TRIGGER_PRIMARY_FAILURE,
                        candidate_behavior=PPA_BEHAVIOR_RETURN_SUCCESS,
                        invokes_on_primary_failure=True,
                        returns_success_after_primary_failure=True,
                        disposition=PPA_DISPOSITION_BLOCK,
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("primary_failure_masked_by_fallback_success", finding_codes(report))


if __name__ == "__main__":
    unittest.main()

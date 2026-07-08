import unittest

from flowguard import (
    FallbackPathCandidate,
    PrimaryPathAuthorityPlan,
    PPA_AUTHORITY_EXTERNAL_FACADE,
    PPA_BEHAVIOR_WRITE_STATE,
    PPA_CANDIDATE_COMPATIBILITY_FACADE,
    PPA_DISPOSITION_PRESERVE_FACADE,
    review_primary_path_authority,
)
from tests.test_primary_path_authority import finding_codes, primary


class PrimaryPathAuthorityFacadeMatrixTests(unittest.TestCase):
    def test_facade_with_business_logic_blocks(self):
        report = review_primary_path_authority(
            PrimaryPathAuthorityPlan(
                "bad-facade",
                primary_paths=(primary(),),
                fallback_candidates=(
                    FallbackPathCandidate(
                        "orders.submit.v1",
                        fallback_for_path_id="submit_order",
                        candidate_surface=PPA_CANDIDATE_COMPATIBILITY_FACADE,
                        candidate_behavior=PPA_BEHAVIOR_WRITE_STATE,
                        classification=PPA_AUTHORITY_EXTERNAL_FACADE,
                        disposition=PPA_DISPOSITION_PRESERVE_FACADE,
                        compatibility_intent="external API compatibility",
                        evidence_refs=("test:facade",),
                        state_writes=("order_status",),
                    ),
                ),
            )
        )

        self.assertFalse(report.ok)
        self.assertIn("facade_contains_business_logic", finding_codes(report))


if __name__ == "__main__":
    unittest.main()

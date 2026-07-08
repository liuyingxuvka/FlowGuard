import unittest

from flowguard import (
    FallbackPathCandidate,
    PrimaryPathAuthorityPlan,
    PPA_BEHAVIOR_READ_STATE,
    PPA_CANDIDATE_OLD_FIELD,
    PPA_DISPOSITION_UNKNOWN,
    PPA_TRIGGER_MISSING_FIELD,
    review_primary_path_authority,
)
from tests.test_primary_path_authority import finding_codes, primary


class PrimaryPathAuthorityFieldMatrixTests(unittest.TestCase):
    def test_old_field_fallback_blocks(self):
        report = review_primary_path_authority(
            PrimaryPathAuthorityPlan(
                "old-field-fallback",
                primary_paths=(primary(),),
                fallback_candidates=(
                    FallbackPathCandidate(
                        "orders.old_status",
                        fallback_for_path_id="submit_order",
                        candidate_surface=PPA_CANDIDATE_OLD_FIELD,
                        candidate_trigger=PPA_TRIGGER_MISSING_FIELD,
                        candidate_behavior=PPA_BEHAVIOR_READ_STATE,
                        returns_success_after_primary_failure=True,
                        disposition=PPA_DISPOSITION_UNKNOWN,
                    ),
                ),
            )
        )

        codes = finding_codes(report)
        self.assertFalse(report.ok)
        self.assertIn("fallback_candidate_unknown_disposition", codes)
        self.assertIn("old_field_or_backup_cache_masks_primary_failure", codes)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

import flowguard


EXPECTED_PORTABLE_COHORT = (
    "PORTABLE_MODEL_SCHEMA_VERSION",
    "PORTABLE_REFINEMENT_SCHEMA_VERSION",
    "PortableModel",
    "RefinementBinding",
    "load_portable_model",
    "validate_portable_model",
    "execute_portable_model",
    "check_portable_model",
    "check_refinement",
    "check_composition",
)


class PublicApiSurfaceTests(unittest.TestCase):
    def test_portable_verification_cohort_has_one_registry_owner(self):
        self.assertEqual(EXPECTED_PORTABLE_COHORT, flowguard.PORTABLE_VERIFICATION_API)
        self.assertEqual(EXPECTED_PORTABLE_COHORT, flowguard.API_SURFACE["portable_verification"])

    def test_every_declared_portable_name_is_public_and_importable(self):
        for name in EXPECTED_PORTABLE_COHORT:
            self.assertIn(name, flowguard.__all__)
            self.assertTrue(hasattr(flowguard, name), name)

    def test_internal_checker_helpers_are_not_public(self):
        for name in ("_tarjan", "_eventual_failure", "_fairness_forces_escape"):
            self.assertNotIn(name, flowguard.__all__)


if __name__ == "__main__":
    unittest.main()

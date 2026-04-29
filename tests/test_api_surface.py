import unittest

import flowguard


class ApiSurfaceTests(unittest.TestCase):
    def test_api_surface_groups_are_exported(self):
        self.assertEqual(
            set(flowguard.API_SURFACE),
            {"core", "modeling_helpers", "reporting_helpers", "evidence"},
        )

        grouped_names = []
        for group_name, names in flowguard.API_SURFACE.items():
            self.assertIsInstance(names, tuple, group_name)
            self.assertTrue(names, group_name)
            for name in names:
                self.assertIn(name, flowguard.__all__, f"{group_name}:{name}")
                self.assertTrue(hasattr(flowguard, name), f"{group_name}:{name}")
                grouped_names.append(name)

        self.assertEqual(len(grouped_names), len(set(grouped_names)))

    def test_core_group_keeps_minimal_path_visible(self):
        self.assertIn("Workflow", flowguard.CORE_API)
        self.assertIn("Explorer", flowguard.CORE_API)
        self.assertIn("Invariant", flowguard.CORE_API)
        self.assertIn("FunctionResult", flowguard.CORE_API)
        self.assertNotIn("run_model_first_checks", flowguard.CORE_API)

    def test_runner_and_internal_evidence_are_not_core(self):
        self.assertIn("run_model_first_checks", flowguard.REPORTING_HELPER_API)
        self.assertIn("audit_model", flowguard.REPORTING_HELPER_API)
        self.assertIn("build_executable_corpus_report", flowguard.EVIDENCE_API)
        self.assertIn("build_evidence_baseline_report", flowguard.EVIDENCE_API)
        self.assertNotIn("build_executable_corpus_report", flowguard.CORE_API)


if __name__ == "__main__":
    unittest.main()

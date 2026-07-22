import unittest

from examples.bounded_system_composition.benchmark import run_bounded_system_benchmark


class BoundedSystemBenchmarkTests(unittest.TestCase):
    def test_three_families_cover_bad_repaired_missing_and_truncated(self):
        report = run_bounded_system_benchmark()
        payload = report.to_dict()
        self.assertTrue(report.ok)
        self.assertEqual(3, payload["family_count"])
        self.assertEqual(12, payload["case_count"])
        self.assertEqual(0, payload["false_finding_count"])
        for family_id in {item.family_id for item in report.cases}:
            observed = {item.case_id: item.report.status for item in report.cases if item.family_id == family_id}
            self.assertEqual({"bad": "fail", "repaired": "pass", "missing-semantics": "blocked", "truncated": "blocked"}, observed)


if __name__ == "__main__":
    unittest.main()

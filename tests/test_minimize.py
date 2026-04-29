import json
import unittest
from dataclasses import dataclass

from flowguard.minimize import minimize_failing_sequence, minimize_report_counterexample


@dataclass(frozen=True)
class Violation:
    invariant_name: str


@dataclass(frozen=True)
class Report:
    ok: bool
    violations: tuple[Violation, ...] = ()
    reachability_failures: tuple[object, ...] = ()
    dead_branches: tuple[object, ...] = ()
    exception_branches: tuple[object, ...] = ()


def _has_two_a_values(sequence):
    return tuple(sequence).count("A") >= 2


class MinimizeTests(unittest.TestCase):
    def test_minimize_failing_sequence_removes_irrelevant_middle_input(self):
        result = minimize_failing_sequence(
            external_input_sequence=("A", "B", "A"),
            run_sequence=lambda sequence: sequence,
            failure_predicate=_has_two_a_values,
        )

        self.assertEqual("reduced", result.status)
        self.assertEqual(("A", "A"), result.minimized_sequence)
        self.assertEqual(("A", "B", "A"), result.original_sequence)
        self.assertTrue(result.reduction_found)
        self.assertIn("original_sequence", result.to_dict())
        self.assertIn("minimized_sequence", result.format_text())

    def test_minimize_failing_sequence_can_remove_contiguous_segment(self):
        result = minimize_failing_sequence(
            external_input_sequence=("A", "B", "C", "A"),
            run_sequence=lambda sequence: sequence,
            failure_predicate=_has_two_a_values,
        )

        self.assertEqual(("A", "A"), result.minimized_sequence)
        self.assertLess(result.to_dict()["minimized_length"], result.to_dict()["original_length"])

    def test_minimize_failing_sequence_reports_when_no_reduction_found(self):
        result = minimize_failing_sequence(
            external_input_sequence=("A", "A"),
            run_sequence=lambda sequence: sequence,
            failure_predicate=_has_two_a_values,
        )

        self.assertEqual("no_reduction_found", result.status)
        self.assertEqual(("A", "A"), result.minimized_sequence)

    def test_minimize_report_counterexample_focuses_on_violation_name(self):
        def factory(sequence):
            if _has_two_a_values(sequence):
                return Report(ok=False, violations=(Violation("target_failure"),))
            return Report(ok=True)

        result = minimize_report_counterexample(
            factory,
            ("A", "B", "A"),
            violation_name="target_failure",
        )

        self.assertEqual(("A", "A"), result.minimized_sequence)
        self.assertEqual("target_failure", result.violation_name)
        self.assertEqual("target_failure", result.minimized_result.violations[0].invariant_name)
        self.assertEqual(("A", "A"), tuple(json.loads(result.to_json_text())["minimized_sequence"]))


if __name__ == "__main__":
    unittest.main()

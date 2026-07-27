import json
import unittest

from flowguard.validation_results import (
    SkippedValidation,
    VALIDATION_EXIT_CODES,
    VALIDATION_STATUS_BLOCKED,
    VALIDATION_STATUS_FAIL,
    VALIDATION_STATUS_PARTIAL,
    VALIDATION_STATUS_PASS,
    ValidationChildResult,
    ValidationResult,
    aggregate_status,
)


class ValidationCommandSurfaceTests(unittest.TestCase):
    def result(self, **overrides):
        values = {
            "command": "fixture-check",
            "status": VALIDATION_STATUS_PASS,
            "scope": "full",
            "counts": {"passed": 2, "total": 2},
            "claim_boundary": "Current fixture evidence only.",
        }
        values.update(overrides)
        return ValidationResult(**values)

    def test_json_and_human_share_status_semantics(self):
        result = self.result(status=VALIDATION_STATUS_FAIL, failures=("broken child",))
        payload = json.loads(result.to_json_text())
        self.assertEqual(result.status, payload["status"])
        self.assertEqual(result.exit_code, payload["exit_code"])
        self.assertIn("status: fail", result.format_text())

    def test_default_output_is_bounded_but_full_keeps_children(self):
        failures = tuple(f"failure {index}" for index in range(20))
        child = ValidationChildResult("child", VALIDATION_STATUS_FAIL, "large trace", payload={"trace": "x" * 10000})
        result = self.result(status=VALIDATION_STATUS_FAIL, failures=failures, children=(child,), artifact_paths=("results/full.json",))
        concise = result.format_text()
        full = result.format_text(full=True)
        self.assertLess(len(concise), 1000)
        self.assertIn("use --full", concise)
        self.assertNotIn("child: child", concise)
        self.assertIn("child: child", full)
        self.assertIn("artifact: results/full.json", concise)

    def test_required_skip_prevents_broad_success(self):
        result = self.result(skipped_checks=(SkippedValidation("native", "not run", "no full confidence", True),))
        self.assertFalse(result.broad_success)

    def test_terminal_envelope_omits_success_payloads_and_keeps_artifact_identity(self):
        child = ValidationChildResult(
            "models",
            VALIDATION_STATUS_PASS,
            payload={"large": "x" * 10000},
        )
        result = self.result(children=(child,))

        payload = result.terminal_envelope(
            run_id="run-1",
            result_path="results/full.json",
            result_sha256="sha256:result",
        )

        self.assertEqual([], payload["non_pass_child_ids"])
        self.assertNotIn("children", payload)
        self.assertNotIn("large", json.dumps(payload))
        self.assertLess(len(json.dumps(payload, sort_keys=True)), 2000)
        self.assertEqual("results/full.json", payload["result_path"])
        self.assertEqual("sha256:result", payload["result_sha256"])

    def test_terminal_envelope_keeps_every_non_pass_child_class_visible(self):
        children = (
            ValidationChildResult("failed", VALIDATION_STATUS_FAIL),
            ValidationChildResult("blocked", VALIDATION_STATUS_BLOCKED),
            ValidationChildResult("passed", VALIDATION_STATUS_PASS),
        )
        result = self.result(
            status=VALIDATION_STATUS_BLOCKED,
            children=children,
            failures=({"code": "failure", "child_id": "failed"},),
            blockers=({"code": "blocker", "child_id": "blocked"},),
        )

        payload = result.terminal_envelope()

        self.assertEqual(["failed"], payload["failed_child_ids"])
        self.assertEqual(["blocked"], payload["blocked_child_ids"])
        self.assertEqual(
            {"failed", "blocked"},
            set(payload["non_pass_child_ids"]),
        )

    def test_partial_has_nonzero_distinct_exit(self):
        result = self.result(status=VALIDATION_STATUS_PARTIAL)
        self.assertNotEqual(0, result.exit_code)
        self.assertNotEqual(VALIDATION_EXIT_CODES[VALIDATION_STATUS_FAIL], result.exit_code)

    def test_one_child_failure_is_not_flattened(self):
        children = (
            ValidationChildResult("inventory", VALIDATION_STATUS_PASS),
            ValidationChildResult("distribution", VALIDATION_STATUS_FAIL, "extra file"),
        )
        self.assertEqual(VALIDATION_STATUS_FAIL, aggregate_status(children, required_child_ids=("inventory", "distribution")))
        result = self.result(status=VALIDATION_STATUS_FAIL, children=children)
        self.assertEqual("distribution", result.to_dict()["children"][1]["child_id"])

    def test_missing_required_child_is_blocked(self):
        children = (ValidationChildResult("inventory", VALIDATION_STATUS_PASS),)
        self.assertEqual(VALIDATION_STATUS_BLOCKED, aggregate_status(children, required_child_ids=("inventory", "models")))


if __name__ == "__main__":
    unittest.main()

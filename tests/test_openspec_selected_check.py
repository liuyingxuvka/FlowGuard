import unittest

from scripts.run_openspec_selected_check import selected_check_passed


class OpenSpecSelectedCheckTests(unittest.TestCase):
    def test_selected_pass_ignores_unselected_not_run_checks(self) -> None:
        payload = {
            "status": "partial",
            "issues": [
                {"level": "warning", "code": "check_not-run", "check_id": "check.other"}
            ],
            "checks": [
                {"id": "check.selected", "status": "passed"},
                {"id": "check.other", "status": "not-run"},
            ],
        }

        self.assertTrue(selected_check_passed(payload, "check.selected"))

    def test_selected_failure_does_not_pass(self) -> None:
        payload = {
            "issues": [],
            "checks": [{"id": "check.selected", "status": "failed"}],
        }

        self.assertFalse(selected_check_passed(payload, "check.selected"))

    def test_blocking_issue_does_not_pass(self) -> None:
        payload = {
            "issues": [{"level": "blocking", "code": "snapshot_changed"}],
            "checks": [{"id": "check.selected", "status": "passed"}],
        }

        self.assertFalse(selected_check_passed(payload, "check.selected"))


if __name__ == "__main__":
    unittest.main()

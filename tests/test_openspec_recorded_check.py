import json
import tempfile
import unittest
from pathlib import Path

from scripts.verify_openspec_recorded_check import verify_recorded_check


def _payload(content_path: str) -> dict:
    return {
        "status": "pass",
        "issues": [],
        "run": {
            "state": "completed",
            "validation_mode": "full",
            "selection": {"check_ids": ["check.one"]},
        },
        "checks": [
            {
                "id": "check.one",
                "status": "passed",
                "accounting": "executed",
                "receipt_id": "receipt:one",
                "execution_key": "execution:one",
                "result_hash": "result:one",
            }
        ],
        "receipts": [
            {
                "id": "receipt:one",
                "check_id": "check.one",
                "execution_key": "execution:one",
                "result_hash": "result:one",
                "content_path": content_path,
            }
        ],
    }


class OpenSpecRecordedCheckTests(unittest.TestCase):
    def test_current_full_receipt_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = "receipts/one.json"
            sidecar = root / relative
            sidecar.parent.mkdir(parents=True)
            sidecar.write_text(
                json.dumps(
                    {
                        "receipt_id": "receipt:one",
                        "execution_key": "execution:one",
                        "result_hash": "result:one",
                        "result": {"status": "passed"},
                    }
                ),
                encoding="utf-8",
            )

            ok, reason = verify_recorded_check(_payload(relative), "check.one", root=root)

            self.assertTrue(ok)
            self.assertEqual("current_pass_receipt_verified", reason)

    def test_partial_run_cannot_project_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = _payload("receipts/one.json")
            payload["status"] = "partial"

            ok, reason = verify_recorded_check(payload, "check.one", root=root)

            self.assertFalse(ok)
            self.assertEqual("full_run_not_complete", reason)

    def test_sidecar_mismatch_cannot_project_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = "receipts/one.json"
            sidecar = root / relative
            sidecar.parent.mkdir(parents=True)
            sidecar.write_text(
                json.dumps(
                    {
                        "receipt_id": "receipt:other",
                        "execution_key": "execution:one",
                        "result_hash": "result:one",
                        "result": {"status": "passed"},
                    }
                ),
                encoding="utf-8",
            )

            ok, reason = verify_recorded_check(_payload(relative), "check.one", root=root)

            self.assertFalse(ok)
            self.assertEqual("receipt_sidecar_mismatch", reason)


if __name__ == "__main__":
    unittest.main()

import json
import subprocess
import sys
import unittest

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AdoptionCliTests(unittest.TestCase):
    def _assert_retired_compact_route(self, operation: str) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "flowguard", operation, "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(2, result.returncode, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual("blocked", payload["status"])
        self.assertEqual("block", payload["decision"])
        self.assertEqual(0, payload["producer_count"])
        self.assertEqual(f"unknown operation: {operation}", payload["error"])
        self.assertEqual(["read", "change", "release"], payload["allowed_operations"])

    def test_retired_adoption_start_route_is_rejected(self):
        self._assert_retired_compact_route("adoption-start")

    def test_retired_adoption_finish_route_is_rejected(self):
        self._assert_retired_compact_route("adoption-finish")


if __name__ == "__main__":
    unittest.main()

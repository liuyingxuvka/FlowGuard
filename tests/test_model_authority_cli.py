import json
import unittest
from contextlib import redirect_stdout
from io import StringIO

from flowguard.__main__ import main


class ModelAuthorityCliTests(unittest.TestCase):
    def _assert_retired_compact_route(self, operation: str) -> None:
        output = StringIO()
        with redirect_stdout(output):
            exit_code = main([operation, "--json"])

        payload = json.loads(output.getvalue())
        self.assertEqual(2, exit_code)
        self.assertEqual("blocked", payload["status"])
        self.assertEqual("block", payload["decision"])
        self.assertEqual(0, payload["producer_count"])
        self.assertEqual(f"unknown operation: {operation}", payload["error"])
        self.assertEqual(["read", "change", "release"], payload["allowed_operations"])

    def test_retired_model_revision_build_route_is_rejected(self):
        self._assert_retired_compact_route("model-revision-build")

    def test_retired_model_revision_activate_route_is_rejected(self):
        self._assert_retired_compact_route("model-revision-activate")

    def test_retired_model_system_audit_route_is_rejected(self):
        self._assert_retired_compact_route("model-system-audit")

    def test_retired_model_system_audit_projection_route_is_rejected(self):
        self._assert_retired_compact_route("model-system-audit")

    def test_retired_intent_bootstrap_route_is_rejected_before_input_read(self):
        self._assert_retired_compact_route("model-revision-intent-bootstrap")

    def test_retired_intent_bootstrap_unknown_field_route_is_rejected(self):
        self._assert_retired_compact_route("model-revision-intent-bootstrap")


if __name__ == "__main__":
    unittest.main()

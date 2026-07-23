import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from flowguard.__main__ import main


class ModelAuthorityCliTests(unittest.TestCase):
    def test_model_system_audit_fails_closed_without_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".flowguard").mkdir()
            (root / ".flowguard" / "project.toml").write_text(
                "[flowguard]\n",
                encoding="utf-8",
            )
            output = StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "model-system-audit",
                        "--root",
                        str(root),
                        "--json",
                    ]
                )

            payload = json.loads(output.getvalue())
            self.assertEqual(1, exit_code)
            self.assertEqual("blocked", payload["status"])
            self.assertFalse(payload["ok"])
            self.assertEqual(
                "model_authority_invalid",
                payload["findings"][0]["code"],
            )


if __name__ == "__main__":
    unittest.main()

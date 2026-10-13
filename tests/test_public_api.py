"""The public facade is plain data: every name resolves, importing is cheap."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

import flowguard

ROOT = Path(__file__).resolve().parents[1]


class PublicApiTests(unittest.TestCase):
    def test_every_public_name_resolves_from_its_owner(self) -> None:
        missing = [name for name in flowguard.__all__ if not hasattr(flowguard, name)]
        self.assertEqual([], missing)

    def test_public_names_are_unique_and_sorted(self) -> None:
        self.assertEqual(sorted(set(flowguard.__all__)), list(flowguard.__all__))

    def test_import_flowguard_loads_only_the_facade(self) -> None:
        code = "import sys, flowguard; print(sorted(m for m in sys.modules if m.startswith('flowguard')))"
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual("['flowguard']", result.stdout.strip())

    def test_core_engine_names_are_public(self) -> None:
        for name in ("Workflow", "FunctionResult", "Invariant", "replay_trace", "review_scenarios"):
            self.assertIn(name, flowguard.__all__)

    def test_unknown_attribute_is_attribute_error(self) -> None:
        with self.assertRaises(AttributeError):
            getattr(flowguard, "no_such_public_name")

    def test_version_matches_pyproject(self) -> None:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn(f'version = "{flowguard.__version__}"', text)


if __name__ == "__main__":
    unittest.main()

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
        for name in ("Workflow", "FunctionResult", "Invariant", "replay_trace", "review_scenarios", "Explorer"):
            self.assertIn(name, flowguard.__all__)

    def test_unknown_attribute_is_attribute_error(self) -> None:
        with self.assertRaises(AttributeError):
            getattr(flowguard, "no_such_public_name")

    def test_version_matches_pyproject(self) -> None:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn(f'version = "{flowguard.__version__}"', text)


    def test_consumer_names_stay_public(self) -> None:
        # Original consumer module paths are part of the compatibility promise.
        imports = (
            ('flowguard', 'FunctionResult'),
            ('flowguard', 'Invariant'),
            ('flowguard', 'InvariantResult'),
            ('flowguard', 'ReplayObservation'),
            ('flowguard', 'Scenario'),
            ('flowguard', 'ScenarioExpectation'),
            ('flowguard', 'Workflow'),
            ('flowguard', 'replay_trace'),
            ('flowguard', 'select_covering_traces'),
            ('flowguard.conformance', 'ConformanceReport'),
            ('flowguard.conformance', 'ConformanceViolation'),
            ('flowguard.conformance', 'projected_output_matches'),
            ('flowguard.conformance', 'projected_state_matches'),
            ('flowguard.explorer', 'Explorer'),
            ('flowguard.kit', 'Feature'),
            ('flowguard.kit', 'feature_conformance'),
            ('flowguard.kit', 'feature_explorer'),
            ('flowguard.kit', 'feature_variants'),
            ('flowguard.replay', 'ReplayObservation'),
        )
        code = "\n".join(f"from {module} import {name}" for module, name in imports)
        # A fresh interpreter cannot borrow an attribute cached by another test.
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

if __name__ == "__main__":
    unittest.main()


def test_lazy_getattr_resolves_public_names_and_rejects_unknown_ones():
    import flowguard
    from flowguard.explorer import Explorer

    assert flowguard.__getattr__("Explorer") is Explorer
    for name, error in (("not_a_flowguard_name", AttributeError), ("RuntimeGateway", ImportError)):
        try:
            flowguard.__getattr__(name)
        except error:
            continue
        raise AssertionError(f"{name} should raise {error.__name__}")

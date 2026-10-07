from __future__ import annotations

import unittest
import importlib.util
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import flowguard


EXPECTED_PORTABLE_COHORT = (
    "PORTABLE_MODEL_SCHEMA_VERSION",
    "PORTABLE_REFINEMENT_SCHEMA_VERSION",
    "PortableModel",
    "RefinementBinding",
    "load_portable_model",
    "validate_portable_model",
    "execute_portable_model",
    "check_portable_model",
    "check_refinement",
    "check_composition",
    "PORTABLE_SYSTEM_SCHEMA_VERSION",
    "PORTABLE_SYSTEM_REQUEST_SCHEMA_VERSION",
    "PortableSystemDefinition",
    "SystemCompositionRequest",
    "PortableSystemSlice",
    "load_portable_system",
    "load_system_composition_request",
    "derive_system_slice",
    "SystemCompositionReport",
    "check_system_composition",
)


class PublicApiSurfaceTests(unittest.TestCase):
    def _current_namespace_metadata_fixture(self, native_exports, governance_exports):
        path = Path(__file__).resolve().parents[1] / "scripts/generate_lazy_public_api.py"
        spec = importlib.util.spec_from_file_location("namespace_metadata_fixture_generator", path)
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        baseline = {
            "names": ["NativeSuiteContext", "prepare_native_suite_context", "NativeSkillCheck",
                      "load_verification_contexts", "UnrelatedLegacy", "CurrentNative"],
            "owners": {
                "NativeSuiteContext": "flowguard.skill_native_checks",
                "prepare_native_suite_context": "flowguard.skill_native_checks",
                "NativeSkillCheck": "flowguard.skill_native_checks",
                "load_verification_contexts": "flowguard.skill_self_governance",
                "UnrelatedLegacy": "flowguard.other",
                "CurrentNative": "flowguard.skill_native_checks",
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "flowguard"
            package.mkdir()
            for module, exports in (("skill_native_checks", native_exports),
                                    ("skill_self_governance", governance_exports),
                                    ("route_topology", ("PUBLIC_LIFECYCLE_IDS",))):
                (package / (module + ".py")).write_text("__all__ = " + repr(exports), encoding="utf-8")
            eager = package / "_eager_exports.py"
            eager.write_text(
                "from . import skill_native_checks as _native\n"
                "from . import skill_self_governance as _governance\n"
                "from . import route_topology as _routes\n"
                "from .other import implementation_coverage_obligation_id\n"
                "FLOWGUARD_GOVERNANCE_API = tuple(name for module in (_native, _governance) for name in module.__all__)\n"
                "__all__ = FLOWGUARD_GOVERNANCE_API\n", encoding="utf-8",
            )
            with (patch.object(generator, "ROOT", root), patch.object(generator, "EAGER_PATH", eager),
                  patch.object(generator, "_decode_current", return_value=baseline)):
                return generator.build_metadata()

    def test_current_source_namespaces_retire_only_their_removed_exports(self):
        metadata = self._current_namespace_metadata_fixture(
            ("CurrentNative", "NewNative"), ("CurrentGovernance",),
        )
        for name in ("NativeSuiteContext", "prepare_native_suite_context", "NativeSkillCheck",
                     "load_verification_contexts"):
            self.assertNotIn(name, metadata["names"])
            self.assertNotIn(name, metadata["owners"])
            self.assertNotIn(name, metadata["targets"])
        self.assertIn("UnrelatedLegacy", metadata["names"])
        self.assertEqual("flowguard.other", metadata["owners"]["UnrelatedLegacy"])
        for name, module in (("CurrentNative", "skill_native_checks"), ("NewNative", "skill_native_checks"),
                             ("CurrentGovernance", "skill_self_governance")):
            self.assertIn(name, metadata["names"])
            self.assertEqual("flowguard." + module, metadata["owners"][name])
            self.assertEqual(name, metadata["targets"][name])

    def test_namespace_export_removal_is_recomputed_from_each_current_ast(self):
        first = self._current_namespace_metadata_fixture(("CurrentNative",), ("CurrentGovernance",))
        second = self._current_namespace_metadata_fixture(("ReplacementNative",), ("ReplacementGovernance",))
        self.assertIn("CurrentNative", first["names"])
        self.assertNotIn("CurrentNative", second["names"])
        self.assertNotIn("CurrentGovernance", second["names"])
        self.assertIn("ReplacementNative", second["names"])
        self.assertIn("ReplacementGovernance", second["names"])
        self.assertIn("UnrelatedLegacy", second["names"])

    def test_current_import_aliases_resolve_exact_original_targets_without_eager_loading(self):
        module = flowguard.layered_proof
        targets = (
            "NON_PASSING_PROOF_STATUSES", "PASSING_PROOF_STATUSES",
            "PROOF_STATUS_ERROR", "PROOF_STATUS_FAILED", "PROOF_STATUS_NOT_RUN",
            "PROOF_STATUS_PASSED", "PROOF_STATUS_PROGRESS_ONLY", "PROOF_STATUS_RUNNING",
            "PROOF_STATUS_SKIPPED", "PROOF_STATUS_STALE",
        )
        with patch.object(flowguard, "_load_eager_facade") as other_owner:
            for target in targets:
                name = "LAYERED_" + target
                with self.subTest(public_name=name):
                    self.assertEqual("flowguard.layered_proof", flowguard._LAZY_OWNERS[name])
                    self.assertEqual(target, flowguard._LAZY_TARGETS[name])
                    self.assertIs(getattr(module, target), flowguard.__getattr__(name))
            other_owner.assert_not_called()

    def test_missing_alias_target_cannot_select_public_name_or_another_owner(self):
        name = "LAYERED_PROOF_STATUS_PASSED"
        owner = "flowguard.layered_proof"
        with (
            patch.dict(flowguard.__dict__, {}),
            patch.object(flowguard.importlib, "import_module", return_value=SimpleNamespace(**{name: object()})) as importer,
            patch.object(flowguard, "_load_eager_facade") as other_owner,
        ):
            vars(flowguard).pop(name, None)
            with self.assertRaisesRegex(AttributeError, "has no export 'PROOF_STATUS_PASSED'"):
                flowguard.__getattr__(name)
            importer.assert_called_once_with(owner)
            other_owner.assert_not_called()
            self.assertNotIn(name, vars(flowguard))

    def test_lazy_metadata_matches_the_current_source_generator(self):
        path = Path(__file__).resolve().parents[1] / "scripts/generate_lazy_public_api.py"
        spec = importlib.util.spec_from_file_location("current_lazy_public_api_generator", path)
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        self.assertEqual(flowguard._API_METADATA, generator.build_metadata())

    def test_portable_verification_cohort_has_one_registry_owner(self):
        self.assertEqual(EXPECTED_PORTABLE_COHORT, flowguard.PORTABLE_VERIFICATION_API)
        self.assertEqual(EXPECTED_PORTABLE_COHORT, flowguard.API_SURFACE["portable_verification"])

    def test_every_declared_portable_name_is_public_and_importable(self):
        for name in EXPECTED_PORTABLE_COHORT:
            self.assertIn(name, flowguard.__all__)
            self.assertTrue(hasattr(flowguard, name), name)

    def test_internal_checker_helpers_are_not_public(self):
        for name in ("_tarjan", "_eventual_failure", "_fairness_forces_escape", "_compile"):
            self.assertNotIn(name, flowguard.__all__)

    def test_missing_declared_lazy_export_does_not_select_another_owner(self):
        name = "_flowguard_test_missing_declared_export"
        owner = "flowguard.declared_test_owner"
        with (
            patch.dict(flowguard._LAZY_OWNERS, {name: owner}),
            patch.dict(flowguard._LAZY_TARGETS, {name: name}),
            patch.object(flowguard.importlib, "import_module", return_value=SimpleNamespace()) as importer,
            patch.object(flowguard, "_load_eager_facade") as other_owner,
        ):
            with self.assertRaisesRegex(AttributeError, "declared public API owner.*has no export"):
                flowguard.__getattr__(name)
            importer.assert_called_once_with(owner)
            other_owner.assert_not_called()
            self.assertNotIn(name, vars(flowguard))

    def test_declared_lazy_owner_import_error_is_preserved(self):
        name = "_flowguard_test_import_failure"
        owner = "flowguard.declared_test_owner"
        failure = AttributeError("declared owner import failed")
        with (
            patch.dict(flowguard._LAZY_OWNERS, {name: owner}),
            patch.dict(flowguard._LAZY_TARGETS, {name: name}),
            patch.object(flowguard.importlib, "import_module", side_effect=failure),
            patch.object(flowguard, "_load_eager_facade") as other_owner,
        ):
            with self.assertRaises(AttributeError) as raised:
                flowguard.__getattr__(name)
            self.assertIs(raised.exception, failure)
            other_owner.assert_not_called()
            self.assertNotIn(name, vars(flowguard))


if __name__ == "__main__":
    unittest.main()

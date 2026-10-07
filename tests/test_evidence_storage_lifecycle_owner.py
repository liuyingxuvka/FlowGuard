"""Storage-owner checks must reject corruption and failed physical effects."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


PATH = Path(__file__).resolve().parents[1] / ".flowguard/models/owners/evidence_storage_lifecycle/model.py"
NAME = "_evidence_storage_lifecycle_owner_test"
SPEC = importlib.util.spec_from_file_location(NAME, PATH)
OWNER = importlib.util.module_from_spec(SPEC)
sys.modules[NAME] = OWNER
SPEC.loader.exec_module(OWNER)


class EvidenceStorageOwnerTests(unittest.TestCase):
    def test_declared_source_identity_rejects_omitted_real_hashing_dependency(self):
        """Missing transitive Source identity must fail without storage execution."""
        from dataclasses import replace
        from flowguard.model_regressions import (
            ModelRegressionManifest, build_regression_model_instance,
            resolve_entry_input_inventory,
        )
        from flowguard.model_path_quality import (
            DeclaredPathQualitySource, verify_declared_path_quality_source,
        )

        root = PATH.parents[4]
        manifest = ModelRegressionManifest.load(root)
        entry = next(row for row in manifest.entries if row.model_id == OWNER.MODEL_ID)
        inventory = resolve_entry_input_inventory(
            root, entry, additional_patterns=manifest.owner_patterns_for(entry.model_id),
        )
        instance = build_regression_model_instance(root, entry, inventory)
        actual_inputs = {row.path: row.sha256 for row in instance.inputs}
        # evidence_lifecycle imports this actual hash implementation. Removing
        # its export would hide a required freshness edge rather than repair it.
        dependency = "flowguard/_hashing.py"
        self.assertIn(dependency, actual_inputs)
        with patch.object(OWNER, "run_review", side_effect=AssertionError("declaration executed storage cases")):
            source = DeclaredPathQualitySource.from_dict(
                OWNER.export_path_quality_source(instance.fingerprint).to_dict(),
            )
            self.assertEqual(instance.logical_model_id, source.model_id)
            self.assertEqual(instance.fingerprint, source.model_instance_fingerprint)
            self.assertEqual((), verify_declared_path_quality_source(source, instance))
            refs = {row["path"]: row["source_fingerprint"] for row in source.source_refs}
            self.assertIn(dependency, refs)
            for path, fingerprint in refs.items():
                self.assertEqual(actual_inputs[path], fingerprint, path)

            missing_dependency = replace(
                instance, inputs=tuple(row for row in instance.inputs if row.path != dependency),
            )
            # Rebind the instance fingerprint deliberately: the failure must
            # arise from the missing exact Source ref, not a stale first-field ID.
            incomplete_source = OWNER.export_path_quality_source(missing_dependency.fingerprint)
            self.assertEqual(
                ("declared_source_identity_mismatch",),
                verify_declared_path_quality_source(incomplete_source, missing_dependency),
            )

    def test_real_temporary_storage_satisfies_each_independent_oracle(self):
        cases = OWNER.run_review()["native_cases"]
        self.assertEqual([], [case["name"] for case in cases if not case["ok"]])
        bad = {case["finding_codes"][0]: case for case in cases if case["case_kind"] == "bad"}
        self.assertEqual(set(OWNER.PROTECTED_FAILURE_IDS), set(bad))
        for case in bad.values():
            self.assertEqual("violation", case["observed_status"], case["name"])

    def test_corruption_oracle_fails_when_verifier_falsely_accepts_every_object(self):
        with patch.object(OWNER, "verify_text_object", return_value=True):
            rows = OWNER.object_cases()
        corrupt = next(row for row in rows if row["name"] == "corrupted_object_rejected")
        self.assertFalse(corrupt["ok"])

    def test_failed_physical_purge_preserves_pending_without_a_success_receipt(self):
        import flowguard.evidence_lifecycle as lifecycle
        with tempfile.TemporaryDirectory(prefix="flowguard-storage-purge-failure-") as directory:
            root = Path(directory)
            old, pinned, current, preserved = OWNER._store(root)
            receipt = lifecycle.apply_evidence_gc(root, OWNER._plan(root))
            quarantine = root / ".quarantine" / receipt["quarantine_id"]
            receipts = root / ".quarantine/receipts"
            pending = receipts / ("purge-pending-" + receipt["quarantine_id"] + ".json")
            final = receipts / ("purge-" + receipt["quarantine_id"] + ".json")
            # A deterministic I/O failure is injected at the physical boundary;
            # the real public purge API must retain its interrupted state.
            with patch.object(lifecycle, "_remove_tree_exact", side_effect=OSError("fixture I/O failure")):
                with self.assertRaisesRegex(OSError, "fixture I/O failure"):
                    lifecycle.purge_evidence_quarantine(root, receipt["quarantine_id"])
            self.assertTrue(quarantine.is_dir())
            self.assertTrue((quarantine / "runs/scope/old/result.json").is_file())
            self.assertEqual("pending", json.loads(pending.read_text(encoding="utf-8"))["status"])
            self.assertFalse(final.exists())
            self.assertTrue(all(path.is_dir() for path in (pinned, current, preserved)))


if __name__ == "__main__":
    unittest.main()

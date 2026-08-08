import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flowguard.model_regressions import (
    MANIFEST_SCHEMA,
    ModelRegressionEntry,
    ModelRegressionEvidenceError,
    ModelRegressionManifest,
    ModelRegressionManifestError,
    audit_intent_source_input_bindings,
    audit_manifest,
    compile_model_impact_map,
    discover_model_directories,
    resolve_current_full_model_regression_parent,
    resolve_entry_input_inventory,
    run_manifest_regressions,
)
from flowguard.model_authority_store import load_current_accepted_revision_set
from flowguard.evidence_receipts import fingerprint_value, receipt_path
from flowguard.model_purpose import build_model_purpose_closure, file_fingerprint
from flowguard.validation_ownership import build_owner_current, resolve_input_manifest


class ModelRegressionManifestTests(unittest.TestCase):
    def test_flowguard_runtime_inputs_use_exact_model_owners_not_run_all(self):
        root = Path(__file__).resolve().parents[1]
        manifest = ModelRegressionManifest.load(root)
        impact = compile_model_impact_map(root, manifest)

        self.assertTrue(impact.ok, impact.errors)
        self.assertFalse(
            any(
                "flowguard/**/*.py" in group.globs
                for group in manifest.shared_input_groups
            ),
            "a broad runtime component would invalidate nearly every model",
        )
        self.assertEqual(
            ("architecture_reduction",),
            impact.owners_by_path["flowguard/self_reduction_inventory.py"],
        )
        self.assertEqual(
            (
                "implementation_blueprint",
                "model_test_code_alignment",
                "structure_refactor_mesh",
            ),
            impact.owners_by_path["flowguard/project_blueprint.py"],
        )
        self.assertEqual(
            ("work_context",),
            impact.owners_by_path["flowguard/template_text/work_context.py"],
        )
        self.assertEqual(
            len(manifest.entries),
            len(impact.owners_by_path["pyproject.toml"]),
        )

    def test_full_run_uses_one_initial_and_one_final_source_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch(
                "flowguard.validation_ownership.resolve_input_manifest",
                wraps=resolve_input_manifest,
            ) as resolve_manifest, patch(
                "flowguard.validation_owner_execution.build_owner_current",
                wraps=build_owner_current,
            ) as publish_current_rebuild:
                report = self.current_parent_fixture(root)

            complete_observations = tuple(
                call
                for call in resolve_manifest.call_args_list
                if len(call.args) > 1 and call.args[1] == ("**/*", "*")
            )
            self.assertEqual(2, len(complete_observations))
            self.assertEqual(0, publish_current_rebuild.call_count)
            diagnostics = report.to_dict()["validation_observation"]
            self.assertEqual(2, diagnostics["complete_observation_count"])
            self.assertTrue(diagnostics["initial_fingerprint"].startswith("sha256:"))
            self.assertTrue(
                diagnostics["final_freshness_fingerprint"].startswith("sha256:")
            )
            self.assertEqual(0, diagnostics["per_leaf_source_current_rebuild_count"])
            self.assertEqual(0, diagnostics["per_leaf_receipt_store_scan_count"])
            self.assertEqual(1, diagnostics["receipt_reconciliation_count"])

    def test_text_source_identity_is_stable_across_line_endings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_dir = root / ".flowguard" / "sample"
            model_dir.mkdir(parents=True)
            model_path = model_dir / "model.py"
            runner_path = model_dir / "run_checks.py"
            model_path.write_bytes(b"first\r\nsecond\r\n")
            runner_path.write_bytes(b"run\r\n")
            entry = ModelRegressionEntry.from_dict(self.entry("sample", root))

            windows_model = file_fingerprint(model_path)
            windows_inventory = resolve_entry_input_inventory(root, entry)
            model_path.write_bytes(b"first\nsecond\n")
            runner_path.write_bytes(b"run\n")

            self.assertEqual(windows_model, file_fingerprint(model_path))
            self.assertEqual(
                windows_inventory,
                resolve_entry_input_inventory(root, entry),
            )

    def test_repository_manifest_accounts_for_every_model(self):
        root = Path(__file__).resolve().parents[1]
        manifest = ModelRegressionManifest.load(root)
        audit = audit_manifest(root, manifest)
        self.assertTrue(audit.ok, audit.errors)
        self.assertEqual(
            len(manifest.entries),
            len(audit.registered_model_ids),
        )
        self.assertGreater(len(audit.registered_model_ids), 0)
        discovered = {
            path.relative_to(root / ".flowguard").as_posix()
            for path in discover_model_directories(root)
        }
        required_public = {
            entry.model_id
            for entry in manifest.entries
            if entry.distribution_policy == "required_public"
        }
        self.assertTrue(required_public.issubset(discovered))
        self.assertTrue(discovered.issubset(set(audit.registered_model_ids)))
        self.assertIn("template_public_release", audit.registered_model_ids)

    def test_manifest_rejects_noncanonical_logical_model_regression_evidence_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_dir = root / ".flowguard" / "sample"
            model_dir.mkdir(parents=True)
            model_dir.joinpath("model.py").write_text("VALUE = 1\n", encoding="utf-8")
            model_dir.joinpath("run_checks.py").write_text(
                "raise SystemExit(0)\n",
                encoding="utf-8",
            )
            row = self.entry("sample", root)
            row["purpose_closure"] = build_model_purpose_closure(
                model_instance_id="regression:sample:current",
                reusable_model_type_id="sample",
                task_intent_id="flowguard-regression:sample",
                guarded_purpose="Prevent a noncanonical evidence identity from being accepted as the current logical model check.",
                protected_failure_ids=("sample:noncanonical-evidence",),
                known_good_case_id="native-runner:sample:good",
                failure_bindings=({
                    "failure_id": "sample:noncanonical-evidence",
                    "known_bad_case_id": "native-runner:sample:bad",
                    "oracle_id": "native:sample:runner",
                },),
                claim_boundary="This fixture proves only exact current model-regression evidence identity.",
                evidence_check_ids=("check:model-regression:sample-alias",),
                model_sha256=file_fingerprint(model_dir / "model.py"),
                runner_sha256=file_fingerprint(model_dir / "run_checks.py"),
            ).to_dict()
            manifest_path = root / ".flowguard" / "model-regression-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": MANIFEST_SCHEMA,
                        "governed_input_globs": [".flowguard/**/*.py"],
                        "snapshot_only_input_globs": [],
                        "shared_input_groups": [],
                        "models": [row],
                    }
                ),
                encoding="utf-8",
            )

            audit = audit_manifest(root, ModelRegressionManifest.load(root))

            self.assertFalse(audit.ok)
            self.assertTrue(
                any(
                    "one exact logical model-regression evidence identity" in item
                    for item in audit.errors
                ),
                audit.errors,
            )

    def test_repository_manifest_binds_every_current_local_intent_to_its_owner(self):
        root = Path(__file__).resolve().parents[1]
        manifest = ModelRegressionManifest.load(root)
        revision = load_current_accepted_revision_set(root)
        self.assertIsNotNone(revision)
        view = revision.current_effective_intent_view
        entries = {entry.model_id: entry for entry in manifest.entries}
        contributions = {
            item.contribution_id: item for item in view.active_contributions
        }

        project_file_count = 0
        for source in view.verified_source_identities:
            if source.authority_kind != "project_file":
                continue
            project_file_count += 1
            contribution = contributions[source.contribution_id]
            owner = contribution.logical_model_id.split("model:", 1)[1]
            self.assertIn(
                source.resolved_project_ref,
                entries[owner].intent_source_inputs,
                (owner, source.resolved_project_ref),
            )

        self.assertEqual(len(view.active_contributions), project_file_count)
        self.assertEqual(
            project_file_count,
            len(
                {
                    source.contribution_id
                    for source in view.verified_source_identities
                    if source.authority_kind == "project_file"
                }
            ),
        )
        self.assertIn(
            "openspec/specs/model-path-quality-closure/spec.md",
            entries["model_maturation_loop"].intent_source_inputs,
        )
        binding_errors = audit_intent_source_input_bindings(
            root,
            manifest,
            view.active_contributions,
            view.verified_source_identities,
        )
        self.assertEqual((), binding_errors)

    def test_exact_intent_source_input_is_owned_and_fingerprinted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_dir = root / ".flowguard" / "sample"
            model_dir.mkdir(parents=True)
            model_dir.joinpath("model.py").write_text("VALUE = 1\n", encoding="utf-8")
            model_dir.joinpath("run_checks.py").write_text("print('ok')\n", encoding="utf-8")
            source = root / "docs" / "intent.md"
            source.parent.mkdir()
            source.write_text("One exact intent.\n", encoding="utf-8")
            row = self.entry("sample", root)
            row["intent_source_inputs"] = ["docs/intent.md"]
            manifest_path = root / ".flowguard" / "model-regression-manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": MANIFEST_SCHEMA,
                        "governed_input_globs": [".flowguard/**/*.py", "docs/*.md"],
                        "snapshot_only_input_globs": [],
                        "shared_input_groups": [],
                        "models": [row],
                    }
                ),
                encoding="utf-8",
            )
            manifest = ModelRegressionManifest.load(root)
            entry = manifest.entries[0]
            inventory = resolve_entry_input_inventory(root, entry)
            impact = compile_model_impact_map(root, manifest)

            self.assertIn("docs/intent.md", entry.effective_input_patterns)
            self.assertIn("docs/intent.md", {item["path"] for item in inventory})
            self.assertEqual(("sample",), impact.owners_by_path["docs/intent.md"])

    def test_intent_source_input_rejects_globs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_dir = root / ".flowguard" / "sample"
            model_dir.mkdir(parents=True)
            model_dir.joinpath("model.py").write_text("VALUE = 1\n", encoding="utf-8")
            model_dir.joinpath("run_checks.py").write_text("print('ok')\n", encoding="utf-8")
            row = self.entry("sample", root)
            row["intent_source_inputs"] = ["docs/*.md"]
            path = root / ".flowguard" / "model-regression-manifest.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": MANIFEST_SCHEMA,
                        "governed_input_globs": [".flowguard/**/*.py"],
                        "snapshot_only_input_globs": [],
                        "shared_input_groups": [],
                        "models": [row],
                    }
                ),
                encoding="utf-8",
            )
            audit = audit_manifest(root, ModelRegressionManifest.load(root))
            self.assertFalse(audit.ok)
            self.assertTrue(
                any("unsafe intent_source_input" in item for item in audit.errors),
                audit.errors,
            )

    def test_authoritative_model_owns_native_owner_verifier_freshness(self):
        root = Path(__file__).resolve().parents[1]
        manifest = ModelRegressionManifest.load(root)
        authority = next(
            entry
            for entry in manifest.entries
            if entry.model_id == "authoritative_model_system"
        )

        self.assertIn(
            "flowguard/model_revision_owner_evidence.py",
            authority.input_globs,
        )
        self.assertIn(
            "tests/test_model_revision_owner_evidence.py",
            authority.input_globs,
        )

    def test_retired_task_instances_delegate_to_exact_current_regression_owners(self):
        root = Path(__file__).resolve().parents[1]
        manifest = ModelRegressionManifest.load(root)
        by_id = {entry.model_id: entry for entry in manifest.entries}
        retired_ids = {
            "openspec_archive_cleanup",
            "readme_positioning_20260602",
            "release_visibility_process",
            "risk_purpose_header",
        }

        self.assertEqual(
            len(audit_manifest(root, manifest).registered_model_ids),
            len(by_id),
        )
        self.assertTrue(retired_ids.isdisjoint(by_id))
        self.assertTrue(
            all(
                retired_ids.isdisjoint(group.consumers)
                for group in manifest.shared_input_groups
            )
        )
        expected_inputs = {
            "minimum_valuable_model_entry": {
                "flowguard/risk.py",
                "tests/test_audit.py",
                "tests/test_risk_plan.py",
                "tests/test_runner.py",
            },
            "development_process_flow": {
                "flowguard/release_verification.py",
                "scripts/verify_flowguard_release.py",
                "scripts/check_openspec_change.py",
                "scripts/check_openspec_semantic_sync.py",
                "tests/test_release_verification.py",
                "tests/test_openspec_semantic_sync.py",
                "tests/test_current_spec_authority.py",
            },
            "test_evidence_mesh": {
                "scripts/run_openspec_selected_check.py",
                "scripts/verify_openspec_recorded_check.py",
                "tests/test_openspec_selected_check.py",
                "tests/test_openspec_recorded_check.py",
            },
            "template_public_release": {
                "flowguard/risk_templates.py",
                "tests/test_risk_templates.py",
            },
            "authoritative_model_system": {
                "flowguard/model_intent_authority.py",
                "flowguard/model_revision_plan.py",
                "tests/test_model_intent_authority.py",
                "tests/test_model_revision_set.py",
                "tests/test_model_revision_plan.py",
                "tests/test_model_authority_cli.py",
                "tests/test_blueprint_cli_routes.py",
                "tests/test_api_surface.py",
                "tests/test_semantic_self_mesh_direct_current.py",
            },
        }
        for owner_id, required_paths in expected_inputs.items():
            self.assertTrue(
                required_paths.issubset(by_id[owner_id].input_globs),
                (owner_id, sorted(required_paths - set(by_id[owner_id].input_globs))),
            )

        minimum_purpose = by_id["minimum_valuable_model_entry"].purpose_closure
        self.assertIsNotNone(minimum_purpose)
        self.assertEqual(
            (
                "minimum_valuable_model_missing_contract_or_binding",
                "minimum_valuable_model_template_operation_on_ordinary_path",
            ),
            minimum_purpose.protected_failure_ids,
        )
        self.assertEqual(
            (
                "native-runner:minimum_valuable_model_entry:broken_accepts_incomplete_model",
                "native-runner:minimum_valuable_model_entry:broken_runs_template_operation_on_ordinary_path",
            ),
            tuple(
                binding.known_bad_case_id
                for binding in minimum_purpose.failure_bindings
            ),
        )

        authority_purpose = by_id["authoritative_model_system"].purpose_closure
        authority_bad_cases = {
            binding.failure_id: binding.known_bad_case_id
            for binding in authority_purpose.failure_bindings
        }
        self.assertEqual(
            "native-runner:authoritative-model-system:topology-omits-one-declared-child-receipt",
            authority_bad_cases[
                "model-authority:topology-child-receipt-coverage-gap"
            ],
        )
        hierarchy_boundary = by_id[
            "hierarchical_model_mesh"
        ].purpose_closure.claim_boundary
        closure_boundary = by_id[
            "model_mesh_closure_model"
        ].purpose_closure.claim_boundary
        self.assertIn("exact current child receipts", hierarchy_boundary)
        self.assertIn("current semantic mesh", closure_boundary)

    def test_current_full_parent_resolver_returns_independent_child_identities(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.current_parent_fixture(root)
            receipt_root = root / ".flowguard" / "evidence" / "model-owner-receipts"
            before = {
                path.relative_to(receipt_root).as_posix(): path.read_bytes()
                for path in receipt_root.rglob("*")
                if path.is_file()
            }

            current = resolve_current_full_model_regression_parent(root)

            after = {
                path.relative_to(receipt_root).as_posix(): path.read_bytes()
                for path in receipt_root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)
            self.assertEqual(report.parent_receipt_path, current.parent_artifact_path)
            self.assertEqual(
                report.parent_receipt_fingerprint,
                current.parent_artifact_fingerprint,
            )
            self.assertEqual(1, len(current.children))
            child = current.child_evidence_by_model_id["alpha"]
            result = report.results[0]
            parent_payload = json.loads(
                Path(report.parent_receipt_path).read_text(encoding="utf-8")
            )
            self.assertEqual(
                parent_payload["children"][0]["receipt_id"],
                child.receipt_id,
            )
            self.assertEqual(result.receipt_fingerprint, child.receipt_fingerprint)
            self.assertEqual(result.model_instance_id, child.model_instance_id)
            self.assertEqual(
                result.model_instance_fingerprint,
                child.model_instance_fingerprint,
            )
            self.assertEqual(
                result.input_inventory_fingerprint,
                child.input_inventory_fingerprint,
            )
            self.assertEqual(
                result.purpose_closure_fingerprint,
                child.purpose_closure_fingerprint,
            )

    def test_repeated_full_run_reuses_the_unique_current_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self.current_parent_fixture(root)

            second = run_manifest_regressions(
                root,
                tier="full",
                output_dir=root / "model-run-second",
            )
            current = resolve_current_full_model_regression_parent(root)

            self.assertEqual(
                first.parent_receipt_path,
                second.parent_receipt_path,
            )
            self.assertEqual(
                first.parent_receipt_fingerprint,
                second.parent_receipt_fingerprint,
            )
            self.assertEqual(
                first.parent_receipt_fingerprint,
                current.parent_artifact_fingerprint,
            )
            parent_dir = (
                root
                / ".flowguard"
                / "evidence"
                / "model-owner-receipts"
                / "model-parents"
            )
            self.assertEqual(1, len(tuple(parent_dir.glob("*.json"))))

    def test_full_run_renews_stale_parent_without_mutating_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self.current_parent_fixture(root)
            first_path = Path(first.parent_receipt_path)
            first_bytes = first_path.read_bytes()
            (root / ".flowguard" / "alpha" / "support.py").write_text(
                "VALUE = 2\n",
                encoding="utf-8",
            )

            second = run_manifest_regressions(
                root,
                tier="full",
                output_dir=root / "model-run-renewed",
            )
            current = resolve_current_full_model_regression_parent(root)

            self.assertNotEqual(
                first.parent_receipt_fingerprint,
                second.parent_receipt_fingerprint,
            )
            self.assertNotEqual(first.parent_receipt_path, second.parent_receipt_path)
            self.assertEqual(first_bytes, first_path.read_bytes())
            self.assertEqual(second.parent_receipt_path, current.parent_artifact_path)
            self.assertEqual(
                second.parent_receipt_fingerprint,
                current.parent_artifact_fingerprint,
            )
            self.assertEqual(
                2,
                len(tuple(first_path.parent.glob("*.json"))),
            )

    def test_full_run_renews_parent_only_stale_wrapper_without_replacing_leaves(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self.current_parent_fixture(root)
            first_path = Path(first.parent_receipt_path)
            first_bytes = first_path.read_bytes()
            first_child = first.results[0]
            parent_only_input = root / "flowguard" / "model_regressions.py"
            parent_only_input.parent.mkdir(parents=True)
            parent_only_input.write_text(
                "PARENT_ONLY_VALUE = 1\n",
                encoding="utf-8",
            )

            second = run_manifest_regressions(
                root,
                tier="full",
                output_dir=root / "model-run-parent-only-renewed",
            )
            current = resolve_current_full_model_regression_parent(root)
            second_child = second.results[0]
            first_parent = json.loads(first_path.read_text(encoding="utf-8"))
            second_parent = json.loads(
                Path(second.parent_receipt_path).read_text(encoding="utf-8")
            )

            self.assertEqual(
                first_parent["children"][0]["receipt_id"],
                second_parent["children"][0]["receipt_id"],
            )
            self.assertEqual(
                first_child.receipt_fingerprint,
                second_child.receipt_fingerprint,
            )
            self.assertEqual("reuse_current", second_child.execution_disposition)
            self.assertEqual(0, second_child.producer_invocations)
            self.assertNotEqual(
                first.parent_receipt_fingerprint,
                second.parent_receipt_fingerprint,
            )
            self.assertNotEqual(first.parent_receipt_path, second.parent_receipt_path)
            self.assertEqual(first_bytes, first_path.read_bytes())
            self.assertEqual(second.parent_receipt_path, current.parent_artifact_path)
            self.assertEqual(
                second.parent_receipt_fingerprint,
                current.parent_artifact_fingerprint,
            )
            self.assertEqual(
                2,
                len(tuple(first_path.parent.glob("*.json"))),
            )

    def test_current_parent_resolver_does_not_treat_retired_v1_as_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.current_parent_fixture(root)
            parent_dir = Path(report.parent_receipt_path).parent
            (parent_dir / "retired-v1-history.json").write_text(
                json.dumps(
                    {
                        "schema_version": (
                            "flowguard.model_regression_parent_receipt.v1"
                        ),
                        "historical_only": True,
                    }
                ),
                encoding="utf-8",
            )

            current = resolve_current_full_model_regression_parent(root)

            self.assertEqual(
                report.parent_receipt_fingerprint,
                current.parent_artifact_fingerprint,
            )

    def test_current_parent_resolver_blocks_unknown_store_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.current_parent_fixture(root)
            parent_dir = Path(report.parent_receipt_path).parent
            (parent_dir / "unknown.json").write_text(
                json.dumps({"schema_version": "unknown.parent.v99"}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ModelRegressionEvidenceError,
                "unknown model parent schema",
            ):
                resolve_current_full_model_regression_parent(root)

    def test_current_full_parent_resolver_rejects_no_matching_parent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.current_parent_fixture(root)
            manifest_path = root / ".flowguard" / "model-regression-manifest.json"
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest_path.write_text(
                json.dumps(manifest_payload, indent=2) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ModelRegressionEvidenceError,
                "no exact-current full/full/pass",
            ):
                resolve_current_full_model_regression_parent(root)

    def test_current_full_parent_resolver_rejects_multiple_matching_parents(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.current_parent_fixture(root)
            parent_path = Path(report.parent_receipt_path)
            alternate = json.loads(parent_path.read_text(encoding="utf-8"))
            alternate["claim_boundary"] += " Alternate current wrapper."
            self.write_parent_artifact(parent_path.parent, alternate)

            with self.assertRaisesRegex(
                ModelRegressionEvidenceError,
                "ambiguous exact-current full model parent",
            ):
                resolve_current_full_model_regression_parent(root)

    def test_current_full_parent_resolver_rejects_missing_child_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.current_parent_fixture(root)
            parent = json.loads(
                Path(report.parent_receipt_path).read_text(encoding="utf-8")
            )
            child_id = parent["children"][0]["receipt_id"]
            child_path = receipt_path(
                child_id,
                root,
                output_directory=(
                    root / ".flowguard" / "evidence" / "model-owner-receipts"
                ),
            )
            child_path.unlink()

            with self.assertRaisesRegex(
                ModelRegressionEvidenceError,
                "child receipt is missing or invalid",
            ):
                resolve_current_full_model_regression_parent(root)

    def test_current_full_parent_resolver_rejects_wrong_child_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.current_parent_fixture(root)
            parent_path = Path(report.parent_receipt_path)
            parent = json.loads(parent_path.read_text(encoding="utf-8"))
            parent_path.unlink()
            parent["children"][0]["receipt_fingerprint"] = (
                "sha256:" + "f" * 64
            )
            self.write_parent_artifact(parent_path.parent, parent)

            with self.assertRaisesRegex(
                ModelRegressionEvidenceError,
                "child fingerprint does not match",
            ):
                resolve_current_full_model_regression_parent(root)

    def test_current_full_parent_resolver_rejects_noncurrent_child(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.current_parent_fixture(root)
            (root / ".flowguard" / "alpha" / "support.py").write_text(
                "VALUE = 2\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ModelRegressionEvidenceError,
                "child evidence is not exact-current",
            ):
                resolve_current_full_model_regression_parent(root)

    def test_current_full_parent_resolver_rejects_parent_as_child(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = self.current_parent_fixture(root)
            parent_path = Path(report.parent_receipt_path)
            parent = json.loads(parent_path.read_text(encoding="utf-8"))
            parent_path.unlink()
            parent["children"][0]["receipt_id"] = parent[
                "execution_receipt_id"
            ]
            parent["children"][0]["receipt_fingerprint"] = parent[
                "execution_receipt_fingerprint"
            ]
            self.write_parent_artifact(parent_path.parent, parent)

            with self.assertRaisesRegex(
                ModelRegressionEvidenceError,
                "cannot claim itself as a child",
            ):
                resolve_current_full_model_regression_parent(root)

    def test_required_public_model_entries_are_tracked_release_files(self):
        git = shutil.which("git")
        if not git:
            self.skipTest("git is required to verify public model distribution")
        root = Path(__file__).resolve().parents[1]
        repository_probe = subprocess.run(
            [git, "rev-parse", "--is-inside-work-tree"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        if repository_probe.returncode != 0:
            self.skipTest("public model distribution check requires a git checkout")
        completed = subprocess.run([git, "ls-files", "-z"], cwd=root, capture_output=True, check=True)
        tracked = {
            item.decode("utf-8", errors="surrogateescape").replace("\\", "/")
            for item in completed.stdout.split(b"\0")
            if item
        }
        manifest = ModelRegressionManifest.load(root)
        for entry in manifest.entries:
            with self.subTest(model=entry.model_id):
                if entry.distribution_policy == "required_public":
                    self.assertIn(entry.model_path, tracked)
                    self.assertIn(entry.runner[1], tracked)
                else:
                    self.assertGreaterEqual(len(entry.absence_reason), 12)

    def test_ui_content_visibility_model_accepts_external_output_directory(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            env = os.environ.copy()
            env["FLOWGUARD_OUTPUT_DIR"] = directory
            completed = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import runpy; "
                        "model = runpy.run_path('.flowguard/harden_ui_content_visibility_validation/model.py'); "
                        "print(model['CORE_PYTEST_ARGS'][-1])"
                    ),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(0, completed.returncode, completed.stderr)
            self.assertIn(Path(directory).resolve().as_posix(), completed.stdout.replace("\\", "/"))

    def test_unregistered_and_extra_records_are_both_visible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            present = root / ".flowguard" / "present"
            present.mkdir(parents=True)
            present.joinpath("model.py").write_text("if __name__ == '__main__': pass\n", encoding="utf-8")
            payload = {
                "schema_version": MANIFEST_SCHEMA,
                "governed_input_globs": [".flowguard/**/model.py"],
                "snapshot_only_input_globs": [],
                "shared_input_groups": [],
                "models": [self.entry("extra", root)],
            }
            manifest_path = root / ".flowguard" / "model-regression-manifest.json"
            manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            audit = audit_manifest(root, ModelRegressionManifest.load(root))
            self.assertFalse(audit.ok)
            self.assertTrue(any("unregistered model directory: present" in item for item in audit.errors))
            self.assertTrue(any("manifest required-public model missing from filesystem: extra" in item for item in audit.errors))

    def test_absent_optional_local_record_is_explicit_but_not_a_public_blocker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".flowguard").mkdir()
            entry = {
                **self.entry("local_only", root),
                "distribution_policy": "optional_local",
                "absence_reason": "This checkout-local model is executed only when its adoption record is present.",
            }
            (root / ".flowguard" / "model-regression-manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": MANIFEST_SCHEMA,
                        "governed_input_globs": [".flowguard/**/model.py"],
                        "snapshot_only_input_globs": [],
                        "shared_input_groups": [],
                        "models": [entry],
                    }
                ),
                encoding="utf-8",
            )
            audit = audit_manifest(root, ModelRegressionManifest.load(root))
            self.assertTrue(audit.ok, audit.errors)

    def test_invalid_runner_and_unjustified_exclusion_fail_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_dir = root / ".flowguard" / "sample"
            model_dir.mkdir(parents=True)
            model_dir.joinpath("model.py").write_text("print('model')\n", encoding="utf-8")
            payload = {
                "schema_version": MANIFEST_SCHEMA,
                "governed_input_globs": [".flowguard/**/model.py"],
                "snapshot_only_input_globs": [],
                "shared_input_groups": [],
                "models": [{**self.entry("sample", root), "runner": [], "exclusion_reason": "short"}],
            }
            (root / ".flowguard" / "model-regression-manifest.json").write_text(json.dumps(payload), encoding="utf-8")
            audit = audit_manifest(root, ModelRegressionManifest.load(root))
            self.assertFalse(audit.ok)
            self.assertTrue(any("exclusion reason" in item for item in audit.errors))

    def test_new_governed_source_without_owner_blocks_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model_dir = root / ".flowguard" / "owned"
            model_dir.mkdir(parents=True)
            model_dir.joinpath("model.py").write_text("VALUE = 1\n", encoding="utf-8")
            model_dir.joinpath("run_checks.py").write_text("print('ok')\n", encoding="utf-8")
            model_dir.joinpath("unmapped.py").write_text("VALUE = 2\n", encoding="utf-8")
            payload = {
                "schema_version": MANIFEST_SCHEMA,
                "governed_input_globs": [".flowguard/**/*.py"],
                "snapshot_only_input_globs": [],
                "shared_input_groups": [],
                "models": [self.entry("owned", root)],
            }
            path = root / ".flowguard" / "model-regression-manifest.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            impact = compile_model_impact_map(
                root,
                ModelRegressionManifest.load(root),
            )

            self.assertFalse(impact.ok)
            self.assertTrue(
                any("unmapped.py" in item for item in impact.errors),
                impact.errors,
            )

    def test_shared_component_maps_only_declared_consumers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shared = root / "shared"
            shared.mkdir()
            shared.joinpath("engine.py").write_text("VALUE = 1\n", encoding="utf-8")
            models = []
            for model_id in ("alpha", "beta"):
                model_dir = root / ".flowguard" / model_id
                model_dir.mkdir(parents=True)
                model_dir.joinpath("model.py").write_text("VALUE = 1\n", encoding="utf-8")
                model_dir.joinpath("run_checks.py").write_text("print('ok')\n", encoding="utf-8")
                models.append(self.entry(model_id, root))
            payload = {
                "schema_version": MANIFEST_SCHEMA,
                "governed_input_globs": [
                    ".flowguard/**/model.py",
                    "shared/**/*.py",
                ],
                "snapshot_only_input_globs": [],
                "shared_input_groups": [
                    {
                        "component_id": "alpha-engine",
                        "globs": ["shared/**/*.py"],
                        "consumers": ["alpha"],
                    }
                ],
                "models": models,
            }
            path = root / ".flowguard" / "model-regression-manifest.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            impact = compile_model_impact_map(
                root,
                ModelRegressionManifest.load(root),
            )

            self.assertTrue(impact.ok, impact.errors)
            self.assertEqual(("alpha",), impact.owners_by_path["shared/engine.py"])

    def test_old_or_unknown_manifest_shape_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".flowguard").mkdir()
            path = root / ".flowguard" / "model-regression-manifest.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": "flowguard.model_regression_manifest.v3",
                        "models": [],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ModelRegressionManifestError):
                ModelRegressionManifest.load(root)

            path.write_text(
                json.dumps(
                    {
                        "schema_version": MANIFEST_SCHEMA,
                        "governed_input_globs": ["flowguard/**/*.py"],
                        "snapshot_only_input_globs": [],
                        "shared_input_groups": [],
                        "models": [],
                        "fallback_run_all": True,
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ModelRegressionManifestError):
                ModelRegressionManifest.load(root)

    def current_parent_fixture(self, root: Path):
        model_dir = root / ".flowguard" / "alpha"
        model_dir.mkdir(parents=True)
        model_dir.joinpath("model.py").write_text(
            "VALUE = 1\n",
            encoding="utf-8",
        )
        model_dir.joinpath("run_checks.py").write_text(
            "raise SystemExit(0)\n",
            encoding="utf-8",
        )
        model_dir.joinpath("support.py").write_text(
            "VALUE = 1\n",
            encoding="utf-8",
        )
        entry = self.entry("alpha", root)
        entry["input_globs"] = [".flowguard/alpha/*.py"]
        manifest_path = root / ".flowguard" / "model-regression-manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": MANIFEST_SCHEMA,
                    "governed_input_globs": [".flowguard/**/*.py"],
                    "snapshot_only_input_globs": [],
                    "shared_input_groups": [],
                    "models": [entry],
                }
            ),
            encoding="utf-8",
        )
        return run_manifest_regressions(
            root,
            tier="full",
            output_dir=root / "model-run",
        )

    @staticmethod
    def write_parent_artifact(parent_dir: Path, payload):
        current = dict(payload)
        current.pop("parent_receipt_fingerprint", None)
        identity = fingerprint_value(current)
        current["parent_receipt_fingerprint"] = identity
        path = parent_dir / (identity.split(":", 1)[1] + ".json")
        path.write_text(
            json.dumps(
                current,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    @staticmethod
    def entry(model_id: str, root: Path) -> dict[str, object]:
        model_path = root / ".flowguard" / model_id / "model.py"
        runner_path = root / ".flowguard" / model_id / "run_checks.py"
        zero = "sha256:" + "0" * 64
        purpose = build_model_purpose_closure(
            model_instance_id=f"regression:{model_id}:current",
            reusable_model_type_id=model_id,
            task_intent_id=f"flowguard-regression:{model_id}",
            guarded_purpose=f"Prevent the {model_id} model from accepting an invalid current outcome as completed evidence.",
            protected_failure_ids=(f"{model_id}:invalid",),
            known_good_case_id=f"native-runner:{model_id}:good",
            failure_bindings=({
                "failure_id": f"{model_id}:invalid",
                "known_bad_case_id": f"native-runner:{model_id}:bad",
                "oracle_id": f"native:{model_id}:runner",
            },),
            claim_boundary=f"Current {model_id} fixture closure proves only the declared temporary test boundary and no production behavior.",
            evidence_check_ids=(f"check:model-regression:{model_id}",),
            model_sha256=file_fingerprint(model_path) if model_path.is_file() else zero,
            runner_sha256=file_fingerprint(runner_path) if runner_path.is_file() else zero,
        )
        return {
            "model_id": model_id,
            "model_path": f".flowguard/{model_id}/model.py",
            "runner": ["{python}", f".flowguard/{model_id}/run_checks.py"],
            "tier": "full",
            "timeout_seconds": 10,
            "shard_safe": True,
            "mutation_policy": "none",
            "input_globs": [f".flowguard/{model_id}/model.py"],
            "expected_artifacts": [],
            "exclusion_reason": "",
            "purpose_closure": purpose.to_dict(),
        }


if __name__ == "__main__":
    unittest.main()

import json
import gzip
import tempfile
import textwrap
import threading
import unittest
from concurrent.futures import Future
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import flowguard.model_regressions as model_regressions
import flowguard.behavior_surface_audit as behavior_surface_audit
from flowguard.model_regressions import MANIFEST_SCHEMA, run_manifest_regressions
from flowguard.model_purpose import build_model_purpose_closure, file_fingerprint
from flowguard.process_supervision import (
    SupervisedCommandResult,
    _attest_supervised_result,
)
from flowguard.validation_ownership import ValidationOwnerPlanRow
from flowguard.validation_results import ValidationChildResult
from flowguard.evidence_receipts import list_evidence_receipts
import flowguard.validation_ownership as validation_ownership


class ModelRegressionOrchestratorTests(unittest.TestCase):
    def make_repo(self, specs: list[dict[str, object]]) -> Path:
        root = Path(tempfile.mkdtemp(prefix="flowguard-model-regression-", dir=self.tempdir.name))
        models = []
        for spec in specs:
            model_id = str(spec["model_id"])
            model_dir = root / ".flowguard" / "models" / "owners" / model_id
            runner_dir = root / ".flowguard" / "verification" / "owners" / model_id
            model_dir.mkdir(parents=True)
            runner_dir.mkdir(parents=True)
            model_dir.joinpath("model.py").write_text("VALUE = 1\n", encoding="utf-8")
            runner_dir.joinpath("run_checks.py").write_text(str(spec["script"]), encoding="utf-8")
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
                model_sha256=file_fingerprint(model_dir / "model.py"),
                runner_sha256=file_fingerprint(runner_dir / "run_checks.py"),
            )
            models.append(
                {
                    "model_id": model_id,
                    "model_path": f".flowguard/models/owners/{model_id}/model.py",
                    "runner": ["{python}", f".flowguard/verification/owners/{model_id}/run_checks.py"],
                    "tier": spec.get("tier", "fast"),
                    "timeout_seconds": spec.get("timeout_seconds", 5),
                    "shard_safe": spec.get("shard_safe", True),
                    "mutation_policy": spec.get("mutation_policy", "none"),
                    "input_globs": [f".flowguard/models/owners/{model_id}/model.py", f".flowguard/verification/owners/{model_id}/run_checks.py"],
                    "expected_artifacts": spec.get("expected_artifacts", []),
                    "exclusion_reason": "",
                    "purpose_closure": purpose.to_dict(),
                }
            )
        (root / ".flowguard" / "models" / "regression-manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": MANIFEST_SCHEMA,
                    "governed_input_globs": [".flowguard/**/*.py"],
                    "snapshot_only_input_globs": [],
                    "shared_input_groups": [],
                    "models": models,
                }
            ),
            encoding="utf-8",
        )
        return root

    @staticmethod
    def controlled_model_result(
        model_id: str,
        *,
        cleanup_confirmed: bool,
    ) -> model_regressions.ModelRunResult:
        supervision = _attest_supervised_result(
            SupervisedCommandResult(
                command=("controlled-owner",),
                cwd="<controlled-fixture>",
                episode_token=f"episode:controlled:{model_id}",
                started_at_epoch=1.0,
                finished_at_epoch=2.0,
                exit_code=0,
                stdout="",
                stderr="",
                terminal_reason=(
                    "process_exit" if cleanup_confirmed else "cleanup_unconfirmed"
                ),
                timed_out=False,
                cancelled=False,
                interrupted=False,
                termination_stage="none",
                cleanup_confirmed=cleanup_confirmed,
                descendant_process_ids=(),
            )
        )
        return model_regressions.ModelRunResult(
            model_id=model_id,
            status="pass" if cleanup_confirmed else "internal_error",
            exit_code=0,
            seconds=0.0,
            command=("controlled-owner",),
            stdout_path="",
            stderr_path="",
            receipt_path="",
            supervision=supervision,
        )

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tempdir.cleanup()

    def projection_mapping_fixture(self):
        from flowguard.native_case_mapping import (
            NativeCaseMappingRegistry, compute_native_case_mapping_fingerprint,
        )
        from flowguard.native_case_protocol import GOOD_DIMENSIONS, NativeCaseBinding
        from flowguard.source_identity import source_file_fingerprint

        root = self.make_repo([
            {"model_id": "alpha", "script": "print('alpha')\n"},
            {"model_id": "beta", "script": "print('beta')\n"},
        ])
        manifest = model_regressions.ModelRegressionManifest.load(root)
        rows = tuple(NativeCaseBinding(
            owner_id="model:" + owner,
            blueprint_case_id="behavior-case:" + case,
            blueprint_source_case_id=case,
            native_case_ids=("native:" + case,),
            case_kind="good", evidence_scope="model_policy",
            covered_dimensions=GOOD_DIMENSIONS, expected_status="pass",
        ) for owner, case in (("alpha", "first"), ("alpha", "second"), ("beta", "third")))
        source_fp = source_file_fingerprint(root / ".flowguard/models/regression-manifest.json")
        path = root / ".flowguard/models/native-case-mapping.json"

        def publish(bindings):
            mapping_fp = compute_native_case_mapping_fingerprint(
                source_manifest_fingerprint=source_fp, source_paths=(), bindings=bindings,
            )
            registry = NativeCaseMappingRegistry(
                mapping_fingerprint=mapping_fp, source_manifest_fingerprint=source_fp,
                source_paths=(), bindings=tuple(replace(row, mapping_fingerprint=mapping_fp) for row in bindings),
            )
            payload = registry.to_dict()
            path.write_text(json.dumps(payload), encoding="utf-8")
            return payload

        return root, manifest, rows, path, publish

    def test_owner_projection_ignores_only_two_native_provenance_fields(self):
        import copy

        root, manifest, rows, _path, publish = self.projection_mapping_fixture()
        payload = publish(rows)
        entry = next(row for row in manifest.entries if row.model_id == "alpha")
        baseline = manifest._owner_projection_fingerprint(
            entry, root=root, native_case_mapping_payload=payload,
        )
        for field in ("mapping_fingerprint", "binding_fingerprint"):
            with self.subTest(field=field):
                changed = copy.deepcopy(payload)
                # Reverse the derived fingerprint order of the two alpha rows:
                # provenance must be excluded before canonical row sorting too.
                for index, row in enumerate(changed["bindings"]):
                    row[field] = "sha256:" + ("f" if index == 0 else "0") * 64
                self.assertEqual(baseline, manifest._owner_projection_fingerprint(
                    entry, root=root, native_case_mapping_payload=changed,
                ))
        # The same names in owner-bindings remain semantic, not excluded.
        owner_path = root / ".flowguard/structure/owner-bindings.json"
        owner_path.parent.mkdir(parents=True)
        owner_payload = {"bindings": [{"owner_id": "model:alpha", "model_ids": ["alpha"]}]}
        owner_path.write_text(json.dumps(owner_payload), encoding="utf-8")
        bound = manifest.owner_projection_fingerprint(entry, root=root)
        for field in ("mapping_fingerprint", "binding_fingerprint"):
            with self.subTest(owner_binding_field=field):
                changed = copy.deepcopy(owner_payload)
                changed["bindings"][0][field] = "owner-specific semantic declaration"
                owner_path.write_text(json.dumps(changed), encoding="utf-8")
                self.assertNotEqual(bound, manifest.owner_projection_fingerprint(entry, root=root))

    def test_owner_projection_tracks_native_semantics_and_unknown_fields(self):
        import copy

        root, manifest, rows, _path, publish = self.projection_mapping_fixture()
        payload = publish(rows)
        entry = next(row for row in manifest.entries if row.model_id == "alpha")
        before = manifest.owner_projection_fingerprint(entry, root=root)
        changed_rows = (replace(rows[0], required_trace_labels=("alpha:required-trace",)), *rows[1:])
        publish(changed_rows)
        self.assertNotEqual(before, manifest.owner_projection_fingerprint(entry, root=root))
        for field, value in (("native_case_ids", ["native:different"]),
                             ("required_child_case_ids", ["model:alpha::child"]),
                             ("future_semantic_obligation", {"must_preserve": True})):
            with self.subTest(field=field):
                changed = copy.deepcopy(payload)
                changed["bindings"][0][field] = value
                # The projection preserves unknown semantic fields too; the
                # public loader independently rejects undeclared schema fields.
                self.assertNotEqual(before, manifest._owner_projection_fingerprint(
                    entry, root=root, native_case_mapping_payload=changed,
                ))

    def test_owner_projection_batch_validates_once_and_is_fresh_across_calls(self):
        from flowguard.native_case_mapping import load_native_case_mapping

        root, manifest, rows, _path, publish = self.projection_mapping_fixture()
        first_payload = publish(rows)
        with patch.object(model_regressions, "load_native_case_mapping", wraps=load_native_case_mapping) as load:
            first = model_regressions._model_owner_contracts(root, manifest, manifest.entries)
        self.assertEqual(1, load.call_count)
        second_payload = publish((*rows[:2], replace(rows[2], required_trace_labels=("beta:changed",))))
        self.assertNotEqual(first_payload["bindings"][0]["mapping_fingerprint"], second_payload["bindings"][0]["mapping_fingerprint"])
        self.assertNotEqual(first_payload["bindings"][0]["binding_fingerprint"], second_payload["bindings"][0]["binding_fingerprint"])
        with patch.object(model_regressions, "load_native_case_mapping", wraps=load_native_case_mapping) as load:
            second = model_regressions._model_owner_contracts(root, manifest, manifest.entries)
        self.assertEqual(1, load.call_count)
        by_owner = lambda contracts: {row.owner_id: row.projected_inputs for row in contracts}
        self.assertEqual(by_owner(first)["model:alpha"], by_owner(second)["model:alpha"])
        self.assertNotEqual(by_owner(first)["model:beta"], by_owner(second)["model:beta"])

    def test_owner_projection_rejects_invalid_complete_native_mapping(self):
        import copy
        from flowguard.native_case_mapping import NativeCaseMappingError

        root, manifest, rows, path, publish = self.projection_mapping_fixture()
        payload = publish(rows)
        alpha = next(row for row in manifest.entries if row.model_id == "alpha")
        baseline = manifest.owner_projection_fingerprint(alpha, root=root)
        for mutation in ("foreign_owner_binding_fingerprint", "root_fingerprint", "unknown_foreign_field", "current_manifest"):
            with self.subTest(mutation=mutation):
                changed = copy.deepcopy(payload)
                if mutation == "foreign_owner_binding_fingerprint":
                    changed["bindings"][2]["binding_fingerprint"] = "sha256:" + "0" * 64
                elif mutation == "root_fingerprint":
                    changed["mapping_fingerprint"] = "sha256:" + "0" * 64
                elif mutation == "unknown_foreign_field":
                    changed["bindings"][2]["undeclared_semantics"] = True
                path.write_text(json.dumps(changed), encoding="utf-8")
                manifest_path = root / ".flowguard/models/regression-manifest.json"
                original = manifest_path.read_text(encoding="utf-8")
                if mutation == "current_manifest":
                    manifest_path.write_text(original + "\n", encoding="utf-8")
                try:
                    with self.assertRaises(NativeCaseMappingError):
                        manifest.owner_projection_fingerprint(alpha, root=root)
                finally:
                    manifest_path.write_text(original, encoding="utf-8")
        path.write_text(json.dumps(payload), encoding="utf-8")
        self.assertEqual(baseline, manifest.owner_projection_fingerprint(alpha, root=root))
        original_read_bytes = Path.read_bytes
        mapping_reads = []

        def drift_after_validation(current_path):
            body = original_read_bytes(current_path)
            if current_path == path:
                mapping_reads.append(current_path)
                if len(mapping_reads) == 2:
                    return body + b"\n"
            return body

        with patch.object(Path, "read_bytes", drift_after_validation):
            with self.assertRaisesRegex(NativeCaseMappingError, "changed during"):
                manifest.owner_projection_fingerprint(alpha, root=root)
        self.assertEqual(2, len(mapping_reads))
        declared = replace(manifest, shared_input_groups=(model_regressions.SharedInputGroup(
            component_id="flowguard-native-owner-bindings",
            globs=(".flowguard/models/native-case-mapping.json",),
            consumers=("alpha", "beta"),
        ),))
        path.unlink()
        with self.assertRaisesRegex(NativeCaseMappingError, "missing"):
            declared.owner_projection_fingerprints(declared.entries, root=root)

    def test_serial_leaf_is_durable_before_later_failure_and_reused_on_retry(self):
        script = "from pathlib import Path\np=Path('beta-attempts.txt')\nn=int(p.read_text())+1 if p.exists() else 1\np.write_text(str(n))\nraise SystemExit(1 if n == 1 else 0)\n"
        root = self.make_repo([
            {"model_id": "alpha", "script": "print('alpha')\n"},
            {"model_id": "beta", "script": script},
            {"model_id": "gamma", "script": "print('gamma')\n"},
        ])
        receipts = root / ".flowguard" / "evidence" / "model-owner-receipts"
        seen = []

        def progress(event):
            if event["event"] == "started":
                seen.append(event["model_id"])
                if event["model_id"] == "beta":
                    evidence = list_evidence_receipts(root, output_directory=receipts, subject_ids=("validation-owner:model:alpha",))
                    self.assertEqual(1, len(evidence))
                    self.assertEqual("pass", evidence[0].result_status)

        with patch.object(model_regressions, "_tracked_paths", return_value=()):
            first = run_manifest_regressions(root, tier="full", jobs=1, output_dir=root / "outputs" / "first", progress=progress)
            second = run_manifest_regressions(root, tier="full", jobs=1, output_dir=root / "outputs" / "second")
        self.assertEqual("blocked", first.status)  # Required gamma was not run.
        self.assertEqual("fail", next(row for row in first.results if row.model_id == "beta").status)
        self.assertEqual(["alpha", "beta"], seen)
        self.assertEqual(("gamma",), first.skipped_model_ids)
        self.assertEqual(4, first.per_leaf_source_current_rebuild_count)
        self.assertTrue(second.ok, second.to_dict())
        rows = {row.model_id: row for row in second.results}
        self.assertEqual("reuse_current", rows["alpha"].execution_disposition)
        self.assertEqual(0, rows["alpha"].producer_invocations)
        self.assertEqual("execute", rows["beta"].execution_disposition)

    def test_serial_pre_leaf_input_drift_starts_no_producer(self):
        root = self.make_repo([{"model_id": "alpha", "script": "print('alpha')\n"}])
        original = model_regressions._assert_validation_owner_current_fresh

        def drift(*args):
            (root / ".flowguard/models/owners/alpha/model.py").write_text("VALUE = 2\n", encoding="utf-8")
            return original(*args)

        with patch.object(model_regressions, "_assert_validation_owner_current_fresh", side_effect=drift), patch.object(model_regressions, "_run_entry") as run:
            with self.assertRaisesRegex(ValueError, "inputs changed"):
                run_manifest_regressions(root, tier="full", output_dir=root / "outputs" / "drift")
        run.assert_not_called()

    def test_stale_live_discovery_blocks_map_owner_before_observation_or_producer(self):
        root = self.make_repo(
            [{"model_id": "alpha", "tier": "full", "script": "print('alpha')\n"}]
        )
        manifest_path = root / ".flowguard/models/regression-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["models"][0]["input_globs"].append(
            ".flowguard/structure/reverse-surfaces/implementation-surface-map.json"
        )
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        audit = model_regressions.ManifestAudit(
            True,
            ("alpha",),
            ("alpha",),
            (),
        )
        with (
            patch.object(model_regressions, "audit_manifest", return_value=audit),
            patch.object(
                behavior_surface_audit,
                "capture_current_implementation_surface_discovery",
                side_effect=ValueError("live source fingerprint is stale"),
            ) as capture_discovery,
            patch.object(model_regressions, "observe_validation_owners") as observe,
            patch.object(model_regressions, "_run_entry") as run_entry,
        ):
            with self.assertRaisesRegex(
                model_regressions.ModelRegressionEvidenceError,
                "live discovery/map currentness failed",
            ):
                run_manifest_regressions(
                    root,
                    tier="full",
                    jobs=1,
                    output_dir=root / "outputs" / "stale-discovery",
                )
        capture_discovery.assert_called_once_with(root.resolve())
        observe.assert_not_called()
        run_entry.assert_not_called()

    def test_serial_post_leaf_input_drift_publishes_no_success(self):
        root = self.make_repo([{"model_id": "alpha", "script": "print('alpha')\n"}])
        original = model_regressions._run_entry

        def drift(*args, **kwargs):
            result = original(*args, **kwargs)
            (root / ".flowguard/models/owners/alpha/model.py").write_text("VALUE = 2\n", encoding="utf-8")
            return result

        with patch.object(model_regressions, "_run_entry", side_effect=drift), patch.object(model_regressions, "_persist_model_owner_result") as publish:
            with self.assertRaisesRegex(ValueError, "inputs changed"):
                run_manifest_regressions(root, tier="full", output_dir=root / "outputs" / "drift")
        publish.assert_not_called()

    def test_serial_cleanup_unconfirmed_stops_before_freshness_and_preserves_lease(self):
        root = self.make_repo([
            {"model_id": "alpha", "script": "print('alpha')\n"},
            {"model_id": "beta", "script": "print('beta')\n"},
        ])
        original = model_regressions._run_entry
        original_check = model_regressions._assert_validation_owner_current_fresh
        calls = []

        def unconfirmed(*args, **kwargs):
            calls.append(args[1].model_id)
            result = original(*args, **kwargs)
            return replace(result, status="internal_error", finding_codes=("model.cleanup_unconfirmed",))

        with patch.object(model_regressions, "_run_entry", side_effect=unconfirmed), patch.object(model_regressions, "_assert_validation_owner_current_fresh", wraps=original_check) as check, patch.object(model_regressions, "_persist_model_owner_result") as publish:
            report = run_manifest_regressions(root, tier="full", output_dir=root / "outputs" / "cleanup")
        self.assertFalse(report.ok)
        self.assertEqual(["alpha"], calls)
        self.assertEqual(1, check.call_count)
        publish.assert_not_called()
        lease_root = root / ".flowguard/evidence/model-owner-receipts/leases"
        residuals = tuple(lease_root.glob("execution-*.lock"))
        self.assertEqual(1, len(residuals))
        self.assertEqual("cleanup_unconfirmed", json.loads(residuals[0].read_text(encoding="utf-8"))["cleanup_status"])

    def test_parallel_cleanup_unconfirmed_survives_sibling_future_exception(self):
        root = self.make_repo([
            {"model_id": "alpha", "script": "print('alpha')\n"},
            {"model_id": "beta", "script": "print('beta')\n"},
            {"model_id": "gamma", "script": "print('gamma')\n"},
        ])
        alpha_returned = threading.Event()

        def controlled_run(_root, entry, _output, **_kwargs):
            if entry.model_id == "alpha":
                result = self.controlled_model_result(
                    "alpha", cleanup_confirmed=False,
                )
                alpha_returned.set()
                return result
            if entry.model_id == "beta":
                self.assertTrue(
                    alpha_returned.wait(timeout=5),
                    "alpha must reach its terminal fixture before beta fails",
                )
                raise OSError("controlled sibling future failure")
            return self.controlled_model_result(
                "gamma", cleanup_confirmed=True,
            )

        receipt_root = root / ".flowguard/evidence/model-owner-receipts"
        with (
            patch.object(model_regressions, "_run_entry", side_effect=controlled_run),
            patch.object(model_regressions, "_persist_model_owner_result") as child_publish,
            patch.object(model_regressions, "_write_model_parent_receipt") as parent_publish,
        ):
            with self.assertRaisesRegex(OSError, "controlled sibling future failure"):
                run_manifest_regressions(
                    root,
                    tier="full",
                    jobs=3,
                    output_dir=root / "outputs" / "sibling-future-failure",
                )

        child_publish.assert_not_called()
        parent_publish.assert_not_called()
        self.assertEqual(
            (),
            list_evidence_receipts(root, output_directory=receipt_root),
        )
        residuals = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (receipt_root / "leases").glob("execution-*.lock")
        ]
        self.assertEqual(
            {"model:alpha", "model:beta"},
            {row["owner_id"] for row in residuals},
        )
        self.assertEqual(2, len(residuals))
        for row in residuals:
            self.assertEqual("cleanup_unconfirmed", row["cleanup_status"])
            self.assertTrue(row["incident_episode_token"])
            with self.assertRaisesRegex(ValueError, "already leased"):
                with model_regressions.evidence_execution_lease(
                    receipt_root / "leases",
                    owner_id=row["owner_id"],
                    resource_key=row["resource_key"],
                    execution_key=row["execution_key"],
                ):
                    self.fail("uncertain cleanup must prevent an owner retry")

    def test_cleanup_unconfirmed_survives_terminal_artifact_write_error(self):
        for jobs in (1, 2):
            with self.subTest(jobs=jobs):
                root = self.make_repo([
                    {"model_id": "alpha", "script": "print('alpha')\n"},
                    {"model_id": "beta", "script": "print('beta')\n"},
                ])
                invoked = []
                results = []
                invoked_lock = threading.Lock()
                original_run_entry = model_regressions._run_entry

                def controlled_supervision(
                    _command,
                    *,
                    cwd,
                    environment,
                    timeout_seconds,
                    cancel_event,
                ):
                    model_id = environment["FLOWGUARD_MODEL_ID"]
                    with invoked_lock:
                        invoked.append(model_id)
                    return self.controlled_model_result(
                        model_id,
                        cleanup_confirmed=(model_id != "alpha"),
                    ).supervision

                def record_run_entry(*args, **kwargs):
                    result = original_run_entry(*args, **kwargs)
                    with invoked_lock:
                        results.append(result)
                    return result

                def fail_terminal_artifact(_path, _supervision):
                    raise OSError("controlled terminal artifact write failure")

                with (
                    patch.object(
                        model_regressions,
                        "run_supervised",
                        side_effect=controlled_supervision,
                    ),
                    patch.object(
                        model_regressions,
                        "write_terminal_artifact",
                        side_effect=fail_terminal_artifact,
                    ),
                    patch.object(
                        model_regressions,
                        "_run_entry",
                        side_effect=record_run_entry,
                    ),
                ):
                    report = run_manifest_regressions(
                        root,
                        tier="full",
                        jobs=jobs,
                        output_dir=root / "outputs" / f"artifact-write-{jobs}",
                    )

                self.assertFalse(report.ok)
                alpha = next(result for result in results if result.model_id == "alpha")
                self.assertIsNotNone(alpha.supervision)
                self.assertFalse(alpha.supervision.cleanup_confirmed)
                self.assertIn("model.cleanup_unconfirmed", alpha.finding_codes)
                self.assertIn(
                    "model.supervisor_terminal_artifact_write_error",
                    alpha.finding_codes,
                )
                self.assertIn("terminal artifact write failure", alpha.message)
                if jobs == 1:
                    self.assertEqual(["alpha"], invoked)
                else:
                    self.assertEqual({"alpha", "beta"}, set(invoked))
                parent_path = Path(report.parent_receipt_path)
                self.assertTrue(parent_path.is_file())
                parent = json.loads(parent_path.read_text(encoding="utf-8"))
                self.assertNotEqual("pass", parent["status"])
                self.assertEqual("", parent["execution_receipt_id"])
                self.assertFalse(
                    (root / ".flowguard/evidence/model-owner-receipts"
                     / "model-parents" / "CURRENT.json").exists()
                )

                receipt_root = root / ".flowguard/evidence/model-owner-receipts"
                residuals = [
                    json.loads(path.read_text(encoding="utf-8"))
                    for path in (receipt_root / "leases").glob("execution-*.lock")
                ]
                self.assertEqual({"model:alpha"}, {row["owner_id"] for row in residuals})
                self.assertEqual(
                    "episode:controlled:alpha",
                    residuals[0]["incident_episode_token"],
                )
                with self.assertRaisesRegex(ValueError, "already leased"):
                    with model_regressions.evidence_execution_lease(
                        receipt_root / "leases",
                        owner_id="model:alpha",
                        resource_key=residuals[0]["resource_key"],
                        execution_key=residuals[0]["execution_key"],
                    ):
                        self.fail("terminal artifact failure must not release alpha's lease")

    def test_parallel_interruption_preserves_unsettled_owner_leases(self):
        root = self.make_repo([
            {"model_id": "alpha", "script": "print('alpha')\n"},
            {"model_id": "beta", "script": "print('beta')\n"},
        ])
        beta_started = threading.Event()
        release_beta = threading.Event()
        executors = []

        class ControlledExecutor:
            """Keep one fixture Future running across simulated join interruption."""

            def __init__(self, *, max_workers, thread_name_prefix):
                self.threads = []
                executors.append(self)

            def __enter__(self):
                return self

            def __exit__(self, _exception_type, _exception, _traceback):
                # The test releases and joins these controlled threads after
                # the orchestrator has had to preserve its running owner's lease.
                return False

            def submit(self, function, *args, **kwargs):
                future = Future()
                if not future.set_running_or_notify_cancel():
                    return future

                def invoke():
                    try:
                        result = function(*args, **kwargs)
                    except BaseException as exc:
                        future.set_exception(exc)
                    else:
                        future.set_result(result)

                worker = threading.Thread(target=invoke, daemon=True)
                self.threads.append(worker)
                worker.start()
                return future

        def controlled_run(_root, entry, _output, **_kwargs):
            if entry.model_id == "alpha":
                self.assertTrue(
                    beta_started.wait(timeout=5),
                    "beta must be running when collection is interrupted",
                )
                return self.controlled_model_result(
                    "alpha", cleanup_confirmed=False,
                )
            beta_started.set()
            self.assertTrue(
                release_beta.wait(timeout=5),
                "the collection fixture must release beta during shutdown",
            )
            raise OSError("controlled worker ended without a terminal result")

        def interrupt_after_alpha(futures):
            submitted = tuple(futures)
            alpha_future = None
            for _ in range(500):
                for future in submitted:
                    if future.cancelled() or not future.done():
                        continue
                    try:
                        result = future.result()
                    except BaseException:
                        continue
                    if result.model_id == "alpha":
                        alpha_future = future
                        break
                if alpha_future is not None:
                    break
                threading.Event().wait(0.01)
            self.assertIsNotNone(alpha_future, "alpha fixture must finish before interruption")
            yield alpha_future
            raise KeyboardInterrupt("controlled future collection interruption")

        receipt_root = root / ".flowguard/evidence/model-owner-receipts"
        try:
            with (
                patch.object(model_regressions, "ThreadPoolExecutor", ControlledExecutor),
                patch.object(model_regressions, "_run_entry", side_effect=controlled_run),
                patch.object(model_regressions, "as_completed", side_effect=interrupt_after_alpha),
                patch.object(model_regressions, "_persist_model_owner_result") as child_publish,
                patch.object(model_regressions, "_write_model_parent_receipt") as parent_publish,
            ):
                with self.assertRaisesRegex(
                    KeyboardInterrupt,
                    "controlled future collection interruption",
                ):
                    run_manifest_regressions(
                        root,
                        tier="full",
                        jobs=2,
                        output_dir=root / "outputs" / "collection-interruption",
                    )
        finally:
            release_beta.set()
            for executor in executors:
                for worker in executor.threads:
                    worker.join(timeout=5)
                    self.assertFalse(worker.is_alive(), "controlled worker thread must terminate")

        child_publish.assert_not_called()
        parent_publish.assert_not_called()
        residuals = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (receipt_root / "leases").glob("execution-*.lock")
        ]
        self.assertEqual(
            {"model:alpha", "model:beta"},
            {row["owner_id"] for row in residuals},
        )
        self.assertEqual(2, len(residuals))
        for row in residuals:
            self.assertEqual("cleanup_unconfirmed", row["cleanup_status"])
            with self.assertRaisesRegex(ValueError, "already leased"):
                with model_regressions.evidence_execution_lease(
                    receipt_root / "leases",
                    owner_id=row["owner_id"],
                    resource_key=row["resource_key"],
                    execution_key=row["execution_key"],
                ):
                    self.fail("an owner without cleanup proof must remain leased")

    def test_parallel_cleanup_unconfirmed_survives_final_freshness_failure(self):
        root = self.make_repo([
            {"model_id": "alpha", "script": "print('alpha')\n"},
            {"model_id": "beta", "script": "print('beta')\n"},
            {"model_id": "gamma", "script": "print('gamma')\n"},
        ])
        original_run = model_regressions._run_entry
        original_check = model_regressions.assert_validation_owner_observation_fresh
        completed = []

        def unconfirmed(*args, **kwargs):
            result = original_run(*args, **kwargs)
            completed.append(result.model_id)
            if result.model_id in {"alpha", "beta"}:
                return replace(result, status="internal_error",
                               finding_codes=("model.cleanup_unconfirmed",))
            return result

        def drift(*args, **kwargs):
            self.assertEqual({"alpha", "beta", "gamma"}, set(completed))
            (root / ".flowguard/models/owners/alpha/model.py").write_text(
                "VALUE = 2\n", encoding="utf-8",
            )
            return original_check(*args, **kwargs)

        with (
            patch.object(model_regressions, "_run_entry", side_effect=unconfirmed),
            patch.object(model_regressions, "assert_validation_owner_observation_fresh",
                         side_effect=drift) as freshness,
            patch.object(model_regressions, "_persist_model_owner_result") as publish,
            patch.object(model_regressions, "_write_model_parent_receipt") as parent_publish,
        ):
            with self.assertRaisesRegex(ValueError, "repository_input_manifest_changed"):
                run_manifest_regressions(
                    root, tier="full", jobs=2,
                    output_dir=root / "outputs" / "parallel-cleanup-drift",
                )
        self.assertEqual(1, freshness.call_count)
        publish.assert_not_called()
        parent_publish.assert_not_called()
        receipt_root = root / ".flowguard/evidence/model-owner-receipts"
        self.assertEqual((), list_evidence_receipts(root, output_directory=receipt_root))
        residuals = [json.loads(path.read_text(encoding="utf-8"))
                     for path in (receipt_root / "leases").glob("execution-*.lock")]
        self.assertEqual({"model:alpha", "model:beta"},
                         {row["owner_id"] for row in residuals})
        self.assertEqual(2, len(residuals))
        for row in residuals:
            self.assertEqual("cleanup_unconfirmed", row["cleanup_status"])
            self.assertTrue(row["incident_episode_token"])
            with self.assertRaisesRegex(ValueError, "already leased"):
                with model_regressions.evidence_execution_lease(
                    receipt_root / "leases", owner_id=row["owner_id"],
                    resource_key=row["resource_key"], execution_key=row["execution_key"],
                ):
                    self.fail("unconfirmed residual must prevent another owner attempt")

    def test_parallel_missing_supervision_error_keeps_lease_without_leaf_receipt(self):
        root = self.make_repo([
            {"model_id": "alpha", "script": "print('alpha')\n"},
        ])
        result = replace(
            self.controlled_model_result("alpha", cleanup_confirmed=True),
            status="internal_error",
            supervision=None,
            finding_codes=("model.launch_error",),
            message="controlled launcher failure",
        )
        receipt_root = root / ".flowguard/evidence/model-owner-receipts"
        with patch.object(model_regressions, "_run_entry", return_value=result), patch.object(
            model_regressions, "_persist_model_owner_result"
        ) as publish:
            report = run_manifest_regressions(
                root,
                tier="full",
                jobs=2,
                output_dir=root / "outputs" / "missing-supervision",
            )

        self.assertFalse(report.ok)
        self.assertEqual(("model.launch_error",), report.results[0].finding_codes)
        publish.assert_not_called()
        self.assertEqual((), list_evidence_receipts(root, output_directory=receipt_root))
        self.assertFalse((receipt_root / "model-parents" / "CURRENT.json").exists())
        residuals = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (receipt_root / "leases").glob("execution-*.lock")
        ]
        self.assertEqual({"model:alpha"}, {row["owner_id"] for row in residuals})
        self.assertEqual("cleanup_unconfirmed", residuals[0]["cleanup_status"])

    def test_serial_ten_cheap_leaves_do_not_rebuild_whole_source_per_leaf(self):
        root = self.make_repo([{"model_id": f"m{index}", "script": "print('ok')\n"} for index in range(10)])
        with patch.object(validation_ownership, "resolve_input_manifest", wraps=validation_ownership.resolve_input_manifest) as resolve:
            report = run_manifest_regressions(root, tier="full", jobs=1, output_dir=root / "outputs" / "ten")
        self.assertTrue(report.ok, report.to_dict())
        # Two complete observations plus exactly two local checks per leaf.
        widths = [len(call.args[1]) for call in resolve.call_args_list]
        self.assertEqual(22, len(widths))
        self.assertEqual(2, widths.count(max(widths)))
        self.assertEqual(20, report.per_leaf_source_current_rebuild_count)
        self.assertEqual(0, report.per_leaf_receipt_store_scan_count)

    def test_serial_later_interruption_keeps_previous_leaf_and_stops_following_owner(self):
        root = self.make_repo([
            {"model_id": "alpha", "script": "print('alpha')\n"},
            {"model_id": "beta", "script": "print('beta')\n"},
            {"model_id": "gamma", "script": "print('gamma')\n"},
        ])
        original = model_regressions._run_entry
        calls = []

        def interrupt(*args, **kwargs):
            calls.append(args[1].model_id)
            if args[1].model_id == "beta":
                raise KeyboardInterrupt("fixture interruption")
            return original(*args, **kwargs)

        with patch.object(model_regressions, "_run_entry", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                run_manifest_regressions(root, tier="full", output_dir=root / "outputs" / "interrupted")
        self.assertEqual(["alpha", "beta"], calls)
        receipts = root / ".flowguard/evidence/model-owner-receipts"
        saved = list_evidence_receipts(root, output_directory=receipts, subject_ids=("validation-owner:model:alpha",))
        self.assertEqual(1, len(saved))
        self.assertEqual("pass", saved[0].result_status)
        self.assertEqual(1, len(tuple((receipts / "leases").glob("execution-*.lock"))))

    def test_timeout_produces_terminal_receipt_and_distinct_status(self):
        root = self.make_repo(
            [{"model_id": "slow", "script": "import time\ntime.sleep(10)\n", "timeout_seconds": 0.2}]
        )
        report = run_manifest_regressions(root, tier="full", output_dir=root / "outputs" / "out-timeout")
        self.assertEqual("timeout", report.status)
        receipt = json.loads(Path(report.results[0].receipt_path).read_text(encoding="utf-8"))
        self.assertEqual("1.0", receipt["schema_version"])
        self.assertEqual("error", receipt["result_status"])
        self.assertIn("owner_status:timeout", receipt["blockers"])
        result = report.results[0]
        self.assertEqual("regression:slow:current", result.model_instance_id)
        self.assertTrue(result.model_instance_fingerprint.startswith("sha256:"))
        self.assertEqual("executable_workflow", result.model_kind)
        self.assertTrue(result.input_inventory_fingerprint.startswith("sha256:"))
        self.assertEqual(
            [
                ".flowguard/models/owners/slow/model.py",
                ".flowguard/verification/owners/slow/run_checks.py",
            ],
            [item["path"] for item in result.input_inventory],
        )
        self.assertTrue(
            all(item["sha256"].startswith("sha256:") for item in result.input_inventory)
        )
        self.assertTrue(result.purpose_closure_fingerprint.startswith("sha256:"))

    def test_cancellation_is_propagated_to_child_receipt(self):
        root = self.make_repo([{"model_id": "slow", "script": "import time\ntime.sleep(10)\n"}])
        cancel = threading.Event()
        timer = threading.Timer(0.2, cancel.set)
        timer.start()
        try:
            report = run_manifest_regressions(
                root, tier="full", output_dir=root / "outputs" / "out-cancel", cancel_event=cancel
            )
        finally:
            timer.cancel()
        self.assertEqual("cancelled", report.status)
        self.assertEqual("cancelled", report.results[0].status)

    def test_parallel_run_rejects_non_shard_safe_entry(self):
        root = self.make_repo(
            [{"model_id": "unsafe", "script": "print('ok')\n", "shard_safe": False}]
        )
        with self.assertRaisesRegex(ValueError, "non-shard-safe"):
            run_manifest_regressions(root, tier="full", jobs=2, output_dir=root / "outputs" / "out-unsafe")

    def test_tiers_filters_and_shards_have_scoped_claims(self):
        root = self.make_repo(
            [
                {"model_id": "a", "script": "print('a')\n", "tier": "fast"},
                {"model_id": "b", "script": "print('b')\n", "tier": "focused"},
                {"model_id": "c", "script": "print('c')\n", "tier": "full"},
            ]
        )
        fast = run_manifest_regressions(root, tier="fast", output_dir=root / "outputs" / "out-fast")
        shard = run_manifest_regressions(root, tier="full", shard="2/3", output_dir=root / "outputs" / "out-shard")
        self.assertEqual(("a",), fast.selected_model_ids)
        self.assertIn("does not support a full-model release claim", fast.to_validation_result().claim_boundary)
        self.assertEqual("scoped", fast.parent_claim_scope)
        self.assertEqual("scoped", shard.parent_claim_scope)
        self.assertIn(
            "cannot support release",
            json.loads(Path(shard.parent_receipt_path).read_text(encoding="utf-8"))[
                "claim_boundary"
            ],
        )
        self.assertEqual(("b",), shard.selected_model_ids)

    def test_complete_full_manifest_composes_exact_full_parent(self):
        root = self.make_repo(
            [
                {"model_id": "a", "script": "print('a')\n", "tier": "fast"},
                {"model_id": "b", "script": "print('b')\n", "tier": "full"},
            ]
        )

        report = run_manifest_regressions(
            root,
            tier="full",
            output_dir=root / "outputs" / "out-full-parent",
        )

        self.assertTrue(report.ok, report.to_dict())
        self.assertEqual("full", report.parent_claim_scope)
        parent = json.loads(
            Path(report.parent_receipt_path).read_text(encoding="utf-8")
        )
        self.assertEqual(["a", "b"], parent["selected_model_ids"])
        self.assertEqual(
            ["a", "b"],
            [item["model_id"] for item in parent["children"]],
        )
        self.assertEqual(
            report.parent_receipt_fingerprint,
            parent["parent_receipt_fingerprint"],
        )

    def test_isolated_artifact_is_required_and_preserved(self):
        script = textwrap.dedent(
            """
            import os
            from pathlib import Path
            target = Path(os.environ['FLOWGUARD_OUTPUT_DIR']) / 'result.json'
            target.write_text('{"ok": true}', encoding='utf-8')
            """
        )
        root = self.make_repo(
            [{"model_id": "artifact", "script": script, "expected_artifacts": ["result.json"]}]
        )
        report = run_manifest_regressions(root, tier="full", output_dir=root / "outputs" / "out-artifact")
        self.assertTrue(report.ok, report.to_dict())
        self.assertTrue(Path(report.results[0].artifact_paths[0]).is_file())

    def test_parent_logs_survive_child_replacing_isolated_output_directory(self):
        script = textwrap.dedent(
            """
            import os
            import shutil
            from pathlib import Path
            target = Path(os.environ['FLOWGUARD_OUTPUT_DIR'])
            shutil.rmtree(target)
            target.mkdir(parents=True)
            print('child replaced output directory')
            """
        )
        root = self.make_repo([{"model_id": "replacer", "script": script}])
        report = run_manifest_regressions(root, tier="full", output_dir=root / "outputs" / "out-replacer")
        self.assertTrue(report.ok, report.to_dict())
        self.assertIn(
            "child replaced output directory",
            gzip.decompress(Path(report.results[0].stdout_path).read_bytes()).decode("utf-8"),
        )
        self.assertTrue(Path(report.results[0].receipt_path).is_file())

    def test_child_imports_the_selected_repository_before_an_external_installation(self):
        root = self.make_repo(
            [
                {
                    "model_id": "source-identity",
                    "script": "import selected_repository_module\n"
                    "print(selected_repository_module.IDENTITY)\n",
                }
            ]
        )
        root.joinpath("selected_repository_module.py").write_text(
            "IDENTITY = 'selected repository'\n", encoding="utf-8"
        )
        with patch.dict("os.environ", {"PYTHONPATH": str(root.parent / "unrelated-install")}, clear=False):
            report = run_manifest_regressions(
                root, tier="full", output_dir=root / "outputs" / "out-source-identity"
            )
        self.assertTrue(report.ok, report.to_dict())
        self.assertIn(
            "selected repository",
            gzip.decompress(Path(report.results[0].stdout_path).read_bytes()).decode("utf-8"),
        )

    def test_tracked_mutation_blocks_success(self):
        script = "from pathlib import Path\nPath('tracked.txt').write_text('changed', encoding='utf-8')\n"
        root = self.make_repo([{"model_id": "writer", "script": script}])
        root.joinpath("tracked.txt").write_text("before", encoding="utf-8")
        with patch("flowguard.model_regressions._tracked_paths", return_value=(root / "tracked.txt",)):
            report = run_manifest_regressions(root, tier="full", output_dir=root / "outputs" / "out-mutation")
        self.assertEqual("blocked", report.status)
        self.assertEqual(("tracked.txt",), report.mutation_paths)

    def test_identical_second_run_reuses_receipt_without_invoking_runner(self):
        script = (
            "from pathlib import Path\n"
            "path = Path('invocations.txt')\n"
            "count = int(path.read_text() if path.exists() else '0')\n"
            "path.write_text(str(count + 1), encoding='utf-8')\n"
        )
        root = self.make_repo([{"model_id": "cached", "script": script}])
        with patch("flowguard.model_regressions._tracked_paths", return_value=()):
            first = run_manifest_regressions(
                root,
                tier="full",
                output_dir=root / "outputs" / "out-first",
            )
            second = run_manifest_regressions(
                root,
                tier="full",
                output_dir=root / "outputs" / "out-second",
            )
        self.assertTrue(first.ok, first.to_dict())
        self.assertTrue(second.ok, second.to_dict())
        self.assertEqual("1", (root / "invocations.txt").read_text(encoding="utf-8"))
        self.assertEqual("execute", first.results[0].execution_disposition)
        self.assertEqual("reuse_current", second.results[0].execution_disposition)
        self.assertEqual(0, second.results[0].producer_invocations)
        self.assertEqual(
            first.results[0].receipt_fingerprint,
            second.results[0].receipt_fingerprint,
        )

    def test_one_model_input_change_executes_only_that_model(self):
        script = (
            "from pathlib import Path\n"
            "model_id = __import__('os').environ['FLOWGUARD_MODEL_ID']\n"
            "path = Path(f'{model_id}-invocations.txt')\n"
            "count = int(path.read_text() if path.exists() else '0')\n"
            "path.write_text(str(count + 1), encoding='utf-8')\n"
        )
        root = self.make_repo(
            [
                {"model_id": "alpha", "script": script},
                {"model_id": "beta", "script": script},
            ]
        )
        alpha_config = root / ".flowguard" / "models" / "owners" / "alpha" / "config.json"
        alpha_config.write_text('{"value": 1}\n', encoding="utf-8")
        manifest_path = root / ".flowguard" / "models" / "regression-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["models"][0]["input_globs"].append(
            ".flowguard/models/owners/alpha/config.json"
        )
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with patch("flowguard.model_regressions._tracked_paths", return_value=()):
            first = run_manifest_regressions(
                root,
                tier="full",
                output_dir=root / "outputs" / "out-first",
            )
            alpha_config.write_text('{"value": 2}\n', encoding="utf-8")
            second = run_manifest_regressions(
                root,
                tier="full",
                output_dir=root / "outputs" / "out-second",
            )
        self.assertTrue(first.ok, first.to_dict())
        self.assertTrue(second.ok, second.to_dict())
        by_id = {item.model_id: item for item in second.results}
        self.assertEqual("execute", by_id["alpha"].execution_disposition)
        self.assertEqual("reuse_current", by_id["beta"].execution_disposition)
        self.assertEqual("2", (root / "alpha-invocations.txt").read_text(encoding="utf-8"))
        self.assertEqual("1", (root / "beta-invocations.txt").read_text(encoding="utf-8"))

    def test_budget_only_manifest_entry_change_reuses_that_model(self):
        script = (
            "from pathlib import Path\n"
            "model_id = __import__('os').environ['FLOWGUARD_MODEL_ID']\n"
            "path = Path(f'{model_id}-manifest-invocations.txt')\n"
            "count = int(path.read_text() if path.exists() else '0')\n"
            "path.write_text(str(count + 1), encoding='utf-8')\n"
        )
        root = self.make_repo(
            [
                {"model_id": "alpha", "script": script},
                {"model_id": "beta", "script": script},
            ]
        )
        with patch("flowguard.model_regressions._tracked_paths", return_value=()):
            first = run_manifest_regressions(
                root,
                tier="full",
                output_dir=root / "outputs" / "out-first",
            )
            manifest_path = (
                root / ".flowguard" / "models" / "regression-manifest.json"
            )
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            beta = next(
                item
                for item in manifest["models"]
                if item["model_id"] == "beta"
            )
            beta["timeout_seconds"] = 6
            manifest_path.write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
            second = run_manifest_regressions(
                root,
                tier="full",
                output_dir=root / "outputs" / "out-second",
            )

        self.assertTrue(first.ok, first.to_dict())
        self.assertTrue(second.ok, second.to_dict())
        self.assertEqual(
            first.parent_receipt_fingerprint,
            second.parent_receipt_fingerprint,
        )
        self.assertEqual(0, second.to_validation_result().counts["producer_invocations"])
        first_by_id = {item.model_id: item for item in first.results}
        by_id = {item.model_id: item for item in second.results}
        self.assertEqual("reuse_current", by_id["alpha"].execution_disposition)
        self.assertEqual("reuse_current", by_id["beta"].execution_disposition)
        self.assertEqual(
            first_by_id["alpha"].model_instance_fingerprint,
            by_id["alpha"].model_instance_fingerprint,
        )
        self.assertEqual(
            first_by_id["beta"].model_instance_fingerprint,
            by_id["beta"].model_instance_fingerprint,
        )
        self.assertEqual(
            "1",
            (root / "alpha-manifest-invocations.txt").read_text(
                encoding="utf-8"
            ),
        )
        self.assertEqual(
            "1",
            (root / "beta-manifest-invocations.txt").read_text(
                encoding="utf-8"
            ),
        )

    def test_tightened_budget_reexecutes_only_leaf_over_new_cap(self):
        script = (
            "import time\n"
            "from pathlib import Path\n"
            "model_id = __import__('os').environ['FLOWGUARD_MODEL_ID']\n"
            "path = Path(f'{model_id}-budget-invocations.txt')\n"
            "count = int(path.read_text() if path.exists() else '0')\n"
            "path.write_text(str(count + 1), encoding='utf-8')\n"
            "time.sleep(0.05)\n"
        )
        root = self.make_repo(
            [
                {"model_id": "alpha", "script": script, "timeout_seconds": 2},
                {"model_id": "beta", "script": script, "timeout_seconds": 2},
            ]
        )
        with patch("flowguard.model_regressions._tracked_paths", return_value=()):
            first = run_manifest_regressions(
                root,
                tier="full",
                output_dir=root / "outputs" / "out-first",
            )
            manifest_path = root / ".flowguard" / "models" / "regression-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            alpha = next(item for item in manifest["models"] if item["model_id"] == "alpha")
            alpha["timeout_seconds"] = 0.001
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            second = run_manifest_regressions(
                root,
                tier="full",
                output_dir=root / "outputs" / "out-second",
            )

        self.assertTrue(first.ok, first.to_dict())
        by_id = {item.model_id: item for item in second.results}
        self.assertEqual("execute", by_id["alpha"].execution_disposition)
        self.assertEqual("reuse_current", by_id["beta"].execution_disposition)
        self.assertEqual(
            "1",
            (root / "beta-budget-invocations.txt").read_text(encoding="utf-8"),
        )

    def test_tightened_budget_marks_only_the_over_cap_leaf_resource_incompatible(self):
        alpha_receipt = object()
        beta_receipt = object()
        rows = (
            ValidationOwnerPlanRow(
                owner_id="model:alpha",
                disposition="reuse_current",
                owner_identity="sha256:" + "a" * 64,
                reason="current terminal receipt",
            ),
            ValidationOwnerPlanRow(
                owner_id="model:beta",
                disposition="reuse_current",
                owner_identity="sha256:" + "b" * 64,
                reason="current terminal receipt",
            ),
        )
        receipts = {
            "model:alpha": alpha_receipt,
            "model:beta": beta_receipt,
        }
        entries = {
            "model:alpha": SimpleNamespace(timeout_seconds=0.5),
            "model:beta": SimpleNamespace(timeout_seconds=2.0),
        }

        def child_for(receipt, _receipt_root):
            child_id = "alpha" if receipt is alpha_receipt else "beta"
            return ValidationChildResult(
                child_id=child_id,
                status="pass",
                payload={
                    "model_result": {
                        "status": "pass",
                        "seconds": 1.0,
                    }
                },
            )

        with patch(
            "flowguard.model_regressions.child_from_owner_receipt",
            side_effect=child_for,
        ):
            refreshed = model_regressions._demote_policy_incompatible_model_rows(
                rows,
                receipts,
                entries,
                receipt_root=Path("unused"),
                timeout_override=None,
            )

        by_owner = {row.owner_id: row for row in refreshed}
        self.assertEqual("execute", by_owner["model:alpha"].disposition)
        self.assertEqual(
            ("resource_incompatible",),
            by_owner["model:alpha"].findings,
        )
        self.assertTrue(
            by_owner["model:alpha"].reason.startswith("resource_incompatible:")
        )
        self.assertEqual("reuse_current", by_owner["model:beta"].disposition)
        self.assertEqual((), by_owner["model:beta"].findings)


if __name__ == "__main__":
    unittest.main()

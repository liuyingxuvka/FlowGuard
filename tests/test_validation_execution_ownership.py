from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import flowguard.validation_ownership as validation_ownership_module
from flowguard.evidence_receipts import (
    EvidenceReceipt,
    ReceiptVerificationResult,
    list_evidence_receipts,
    receipt_path,
    verify_evidence_receipt,
)
from flowguard.validation_owner_execution import execute_validation_owner_command
from flowguard.validation_ownership import (
    ValidationOwnerContract,
    ValidationOwnerCurrent,
    ValidationObservationFreshness,
    VALIDATION_CLAIM_SCOPE_LOCAL,
    assert_validation_owner_receipt_integrity,
    assert_validation_owner_observation_fresh,
    build_child_bound_owner_receipt_context,
    build_owner_current,
    build_owner_current_from_observation,
    build_validation_owner_plan,
    build_validation_parent_current,
    dependency_receipt_bindings,
    filter_resolved_input_manifest,
    find_reusable_owner_receipt,
    manifest_fingerprint,
    observe_validation_owners,
    plan_validation_owners,
    nested_owner_launch_allowed,
    selected_owner_ids,
    assert_nested_owner_launch_allowed,
    resolve_input_manifest,
    save_child_bound_owner_receipt,
    save_child_bound_owner_receipt_from_observation,
    topological_owner_contracts,
    validation_input_manifest,
)
from flowguard.observation_metrics import InvocationMetrics
from flowguard.validation_results import ValidationChildResult


def contract(
    owner_id: str,
    *,
    dependencies: tuple[str, ...] = (),
    resources: tuple[str, ...] = (),
    external: tuple[tuple[str, str], ...] = (),
    input_patterns: tuple[str, ...] = ("source.txt",),
) -> ValidationOwnerContract:
    return ValidationOwnerContract(
        owner_id=owner_id,
        command=(sys.executable, "-c", "raise SystemExit(0)"),
        input_patterns=input_patterns,
        obligation_ids=(f"obligation:{owner_id}",),
        dependency_owner_ids=dependencies,
        resource_keys=resources,
        external_component_bindings=external,
    )


def evidence_files(receipt_root: Path) -> tuple[str, ...]:
    if not receipt_root.exists():
        return ()
    return tuple(
        sorted(
            path.relative_to(receipt_root).as_posix()
            for path in receipt_root.rglob("*")
            if path.is_file()
        )
    )


class ValidationExecutionOwnershipTests(unittest.TestCase):
    def test_git_cancelled_cleanup_status_keeps_unknown_blocked_and_known_aborted(self):
        for interruption in ("cancelled", "interrupted"):
            for cleanup_confirmed in (False, True):
                with self.subTest(interruption=interruption, cleanup=cleanup_confirmed):
                    completed = SimpleNamespace(
                        timed_out=False,
                        cancelled=interruption == "cancelled",
                        interrupted=interruption == "interrupted",
                        cleanup_confirmed=cleanup_confirmed, exit_code=0,
                        terminal_reason=interruption if cleanup_confirmed else "cleanup_unconfirmed",
                        episode_token="episode:cancel-fixture", root_process_id=123,
                        root_process_running=False, containment_query_succeeded=cleanup_confirmed,
                        descendant_process_ids=(),
                    )
                    expected_error = (
                        validation_ownership_module.GitQueryAborted if cleanup_confirmed
                        else validation_ownership_module.GitQueryCleanupUnconfirmed
                    )
                    with patch.object(
                        validation_ownership_module, "run_supervised_bytes", return_value=completed,
                    ) as supervise:
                        with self.assertRaises(expected_error) as raised:
                            validation_ownership_module._git_bytes(Path.cwd(), "ls-files")
                    supervise.assert_called_once()
                    self.assertEqual(cleanup_confirmed, raised.exception.cleanup_confirmed)
                    self.assertEqual(completed.terminal_reason, raised.exception.terminal_reason)
                    self.assertIn(
                        f"cleanup_confirmed={str(cleanup_confirmed).lower()}",
                        str(raised.exception),
                    )
                    if not cleanup_confirmed:
                        self.assertEqual("episode:cancel-fixture", raised.exception.episode_token)
                        self.assertFalse(raised.exception.containment_query_succeeded)

    def test_git_timeout_diagnostic_keeps_priority_and_actual_unknown_cleanup(self):
        completed = SimpleNamespace(
            timed_out=True, cancelled=True, interrupted=False,
            cleanup_confirmed=False, exit_code=None, terminal_reason="cleanup_unconfirmed",
        )
        with patch.object(
            validation_ownership_module, "run_supervised_bytes", return_value=completed,
        ) as supervise:
            with self.assertRaises(validation_ownership_module.GitQueryTimeout) as raised:
                validation_ownership_module._git_bytes(Path.cwd(), "ls-files")
        supervise.assert_called_once()
        self.assertFalse(raised.exception.cleanup_confirmed)
        self.assertEqual("cleanup_unconfirmed", raised.exception.terminal_reason)

    def test_git_cleanup_unknown_preserves_actual_terminal_diagnostics(self):
        completed = SimpleNamespace(
            timed_out=False, cancelled=False, interrupted=False,
            cleanup_confirmed=False, exit_code=0,
            terminal_reason="cleanup_unconfirmed", episode_token="episode:fixture",
            root_process_id=123, root_process_running=False,
            containment_query_succeeded=False, descendant_process_ids=(456,),
            stdout=b"secret command output", stderr=b"secret stderr",
        )
        with patch.object(
            validation_ownership_module, "run_supervised_bytes", return_value=completed,
        ) as supervise:
            with self.assertRaises(
                validation_ownership_module.GitQueryCleanupUnconfirmed,
            ) as raised:
                validation_ownership_module._git_bytes(Path.cwd(), "ls-files", "--cached")
        supervise.assert_called_once()
        error = raised.exception
        self.assertFalse(error.cleanup_confirmed)
        self.assertEqual("episode:fixture", error.episode_token)
        self.assertEqual(123, error.root_process_id)
        self.assertEqual(0, error.exit_code)
        self.assertFalse(error.containment_query_succeeded)
        self.assertFalse(error.root_process_running)
        self.assertEqual((456,), error.descendant_process_ids)
        self.assertEqual(1, error.descendant_process_count)
        message = str(error)
        self.assertIn("git_query_cleanup_unconfirmed", message)
        self.assertIn('"episode_token":"episode:fixture"', message)
        self.assertIn('"containment_query_succeeded":false', message)
        self.assertIn('"descendant_process_ids":[456]', message)
        self.assertNotIn("secret", message)
        self.assertNotIn("--cached", message)

    def test_git_cleanup_unknown_diagnostics_are_bounded_and_missing_stays_unknown(self):
        error = validation_ownership_module.GitQueryCleanupUnconfirmed(
            query_category="ls-files", elapsed_seconds=0.1,
            terminal_reason="cleanup_unconfirmed", episode_token="e" * 1000,
            descendant_process_ids=tuple(range(1, 101)),
        )
        self.assertEqual("e" * 128, error.episode_token)
        self.assertEqual(tuple(range(1, 33)), error.descendant_process_ids)
        self.assertEqual(100, error.descendant_process_count)
        self.assertLess(len(str(error)), 1000)
        self.assertIsNone(error.root_process_running)
        self.assertIsNone(error.containment_query_succeeded)
        self.assertIn('"root_process_running":null', str(error))
        self.assertIn('"containment_query_succeeded":null', str(error))
        completed = SimpleNamespace(
            timed_out=False, cancelled=False, interrupted=False,
            cleanup_confirmed=False, exit_code=0,
            terminal_reason="cleanup_unconfirmed", root_process_running=False,
            descendant_process_ids=(),
        )
        with patch.object(
            validation_ownership_module, "run_supervised_bytes", return_value=completed,
        ) as supervise:
            with self.assertRaises(
                validation_ownership_module.GitQueryCleanupUnconfirmed,
            ) as raised:
                validation_ownership_module._git_bytes(Path.cwd(), "ls-files")
        supervise.assert_called_once()
        self.assertIsNone(raised.exception.containment_query_succeeded)
        self.assertEqual((), raised.exception.descendant_process_ids)
        self.assertFalse(raised.exception.cleanup_confirmed)

    def test_serial_local_check_is_bounded_and_final_check_still_detects_other_owner_drift(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            (root / "other.txt").write_text("other", encoding="utf-8")
            owners = (contract("child"), contract("other", input_patterns=("other.txt",)))
            observation = observe_validation_owners(root, owners, receipt_root=root / "receipts")
            (root / "other.txt").write_text("changed", encoding="utf-8")
            with patch.object(validation_ownership_module, "resolve_input_manifest", wraps=resolve_input_manifest) as resolve, patch.object(validation_ownership_module, "list_evidence_receipts") as receipts:
                local = validation_ownership_module._assert_validation_owner_current_fresh(observation, "child", root)
            self.assertTrue(local.ok)
            self.assertEqual(("child",), tuple(local.current_by_owner))
            self.assertEqual(("source.txt",), resolve.call_args.args[1])
            receipts.assert_not_called()
            with self.assertRaisesRegex(ValueError, "repository_input_manifest_changed"):
                assert_validation_owner_observation_fresh(observation, root, root / "receipts")
            with patch("flowguard.validation_ownership.platform.machine", return_value="drift"):
                with self.assertRaisesRegex(ValueError, "inputs changed"):
                    validation_ownership_module._assert_validation_owner_current_fresh(observation, "child", root)
            with self.assertRaisesRegex(ValueError, "outside the frozen"):
                validation_ownership_module._assert_validation_owner_current_fresh(observation, "foreign", root)

    def test_owned_receipt_ledger_preserves_exact_all_and_latest_inventory_semantics(self):
        for latest in (False, True):
            with self.subTest(latest=latest), tempfile.TemporaryDirectory() as temporary:
                root = self._repository(Path(temporary))
                receipt_root = root / "receipts"
                owner, first, _ = self._supervised_child(root, receipt_root)
                observation = observe_validation_owners(root, (owner,), receipt_root=receipt_root, prefer_latest_model_receipt=latest)

                def publish_nonpass(label):
                    now = datetime.now(timezone.utc).isoformat()
                    return validation_ownership_module.record_validation_owner_nonpass(
                        observation.current_by_owner[owner.owner_id],
                        ValidationChildResult(child_id=owner.owner_id, status="fail", summary=label),
                        root, receipt_root, all_contracts=(owner,),
                        started_at=now, finished_at=now,
                    )

                # An initial successful attempt followed by a failed retry is
                # a legitimate multi-receipt inventory, not two competing passes.
                produced = publish_nonpass("owned attempt")
                expected = validation_ownership_module._receipt_inventory_after_owned_publications(observation, (produced,))
                self.assertEqual(1 if latest else 2, len(expected))
                self.assertIn(produced.receipt_id, {row[1] for row in expected})
                self.assertEqual(not latest, first.receipt_id in {row[1] for row in expected})
                self.assertTrue(assert_validation_owner_observation_fresh(observation, root, receipt_root, published_receipts=(produced,)).ok)
                if not latest:
                    altered = replace(observation, receipt_inventory_identities=((produced.subject_id, produced.receipt_id, "sha256:altered"),))
                    with self.assertRaisesRegex(ValueError, "immutable receipt"):
                        validation_ownership_module._receipt_inventory_after_owned_publications(altered, (produced,))
                with self.assertRaisesRegex(ValueError, "cannot narrow"):
                    assert_validation_owner_observation_fresh(observation, root, receipt_root, receipt_ids=(produced.receipt_id,), published_receipts=(produced,))
                with self.assertRaisesRegex(ValueError, "one receipt per owner"):
                    validation_ownership_module._receipt_inventory_after_owned_publications(observation, (produced, produced))
                # A later same-subject publication is not owned by this call.
                publish_nonpass("foreign attempt")
                with self.assertRaisesRegex(ValueError, "receipt_inventory_changed"):
                    assert_validation_owner_observation_fresh(observation, root, receipt_root, published_receipts=(produced,))

    def test_owned_receipt_ledger_rejects_foreign_owner_context(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            receipt_root = root / "receipts"
            _owner, receipt, _ = self._supervised_child(root, receipt_root)
            foreign_observation = observe_validation_owners(root, (contract("foreign"),), receipt_root=receipt_root)
            with self.assertRaisesRegex(ValueError, "outside the frozen"):
                validation_ownership_module._receipt_inventory_after_owned_publications(foreign_observation, (receipt,))

    def test_author_request_outputs_are_excluded_but_contracts_remain_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            prefix = ".agents/skills/flowguard/.skillguard/"
            request_prefix = prefix + "runtime-requests/full-author-assurance/"
            sources = (
                prefix + "skill_contract.json",
                prefix + "compiled/check-manifest.json",
                prefix + "runtime-requests/full-author-assurance-extra/source.json",
                ".agents/skills/other/.skillguard/runtime-requests/full-author-assurance/source.json",
            )
            for name in (*sources, request_prefix + "tracked.json", request_prefix + "untracked.json"):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{}", encoding="utf-8")
            subprocess.run(("git", "add", request_prefix + "tracked.json"), cwd=root, check=True)
            before = resolve_input_manifest(root, (".agents/skills/**/*",))
            self.assertEqual(set(sources), {row["path"] for row in before})
            (root / (request_prefix + "tracked.json")).write_text('{"request":2}', encoding="utf-8")
            self.assertEqual(before, resolve_input_manifest(root, (".agents/skills/**/*",)))
            with patch.object(validation_ownership_module, "_git_candidate_paths", return_value=None):
                self.assertEqual(before, resolve_input_manifest(root, (".agents/skills/**/*",)))
            from flowguard.model_regressions import _tracked_paths
            self.assertNotIn(root / (request_prefix + "tracked.json"), _tracked_paths(root))
            (root / sources[0]).write_text('{"contract":2}', encoding="utf-8")
            self.assertNotEqual(before, resolve_input_manifest(root, (".agents/skills/**/*",)))

    def test_owner_required_wire_boolean_cannot_change_protection_denominator(self):
        values = contract("owner").to_dict()
        for invalid in (None, 0, 1, "false"):
            with self.subTest(required=invalid):
                values["required"] = invalid
                with self.assertRaisesRegex(ValueError, "required must be boolean"):
                    ValidationOwnerContract.from_dict(values)

    def test_nested_owner_selection_blocks_duplicate_launch_without_fuzzy_matching(self):
        selected = ("model:child", "named:nested")
        self.assertEqual(
            frozenset(selected), selected_owner_ids(selected)
        )
        self.assertFalse(
            nested_owner_launch_allowed(
                "model:parent", "child", selected=selected
            )
        )
        self.assertTrue(
            nested_owner_launch_allowed(
                "model:parent", "child-extra", selected=selected
            )
        )
        with self.assertRaisesRegex(ValueError, "consume its current receipt"):
            assert_nested_owner_launch_allowed(
                "model:parent", "child", selected=selected
            )

    def test_literal_manifest_projection_skips_general_pattern_matching(self) -> None:
        manifest = (
            {"path": "source.txt", "sha256": "sha256:source"},
            {"path": "flowguard/direct.py", "sha256": "sha256:direct"},
            {"path": "flowguard/nested/deep.py", "sha256": "sha256:deep"},
        )
        with patch(
            "flowguard.validation_ownership._matches_declared_pattern",
            wraps=validation_ownership_module._matches_declared_pattern,
        ) as matcher:
            rows = filter_resolved_input_manifest(
                manifest,
                ("source.txt", "flowguard/**/*.py"),
            )

        self.assertEqual(
            ("flowguard/direct.py", "flowguard/nested/deep.py", "source.txt"),
            tuple(row["path"] for row in rows),
        )
        self.assertTrue(matcher.call_args_list)
        self.assertNotIn(
            "source.txt",
            tuple(call.args[1] for call in matcher.call_args_list),
        )

    def test_explicit_observation_scans_source_and_receipts_once(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            receipt_root = root / "receipts"
            with (
                patch(
                    "flowguard.validation_ownership.resolve_input_manifest",
                    wraps=resolve_input_manifest,
                ) as resolve_manifest,
                patch(
                    "flowguard.validation_ownership.list_evidence_receipts",
                    wraps=list_evidence_receipts,
                ) as list_receipts,
            ):
                observation = observe_validation_owners(
                    root,
                    (contract("a"), contract("b")),
                    receipt_root=receipt_root,
                )

            self.assertEqual(1, resolve_manifest.call_count)
            self.assertEqual(1, list_receipts.call_count)
            self.assertEqual(2, len(observation.owner_currents))
            self.assertTrue(observation.observation_fingerprint.startswith("sha256:"))

    def test_observation_metrics_report_real_single_pass_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            metrics = InvocationMetrics()
            observation = observe_validation_owners(
                root,
                (contract("a"), contract("b")),
                receipt_root=root / "receipts",
                metrics=metrics,
            )

            counters = metrics.snapshot()["counters"]
            self.assertEqual(1, counters["source_manifest_builds"])
            self.assertEqual(1, counters["receipt_directory_scans"])
            self.assertEqual(2, counters["owner_current_builds"])
            self.assertEqual(metrics.snapshot(), dict(observation.metrics))

    def test_observation_freshness_is_visible_and_detects_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            receipt_root = root / "receipts"
            child_contract, child_receipt, _verification = self._supervised_child(
                root,
                receipt_root,
            )
            observation = observe_validation_owners(
                root,
                (child_contract,),
                receipt_root=receipt_root,
            )
            not_run = ValidationObservationFreshness.not_run(observation)
            self.assertEqual("not_run", not_run.status)
            self.assertFalse(not_run.ok)
            self.assertTrue(
                assert_validation_owner_observation_fresh(
                    observation,
                    root,
                    receipt_root,
                ).ok
            )

            receipt_path(
                child_receipt.receipt_id,
                root,
                output_directory=receipt_root,
            ).unlink()
            with self.assertRaisesRegex(ValueError, "receipt_inventory_changed"):
                assert_validation_owner_observation_fresh(
                    observation,
                    root,
                    receipt_root,
                )

    def test_new_dependency_receipt_invalidates_old_consumer_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            receipt_root = root / "receipts"
            dependency_contract = contract("dependency")
            consumer_contract = contract(
                "consumer",
                dependencies=("dependency",),
            )
            contracts = (dependency_contract, consumer_contract)

            first_dependency = execute_validation_owner_command(
                build_owner_current(
                    root,
                    dependency_contract,
                    all_contracts=contracts,
                ),
                root,
                receipt_root,
                all_contracts=contracts,
                child_id="dependency",
                evidence_context={"fixture": "dependency-1"},
                summary="dependency pass",
                claim_boundary="Only the dependency fixture.",
            )
            self.assertTrue(first_dependency.ok)
            assert first_dependency.receipt is not None

            first_binding = [
                {
                    "owner_id": owner_id,
                    "receipt_id": receipt_id,
                    "receipt_fingerprint": fingerprint,
                }
                for owner_id, receipt_id, fingerprint in dependency_receipt_bindings(
                    {"dependency": first_dependency.receipt}
                )
            ]
            first_consumer = execute_validation_owner_command(
                build_owner_current(
                    root,
                    consumer_contract,
                    all_contracts=contracts,
                ),
                root,
                receipt_root,
                all_contracts=contracts,
                child_id="consumer",
                evidence_context={
                    "fixture": "consumer-1",
                    "dependency_receipt_bindings": first_binding,
                },
                summary="consumer pass",
                claim_boundary="Only the consumer fixture.",
            )
            self.assertTrue(first_consumer.ok)
            assert first_consumer.receipt is not None

            # A later dependency producer result can keep the source inputs
            # unchanged while changing the consumed evidence identity.  It is
            # represented here as a valid content-addressed receipt object;
            # the consumer must still reject its older binding.
            second_dependency = replace(
                first_dependency.receipt,
                metadata={"fixture": "dependency-2"},
            )
            self.assertNotEqual(
                first_dependency.receipt.fingerprint,
                second_dependency.fingerprint,
            )

            selected, verification = find_reusable_owner_receipt(
                build_owner_current(
                    root,
                    consumer_contract,
                    all_contracts=contracts,
                ),
                root,
                receipt_root,
                dependency_receipts={"dependency": second_dependency},
            )
            self.assertIsNone(selected)
            self.assertIsNone(verification)

    def test_observation_freshness_detects_source_and_environment_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            observation = observe_validation_owners(
                root,
                (contract("child"),),
                receipt_root=root / "receipts",
            )
            (root / "source.txt").write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "repository_input_manifest_changed"):
                assert_validation_owner_observation_fresh(
                    observation,
                    root,
                    root / "receipts",
                )

        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            observation = observe_validation_owners(
                root,
                (contract("child"),),
                receipt_root=root / "receipts",
            )
            with patch("flowguard.validation_ownership.platform.machine", return_value="drift"):
                with self.assertRaisesRegex(ValueError, "owner_context_changed"):
                    assert_validation_owner_observation_fresh(
                        observation,
                        root,
                        root / "receipts",
                    )

    def test_two_aggregates_share_one_observation_without_merging_owners(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            receipt_root = root / "receipts"
            child_contract, child_receipt, _verification = self._supervised_child(
                root,
                receipt_root,
            )
            observation = observe_validation_owners(
                root,
                (child_contract,),
                receipt_root=receipt_root,
            )
            freshness = assert_validation_owner_observation_fresh(
                observation,
                root,
                receipt_root,
            )
            aggregates: list[EvidenceReceipt] = []
            for owner_id in ("aggregate-a", "aggregate-b"):
                aggregate_contract = ValidationOwnerContract(
                    owner_id=owner_id,
                    command=("python", "-m", "flowguard", owner_id),
                    input_patterns=(),
                    obligation_ids=(f"obligation:{owner_id}",),
                    projected_inputs=(("child:receipt", child_receipt.fingerprint),),
                )
                current = build_owner_current_from_observation(
                    root,
                    aggregate_contract,
                    all_contracts=(aggregate_contract,),
                    observation=observation,
                )
                aggregate, verification = (
                    save_child_bound_owner_receipt_from_observation(
                        current,
                        ("child",),
                        root,
                        receipt_root,
                        observation=observation,
                        freshness=freshness,
                        started_at=child_receipt.started_at,
                        finished_at=child_receipt.finished_at,
                        evidence_context={"fixture": owner_id},
                        claim_boundary=f"Only {owner_id}.",
                    )
                )
                self.assertTrue(verification.ok)
                aggregates.append(aggregate)

            self.assertNotEqual(aggregates[0].receipt_id, aggregates[1].receipt_id)
            self.assertEqual(
                {"validation-owner:aggregate-a", "validation-owner:aggregate-b"},
                {item.subject_id for item in aggregates},
            )
            self.assertEqual(
                {(child_receipt.receipt_id,)},
                {item.consumed_child_receipt_ids for item in aggregates},
            )

    def test_owner_plan_reads_receipt_store_once_per_frozen_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            receipt_root = root / "receipts"
            with patch(
                "flowguard.validation_ownership.list_evidence_receipts",
                return_value=(),
            ) as list_receipts:
                rows, currents, reusable = plan_validation_owners(
                    root,
                    (contract("a"), contract("b")),
                    receipt_root=receipt_root,
                )

            self.assertEqual(1, list_receipts.call_count)
            self.assertEqual(("a", "b"), tuple(item.owner_id for item in rows))
            self.assertEqual({"a", "b"}, set(currents))
            self.assertEqual({}, dict(reusable))

    def test_owner_and_parent_current_do_not_reimport_platform(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            owner_contract = contract("a")
            plan = build_validation_owner_plan(
                root,
                (owner_contract,),
                receipt_root=root / "receipts",
            )

            with (
                patch.dict(sys.modules, {"platform": None}),
                patch(
                    "flowguard.validation_ownership._package_version",
                    return_value="source",
                ),
            ):
                owner = build_owner_current(
                    root,
                    owner_contract,
                    all_contracts=(owner_contract,),
                )
                parent = build_validation_parent_current(root, plan)

            expected_keys = {
                "flowguard_version",
                "platform_machine",
                "platform_system",
                "python_implementation",
                "python_version",
            }
            self.assertEqual(expected_keys, set(owner.environment_metadata))
            self.assertEqual(expected_keys, set(parent.environment_metadata))

    def test_owner_plan_resolves_declared_repository_inputs_once_then_filters_owners(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            (root / "other.txt").write_text("other\n", encoding="utf-8")
            receipt_root = root / "receipts"
            with patch(
                "flowguard.validation_ownership.resolve_input_manifest",
                wraps=resolve_input_manifest,
            ) as resolve_manifest:
                _rows, currents, _reusable = plan_validation_owners(
                    root,
                    (
                        contract("a", input_patterns=("source.txt",)),
                        contract("b", input_patterns=("other.txt",)),
                    ),
                    receipt_root=receipt_root,
                )

            self.assertEqual(1, resolve_manifest.call_count)
            self.assertEqual(
                ("source.txt", "other.txt"),
                resolve_manifest.call_args.args[1],
            )
            self.assertEqual(
                ("source.txt",),
                tuple(row["path"] for row in currents["a"].input_manifest),
            )
            self.assertEqual(
                ("other.txt",),
                tuple(row["path"] for row in currents["b"].input_manifest),
            )

    def test_unknown_dependency_and_cycle_block(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown dependencies"):
            topological_owner_contracts((contract("a", dependencies=("missing",)),))
        with self.assertRaisesRegex(ValueError, "dependency cycle"):
            topological_owner_contracts(
                (
                    contract("a", dependencies=("b",)),
                    contract("b", dependencies=("a",)),
                )
            )

    def test_shared_resource_must_be_dependency_ordered(self) -> None:
        with self.assertRaisesRegex(ValueError, "resource conflict"):
            topological_owner_contracts(
                (
                    contract("a", resources=("workspace",)),
                    contract("b", resources=("workspace",)),
                )
            )
        ordered = topological_owner_contracts(
            (
                contract("b", dependencies=("a",), resources=("workspace",)),
                contract("a", resources=("workspace",)),
            )
        )
        self.assertEqual(("a", "b"), tuple(item.owner_id for item in ordered))

    def test_external_component_mapping_is_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            digest = "sha256:" + "1" * 64
            with self.assertRaisesRegex(ValueError, "mapping is not exact"):
                build_validation_owner_plan(
                    root,
                    (contract("a"),),
                    receipt_root=root / "receipts",
                    required_external_components={"shadow:skills": digest},
                )
            plan = build_validation_owner_plan(
                root,
                (contract("a", external=(("shadow:skills", digest),)),),
                receipt_root=root / "receipts",
                required_external_components={"shadow:skills": digest},
            )
            self.assertFalse(plan.blocked)

    def test_source_drift_after_plan_freeze_blocks_parent_current(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            plan = build_validation_owner_plan(
                root,
                (contract("a"),),
                receipt_root=root / "receipts",
            )
            (root / "source.txt").write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "changed after owner-plan freeze"):
                build_validation_parent_current(root, plan)

    def test_local_parent_does_not_bind_or_rebuild_release_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            plan = build_validation_owner_plan(
                root,
                (contract("a"),),
                receipt_root=root / "receipts",
                claim_scope=VALIDATION_CLAIM_SCOPE_LOCAL,
            )
            self.assertEqual((), plan.release_tree_manifest)
            first = build_validation_parent_current(root, plan)

            # A packaging/report file is outside this local functional owner.
            # It must not reopen the functional parent or launch a producer.
            (root / "release-only-report.txt").write_text(
                "report\n",
                encoding="utf-8",
            )
            second = build_validation_parent_current(root, plan)
            self.assertEqual(first.parent_identity, second.parent_identity)
            self.assertEqual(
                manifest_fingerprint(()),
                second.release_tree_snapshot.raw_sha256,
            )

    def test_evidence_outputs_do_not_refresh_source_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            before = manifest_fingerprint(validation_input_manifest(root))
            output = root / ".flowguard" / "evidence" / "run" / "result.json"
            output.parent.mkdir(parents=True)
            output.write_text('{"status":"pass"}\n', encoding="utf-8")
            after = manifest_fingerprint(validation_input_manifest(root))
            self.assertEqual(before, after)

    def test_run_artifacts_are_excluded_for_tracked_and_untracked_git_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            tracked = root / ".flowguard" / "run_artifacts" / "tracked.json"
            untracked = root / ".flowguard" / "run_artifacts" / "untracked.json"
            tracked.parent.mkdir(parents=True)
            tracked.write_text('{"tracked": true}\n', encoding="utf-8")
            subprocess.run(("git", "add", str(tracked.relative_to(root))), cwd=root, check=True)
            subprocess.run(
                ("git", "commit", "-q", "-m", "tracked run artifact"),
                cwd=root,
                check=True,
            )
            untracked.write_text('{"untracked": true}\n', encoding="utf-8")

            rows = resolve_input_manifest(root, (".flowguard/**/*.json",))

            self.assertNotIn(".flowguard/run_artifacts/tracked.json", {row["path"] for row in rows})
            self.assertNotIn(".flowguard/run_artifacts/untracked.json", {row["path"] for row in rows})

    def test_run_artifacts_are_excluded_when_git_candidate_lookup_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            artifact = root / ".flowguard" / "run_artifacts" / "fallback.json"
            artifact.parent.mkdir(parents=True)
            artifact.write_text('{"fallback": true}\n', encoding="utf-8")

            with patch(
                "flowguard.validation_ownership._git_candidate_paths",
                return_value=None,
            ):
                rows = resolve_input_manifest(root, (".flowguard/**/*.json",))

            self.assertNotIn(
                ".flowguard/run_artifacts/fallback.json",
                {row["path"] for row in rows},
            )

    def test_history_and_reverse_surface_payloads_do_not_enter_source_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            current = root / "flowguard" / "current.py"
            history = root / ".flowguard" / "history" / "retired" / "old.py"
            reverse = (
                root
                / ".flowguard"
                / "structure"
                / "reverse-surfaces"
                / "current-discovery.json"
            )
            current.parent.mkdir(parents=True)
            history.parent.mkdir(parents=True)
            reverse.parent.mkdir(parents=True)
            current.write_text("CURRENT = True\n", encoding="utf-8")
            history.write_text("OLD = True\n", encoding="utf-8")
            reverse.write_text('{"status":"passed"}\n', encoding="utf-8")

            rows = resolve_input_manifest(
                root,
                ("flowguard/**/*.py", ".flowguard/**/*.py"),
            )
            paths = {row["path"] for row in rows}

            self.assertIn("flowguard/current.py", paths)
            self.assertNotIn(".flowguard/history/retired/old.py", paths)
            self.assertNotIn(
                ".flowguard/structure/reverse-surfaces/current-discovery.json",
                paths,
            )

    def test_git_candidates_preserve_recursive_globs_without_walking_ignored_evidence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            direct = root / "flowguard" / "direct.py"
            nested = root / "flowguard" / "nested" / "deep.py"
            ignored = root / ".flowguard" / "evidence" / "run" / "noise.py"
            lookalike = root / ".agents" / "skills" / "flowguard" / "noise.py"
            direct.parent.mkdir(parents=True)
            nested.parent.mkdir(parents=True)
            ignored.parent.mkdir(parents=True)
            lookalike.parent.mkdir(parents=True)
            direct.write_text("DIRECT = True\n", encoding="utf-8")
            nested.write_text("DEEP = True\n", encoding="utf-8")
            ignored.write_text("NOISE = True\n", encoding="utf-8")
            lookalike.write_text("LOOKALIKE = True\n", encoding="utf-8")
            (root / ".gitignore").write_text(
                ".flowguard/evidence/\n",
                encoding="utf-8",
            )

            rows = resolve_input_manifest(
                root,
                ("flowguard/**/*.py", ".flowguard/**/*.py"),
            )
            paths = {row["path"] for row in rows}

            self.assertIn("flowguard/direct.py", paths)
            self.assertIn("flowguard/nested/deep.py", paths)
            self.assertNotIn(
                ".flowguard/evidence/run/noise.py",
                paths,
            )
            self.assertNotIn(".agents/skills/flowguard/noise.py", paths)

    def test_git_candidates_union_tracked_and_untracked_literal_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            tracked = root / "tracked.json"
            untracked = root / "untracked.json"
            tracked.write_text('{"tracked": true}\n', encoding="utf-8")
            untracked.write_text('{"untracked": true}\n', encoding="utf-8")
            subprocess.run(("git", "add", "tracked.json"), cwd=root, check=True)
            subprocess.run(
                ("git", "commit", "-q", "-m", "tracked input"),
                cwd=root,
                check=True,
            )

            rows = resolve_input_manifest(
                root,
                ("tracked.json", "untracked.json"),
            )

            self.assertEqual(
                {"tracked.json", "untracked.json"},
                {row["path"] for row in rows},
            )

    def test_child_bound_owner_receipt_consumes_real_verified_child(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            receipt_root = root / "receipts"
            child_contract, child_receipt, child_verification = (
                self._supervised_child(root, receipt_root)
            )

            aggregate_contract = ValidationOwnerContract(
                owner_id="aggregate",
                command=("python", "-m", "flowguard", "aggregate"),
                input_patterns=(),
                obligation_ids=("obligation:aggregate",),
                projected_inputs=(("child:receipt", child_receipt.fingerprint),),
            )
            aggregate_current = build_owner_current(
                root,
                aggregate_contract,
                all_contracts=(aggregate_contract,),
            )
            with patch(
                "flowguard.validation_ownership.list_evidence_receipts",
                wraps=list_evidence_receipts,
            ) as list_receipts:
                aggregate, verification = save_child_bound_owner_receipt(
                    aggregate_current,
                    (child_receipt,),
                    root,
                    receipt_root,
                    all_contracts=(aggregate_contract,),
                    child_contracts=(child_contract,),
                    started_at=child_receipt.started_at,
                    finished_at=child_receipt.finished_at,
                    evidence_context={"fixture": "exact-child-composition"},
                    claim_boundary="Only the aggregate fixture.",
                )

            self.assertTrue(verification.ok)
            self.assertEqual(2, list_receipts.call_count)
            assert_validation_owner_receipt_integrity(aggregate)
            with self.assertRaisesRegex(ValueError, "content address mismatch"):
                assert_validation_owner_receipt_integrity(
                    replace(
                        aggregate,
                        started_at="2000-01-01T00:00:00+00:00",
                    )
                )
            self.assertEqual(
                (child_receipt.receipt_id,),
                tuple(item.receipt_id for item in aggregate.required_child_receipts),
            )
            self.assertEqual(
                (child_receipt.receipt_id,),
                aggregate.consumed_child_receipt_ids,
            )
            context = build_child_bound_owner_receipt_context(
                aggregate_current,
                aggregate,
                root,
                receipt_root,
                child_receipts=(child_receipt,),
                child_verification_results=(child_verification,),
            )
            self.assertTrue(verify_evidence_receipt(aggregate, context).ok)

    def test_child_bound_owner_rejects_forged_green_for_stale_child(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            receipt_root = root / "receipts"
            child_contract, child_receipt, child_verification = (
                self._supervised_child(root, receipt_root)
            )
            aggregate_contract, aggregate_current = self._aggregate_owner(
                root,
                child_receipt,
            )
            (root / "source.txt").write_text("changed\n", encoding="utf-8")
            forged = replace(
                child_verification,
                current=True,
                eligible=True,
                status="pass",
                findings=(),
                satisfied_obligations=child_receipt.covered_obligations,
                minimum_revalidation=(),
            )
            self.assertTrue(forged.ok)
            before = evidence_files(receipt_root)

            with self.assertRaisesRegex(ValueError, "not exact-current"):
                save_child_bound_owner_receipt(
                    aggregate_current,
                    (child_receipt,),
                    root,
                    receipt_root,
                    all_contracts=(aggregate_contract,),
                    child_contracts=(child_contract,),
                    started_at=child_receipt.started_at,
                    finished_at=child_receipt.finished_at,
                    evidence_context={"fixture": "forged-green"},
                    claim_boundary="Only the aggregate fixture.",
                )
            self.assertEqual(before, evidence_files(receipt_root))

    def test_child_bound_owner_rejects_foreign_contract_subject(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            receipt_root = root / "receipts"
            _child_contract, child_receipt, _verification = self._supervised_child(
                root,
                receipt_root,
            )
            aggregate_contract, aggregate_current = self._aggregate_owner(
                root,
                child_receipt,
            )
            before = evidence_files(receipt_root)

            with self.assertRaisesRegex(ValueError, "subjects do not exactly match"):
                save_child_bound_owner_receipt(
                    aggregate_current,
                    (child_receipt,),
                    root,
                    receipt_root,
                    all_contracts=(aggregate_contract,),
                    child_contracts=(contract("foreign"),),
                    started_at=child_receipt.started_at,
                    finished_at=child_receipt.finished_at,
                    evidence_context={"fixture": "foreign-contract"},
                    claim_boundary="Only the aggregate fixture.",
                )
            self.assertEqual(before, evidence_files(receipt_root))

    def test_child_bound_owner_rejects_missing_canonical_child(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            receipt_root = root / "receipts"
            child_contract, child_receipt, _verification = self._supervised_child(
                root,
                receipt_root,
            )
            aggregate_contract, aggregate_current = self._aggregate_owner(
                root,
                child_receipt,
            )
            receipt_path(
                child_receipt.receipt_id,
                root,
                output_directory=receipt_root,
            ).unlink()
            before = evidence_files(receipt_root)

            with self.assertRaisesRegex(ValueError, "not exact-current"):
                save_child_bound_owner_receipt(
                    aggregate_current,
                    (child_receipt,),
                    root,
                    receipt_root,
                    all_contracts=(aggregate_contract,),
                    child_contracts=(child_contract,),
                    started_at=child_receipt.started_at,
                    finished_at=child_receipt.finished_at,
                    evidence_context={"fixture": "missing-canonical-child"},
                    claim_boundary="Only the aggregate fixture.",
                )
            self.assertEqual(before, evidence_files(receipt_root))

    def test_child_bound_owner_rejects_aggregate_input_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            receipt_root = root / "receipts"
            child_contract, child_receipt, _verification = self._supervised_child(
                root,
                receipt_root,
            )
            aggregate_input = root / "aggregate.txt"
            aggregate_input.write_text("current\n", encoding="utf-8")
            aggregate_contract, aggregate_current = self._aggregate_owner(
                root,
                child_receipt,
                input_patterns=("aggregate.txt",),
            )
            aggregate_input.write_text("changed\n", encoding="utf-8")
            before = evidence_files(receipt_root)

            with self.assertRaisesRegex(ValueError, "inputs changed before publication"):
                save_child_bound_owner_receipt(
                    aggregate_current,
                    (child_receipt,),
                    root,
                    receipt_root,
                    all_contracts=(aggregate_contract,),
                    child_contracts=(child_contract,),
                    started_at=child_receipt.started_at,
                    finished_at=child_receipt.finished_at,
                    evidence_context={"fixture": "aggregate-drift"},
                    claim_boundary="Only the aggregate fixture.",
                )
            self.assertEqual(before, evidence_files(receipt_root))

    def _supervised_child(
        self,
        root: Path,
        receipt_root: Path,
    ) -> tuple[
        ValidationOwnerContract,
        EvidenceReceipt,
        ReceiptVerificationResult,
    ]:
        child_contract = contract("child")
        child_current = build_owner_current(
            root,
            child_contract,
            all_contracts=(child_contract,),
        )
        child_execution = execute_validation_owner_command(
            child_current,
            root,
            receipt_root,
            all_contracts=(child_contract,),
            child_id="child",
            evidence_context={"fixture": "real-supervised-child"},
            summary="child pass",
            claim_boundary="Only the child fixture.",
        )
        self.assertTrue(child_execution.ok)
        self.assertIsNotNone(child_execution.receipt)
        self.assertIsNotNone(child_execution.verification)
        assert child_execution.receipt is not None
        assert child_execution.verification is not None
        self.assertTrue(child_execution.verification.ok)
        return (
            child_contract,
            child_execution.receipt,
            child_execution.verification,
        )

    @staticmethod
    def _aggregate_owner(
        root: Path,
        child_receipt: EvidenceReceipt,
        *,
        input_patterns: tuple[str, ...] = (),
    ) -> tuple[ValidationOwnerContract, ValidationOwnerCurrent]:
        aggregate_contract = ValidationOwnerContract(
            owner_id="aggregate",
            command=("python", "-m", "flowguard", "aggregate"),
            input_patterns=input_patterns,
            obligation_ids=("obligation:aggregate",),
            projected_inputs=(("child:receipt", child_receipt.fingerprint),),
        )
        aggregate_current = build_owner_current(
            root,
            aggregate_contract,
            all_contracts=(aggregate_contract,),
        )
        return aggregate_contract, aggregate_current

    @staticmethod
    def _repository(root: Path) -> Path:
        root.mkdir(parents=True, exist_ok=True)
        (root / "source.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(("git", "init", "-q"), cwd=root, check=True)
        subprocess.run(
            ("git", "config", "user.email", "fixture@example.invalid"),
            cwd=root,
            check=True,
        )
        subprocess.run(
            ("git", "config", "user.name", "FlowGuard Fixture"),
            cwd=root,
            check=True,
        )
        subprocess.run(("git", "add", "."), cwd=root, check=True)
        subprocess.run(
            ("git", "commit", "-q", "-m", "fixture"),
            cwd=root,
            check=True,
        )
        return root


if __name__ == "__main__":
    unittest.main()

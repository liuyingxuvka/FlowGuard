from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
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
    assert_validation_owner_receipt_integrity,
    assert_validation_owner_observation_fresh,
    build_child_bound_owner_receipt_context,
    build_owner_current,
    build_owner_current_from_observation,
    build_validation_owner_plan,
    build_validation_parent_current,
    filter_resolved_input_manifest,
    manifest_fingerprint,
    observe_validation_owners,
    plan_validation_owners,
    resolve_input_manifest,
    save_child_bound_owner_receipt,
    save_child_bound_owner_receipt_from_observation,
    topological_owner_contracts,
    validation_input_manifest,
)


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

    def test_owner_plan_resolves_repository_inputs_once_then_filters_owners(
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
                ("**/*", "*"),
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

    def test_evidence_outputs_do_not_refresh_source_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._repository(Path(temporary))
            before = manifest_fingerprint(validation_input_manifest(root))
            output = root / ".flowguard" / "evidence" / "run" / "result.json"
            output.parent.mkdir(parents=True)
            output.write_text('{"status":"pass"}\n', encoding="utf-8")
            after = manifest_fingerprint(validation_input_manifest(root))
            self.assertEqual(before, after)

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

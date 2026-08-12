from __future__ import annotations

import gzip
import json
import os
import shutil
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from flowguard.evidence_lifecycle import (
    EvidenceLifecycleError,
    apply_evidence_gc,
    audit_evidence,
    evidence_execution_lease,
    ensure_new_run_directory,
    plan_evidence_gc,
    publish_run,
    purge_evidence_quarantine,
    read_current_head,
    read_evidence_execution_lease,
    restore_evidence_quarantine,
    settle_cleanup_unconfirmed_lease,
    settle_interrupted_execution_leases,
    store_text_object,
    verify_text_object,
    write_json_atomic,
)


class EvidenceObjectTests(unittest.TestCase):
    def test_complete_stream_is_deterministic_and_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary) / "run"
            first = store_text_object(run, "same output\n")
            second = store_text_object(run, "same output\n")

            self.assertEqual(first, second)
            self.assertEqual(first["logical_sha256"], second["logical_sha256"])
            objects = list((run / "objects" / "sha256").glob("*.gz"))
            self.assertEqual(1, len(objects))
            self.assertEqual(b"same output\n", gzip.decompress(objects[0].read_bytes()))
            self.assertTrue(verify_text_object(run, first))

    def test_descriptor_keeps_only_a_bounded_tail(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            descriptor = store_text_object(temporary, "x" * 10000, tail_chars=100)

            self.assertEqual(100, len(descriptor["diagnostic_tail"]))
            self.assertTrue(descriptor["diagnostic_truncated"])
            self.assertEqual(10000, descriptor["logical_bytes"])

    def test_concurrent_identical_objects_converge_on_one_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary) / "run"
            with ThreadPoolExecutor(max_workers=16) as executor:
                descriptors = tuple(
                    executor.map(
                        lambda _index: store_text_object(run, ""),
                        range(64),
                    )
                )

            self.assertTrue(
                all(item == descriptors[0] for item in descriptors)
            )
            objects = list((run / "objects" / "sha256").glob("*.gz"))
            self.assertEqual(1, len(objects))
            self.assertEqual(b"", gzip.decompress(objects[0].read_bytes()))

    @unittest.skipUnless(os.name == "nt", "Windows long-path behavior")
    def test_object_store_supports_windows_paths_beyond_legacy_limit(self) -> None:
        temporary = Path(tempfile.mkdtemp())
        try:
            run = temporary / ("deep-a-" + "a" * 80) / ("deep-b-" + "b" * 80) / ("deep-c-" + "c" * 80)
            descriptor = store_text_object(run, "long-path evidence\n")
            object_path = run / descriptor["object_path"]

            self.assertGreater(len(str(object_path.resolve())), 260)
            self.assertTrue(verify_text_object(run, descriptor))
        finally:
            shutil.rmtree("\\\\?\\" + str(temporary.resolve()), ignore_errors=True)

    def test_run_directory_must_be_empty_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary) / "run"
            write_json_atomic(run / "old.json", {"status": "old"})

            with self.assertRaisesRegex(EvidenceLifecycleError, "not empty"):
                ensure_new_run_directory(run)


class EvidenceExecutionLeaseTests(unittest.TestCase):
    def _residual(
        self,
        lock_root: Path,
        *,
        owner_id: str,
        resource_key: str,
        plan_id: str = "plan:frozen",
    ) -> dict[str, object]:
        with evidence_execution_lease(
            lock_root,
            owner_id=owner_id,
            resource_key=resource_key,
            execution_key="request:frozen",
            lease_token=f"token:{owner_id}",
            plan_id=plan_id,
        ) as lease:
            lease["_preserve_residual"] = True
        current = read_evidence_execution_lease(
            lock_root,
            owner_id=owner_id,
            resource_key=resource_key,
            execution_key="request:frozen",
        )
        self.assertIsNotNone(current)
        return current

    def _settlement_request(self, rows: list[dict[str, object]]) -> dict[str, object]:
        return {
            "schema_version": "flowguard.evidence_interruption_settlement_request.v1",
            "plan_id": "plan:frozen",
            "process_id": os.getpid(),
            "operator_reason": "fixture launcher was externally interrupted",
            "zero_descendant_observation": {
                "descendant_process_ids": [],
                "observed_at_epoch": 1.0,
                "observed_by": "test:operator",
                "method": "fixture-process-tree-audit",
            },
            "leases": [
                {
                    "owner_id": row["owner_id"],
                    "resource_key": row["resource_key"],
                    "execution_key": row["execution_key"],
                    "lease_token": row["lease_token"],
                }
                for row in rows
            ],
        }

    def test_external_interruption_settles_exact_dead_process_leases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lock_root = Path(temporary) / "leases"
            rows = [
                self._residual(lock_root, owner_id="owner:a", resource_key="resource:a"),
                self._residual(lock_root, owner_id="owner:b", resource_key="resource:b"),
            ]
            with patch("flowguard.evidence_lifecycle._process_is_alive", return_value=False):
                incident = settle_interrupted_execution_leases(
                    lock_root, self._settlement_request(rows)
                )

            self.assertEqual("interrupted", incident["status"])
            self.assertFalse(incident["reusable"])
            self.assertFalse(incident["partial_results_reusable"])
            self.assertEqual(2, incident["settled_lease_count"])
            self.assertFalse(tuple(lock_root.glob("execution-*.lock")))
            self.assertTrue(Path(incident["incident_path"]).is_file())
            self.assertEqual(
                2,
                len(tuple(Path(incident["incident_path"]).parent.glob("leases/*.lock"))),
            )

    def test_external_interruption_is_all_or_nothing_for_foreign_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lock_root = Path(temporary) / "leases"
            rows = [
                self._residual(lock_root, owner_id="owner:a", resource_key="resource:a"),
                self._residual(
                    lock_root,
                    owner_id="owner:b",
                    resource_key="resource:b",
                    plan_id="plan:foreign",
                ),
            ]
            with (
                patch("flowguard.evidence_lifecycle._process_is_alive", return_value=False),
                self.assertRaisesRegex(EvidenceLifecycleError, "identity mismatch"),
            ):
                settle_interrupted_execution_leases(
                    lock_root, self._settlement_request(rows)
                )
            self.assertEqual(2, len(tuple(lock_root.glob("execution-*.lock"))))
            self.assertFalse((lock_root.parent / "interrupted-incidents").exists())

    def test_external_interruption_rejects_live_process_and_descendants(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lock_root = Path(temporary) / "leases"
            row = self._residual(lock_root, owner_id="owner:a", resource_key="resource:a")
            request = self._settlement_request([row])
            with self.assertRaisesRegex(EvidenceLifecycleError, "still live"):
                settle_interrupted_execution_leases(lock_root, request)
            request["zero_descendant_observation"]["descendant_process_ids"] = [123]
            with (
                patch("flowguard.evidence_lifecycle._process_is_alive", return_value=False),
                self.assertRaisesRegex(EvidenceLifecycleError, "descendants remain"),
            ):
                settle_interrupted_execution_leases(lock_root, request)
            self.assertEqual(1, len(tuple(lock_root.glob("execution-*.lock"))))

    def test_same_owner_resource_blocks_different_execution_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lock_root = Path(temporary) / "leases"
            with evidence_execution_lease(
                lock_root,
                owner_id="owner:model-a",
                resource_key="resource:model-a",
                execution_key="snapshot:first",
            ):
                with self.assertRaisesRegex(EvidenceLifecycleError, "already leased"):
                    with evidence_execution_lease(
                        lock_root,
                        owner_id="owner:model-a",
                        resource_key="resource:model-a",
                        execution_key="snapshot:second",
                    ):
                        self.fail("resource-wide mutual exclusion was bypassed")

    def test_cleanup_unconfirmed_requires_exact_episode_and_zero_descendants(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lock_root = Path(temporary) / "leases"
            with evidence_execution_lease(
                lock_root,
                owner_id="owner:model-a",
                resource_key="resource:model-a",
                execution_key="snapshot:first",
                lease_token="lease:one",
            ) as lease:
                lease["_preserve_residual"] = True
                lease["incident_episode_token"] = "episode:one"

            with self.assertRaisesRegex(EvidenceLifecycleError, "descendants remain"):
                settle_cleanup_unconfirmed_lease(
                    lock_root,
                    owner_id="owner:model-a",
                    resource_key="resource:model-a",
                    execution_key="snapshot:first",
                    incident_episode_token="episode:one",
                    descendant_process_ids=(123,),
                )
            with self.assertRaisesRegex(EvidenceLifecycleError, "token does not match"):
                settle_cleanup_unconfirmed_lease(
                    lock_root,
                    owner_id="owner:model-a",
                    resource_key="resource:model-a",
                    execution_key="snapshot:first",
                    incident_episode_token="episode:wrong",
                    descendant_process_ids=(),
                )
            settle_cleanup_unconfirmed_lease(
                lock_root,
                owner_id="owner:model-a",
                resource_key="resource:model-a",
                execution_key="snapshot:first",
                incident_episode_token="episode:one",
                descendant_process_ids=(),
            )
            self.assertIsNone(
                read_evidence_execution_lease(
                    lock_root,
                    owner_id="owner:model-a",
                    resource_key="resource:model-a",
                    execution_key="snapshot:next",
                )
            )

    def test_lease_is_readable_exclusive_and_released_by_its_token(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lock_root = Path(temporary) / "leases"

            with evidence_execution_lease(
                lock_root,
                owner_id="owner:full-validation",
                execution_key="request:abc123",
                lease_token="token:first",
                plan_id="plan:frozen",
            ) as acquired:
                current = read_evidence_execution_lease(
                    lock_root,
                    owner_id="owner:full-validation",
                    execution_key="request:abc123",
                )

                self.assertEqual(acquired, current)
                self.assertEqual("token:first", current["lease_token"])
                self.assertEqual("plan:frozen", current["plan_id"])
                with self.assertRaisesRegex(EvidenceLifecycleError, "already leased"):
                    with evidence_execution_lease(
                        lock_root,
                        owner_id="owner:full-validation",
                        execution_key="request:abc123",
                        lease_token="token:second",
                    ):
                        self.fail("a second owner must not enter the same execution")

            self.assertIsNone(
                read_evidence_execution_lease(
                    lock_root,
                    owner_id="owner:full-validation",
                    execution_key="request:abc123",
                )
            )

    def test_token_mismatch_preserves_residual_lock_and_blocks_reacquisition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lock_root = Path(temporary) / "leases"
            manager = evidence_execution_lease(
                lock_root,
                owner_id="owner:full-validation",
                execution_key="request:abc123",
                lease_token="token:original",
            )
            manager.__enter__()
            lease_path = next(lock_root.glob("execution-*.lock"))
            replacement = json.loads(lease_path.read_text(encoding="utf-8"))
            replacement["lease_token"] = "token:replacement"
            write_json_atomic(lease_path, replacement)

            with self.assertRaisesRegex(EvidenceLifecycleError, "token changed"):
                manager.__exit__(None, None, None)

            self.assertTrue(lease_path.is_file())
            self.assertEqual(
                "token:replacement",
                read_evidence_execution_lease(
                    lock_root,
                    owner_id="owner:full-validation",
                    execution_key="request:abc123",
                )["lease_token"],
            )
            with self.assertRaisesRegex(EvidenceLifecycleError, "already leased"):
                with evidence_execution_lease(
                    lock_root,
                    owner_id="owner:full-validation",
                    execution_key="request:abc123",
                    lease_token="token:new",
                ):
                    self.fail("a residual lock must never be broken automatically")

            lease_path.unlink()

    def test_owned_lease_is_released_when_the_execution_raises(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            lock_root = Path(temporary) / "leases"

            with self.assertRaisesRegex(RuntimeError, "fixture failure"):
                with evidence_execution_lease(
                    lock_root,
                    owner_id="owner:full-validation",
                    execution_key="request:abc123",
                ):
                    raise RuntimeError("fixture failure")

            self.assertIsNone(
                read_evidence_execution_lease(
                    lock_root,
                    owner_id="owner:full-validation",
                    execution_key="request:abc123",
                )
            )


class EvidenceLifecycleTests(unittest.TestCase):
    def _publish(self, root: Path, name: str, status: str = "pass", finished: float = 1.0) -> Path:
        run = root / "scope" / name
        write_json_atomic(
            run / "result.json",
            {
                "schema_version": "flowguard.validation_result.v1",
                "command": "flowguard-simulator",
                "status": status,
            },
        )
        publish_run(
            run,
            kind="model-simulator",
            status=status,
            result_path=run / "result.json",
            started_at_epoch=finished - 1,
            finished_at_epoch=finished,
        )
        return run

    def test_head_is_explicit_and_prior_run_becomes_collectible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._publish(root, "first", finished=1)
            self._publish(root, "second", status="fail", finished=2)

            audit = audit_evidence(root)
            by_path = {row["path"]: row for row in audit["runs"]}
            self.assertEqual("collectible", by_path["scope/first"]["classification"])
            self.assertEqual("current", by_path["scope/second"]["classification"])
            self.assertEqual("fail", audit["heads"][0]["status"])

    def test_child_current_pointer_cannot_verify_as_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "scope" / "child"
            write_json_atomic(run / "result.json", {"status": "pass"})
            publish_run(
                run,
                kind="fixture-child",
                status="pass",
                result_path=run / "result.json",
                authority_kind="child",
                parent_scope="fixture-parent",
            )

            self.assertEqual(
                "child", read_current_head(run.parent)["authority_kind"]
            )
            with self.assertRaisesRegex(EvidenceLifecycleError, "authority-kind mismatch"):
                read_current_head(run.parent, expected_authority_kind="parent")

    def test_legacy_parent_is_visible_but_not_inferred_current(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy = root / "release" / "old"
            write_json_atomic(
                legacy / "result.json",
                {
                    "schema_version": "flowguard.validation_result.v1",
                    "command": "check-flowguard-skill-suite",
                    "status": "pass",
                },
            )

            audit = audit_evidence(root)
            self.assertEqual(1, audit["counts"]["legacy_unmanaged"])
            self.assertEqual(0, audit["counts"]["current"])

    def test_unmanaged_tree_without_result_is_classified_and_preservable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_json_atomic(root / "external-receipts" / "receipt.json", {"status": "pass"})

            audit = audit_evidence(root)
            self.assertEqual(1, audit["counts"]["legacy_unmanaged"])
            self.assertEqual(0, audit["unclassified_bytes"])
            plan = plan_evidence_gc(
                root,
                keep=0,
                include_legacy=True,
                preserve_paths=("external-receipts",),
            )
            self.assertEqual(["external-receipts"], plan["preserved_paths"])
            self.assertEqual([], plan["candidates"])

    def test_gc_quarantines_restores_and_purges_exact_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self._publish(root, "first", finished=1)
            self._publish(root, "second", finished=2)
            plan = plan_evidence_gc(root, keep=0)

            receipt = apply_evidence_gc(root, plan)
            self.assertFalse(first.exists())
            self.assertEqual(1, len(receipt["moved"]))
            self.assertEqual(1, audit_evidence(root)["counts"]["quarantined"])

            restored = restore_evidence_quarantine(root, receipt["quarantine_id"])
            self.assertEqual(["scope/first"], restored["restored"])
            self.assertTrue(first.exists())

            second_plan = plan_evidence_gc(root, keep=0)
            second_receipt = apply_evidence_gc(root, second_plan)
            purged = purge_evidence_quarantine(root, second_receipt["quarantine_id"])
            self.assertEqual("pass", purged["status"])
            self.assertGreater(purged["deleted_bytes"], 0)

    def test_stale_plan_moves_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self._publish(root, "first", finished=1)
            self._publish(root, "second", finished=2)
            plan = plan_evidence_gc(root, keep=0)
            self._publish(root, "third", finished=3)

            with self.assertRaisesRegex(EvidenceLifecycleError, "stale"):
                apply_evidence_gc(root, plan)
            self.assertTrue(first.exists())

    def test_move_failure_rolls_back_every_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self._publish(root, "first", finished=1)
            second = self._publish(root, "second", finished=2)
            self._publish(root, "third", finished=3)
            plan = plan_evidence_gc(root, keep=0)
            real_move = __import__("shutil").move
            calls = 0

            def fail_second(source, destination):
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("fixture move failure")
                return real_move(source, destination)

            with patch("flowguard.evidence_lifecycle.shutil.move", side_effect=fail_second):
                with self.assertRaisesRegex(OSError, "fixture move failure"):
                    apply_evidence_gc(root, plan)
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())
            self.assertEqual(0, audit_evidence(root)["counts"]["quarantined"])

    def test_purge_cannot_target_active_store(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._publish(root, "current", finished=1)

            with self.assertRaisesRegex(EvidenceLifecycleError, "not one exact"):
                purge_evidence_quarantine(root, "../scope")

    def test_purge_handles_deep_quarantined_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            old = self._publish(root, "old", finished=1)
            deep = old / ("a" * 100) / ("b" * 100)
            deep_path = ("\\\\?\\" + str(deep.resolve())) if os.name == "nt" else str(deep)
            os.makedirs(deep_path, exist_ok=True)
            with open(os.path.join(deep_path, "receipt.json"), "w", encoding="utf-8") as handle:
                json.dump({"status": "historical"}, handle)
            self._publish(root, "current", finished=2)
            receipt = apply_evidence_gc(root, plan_evidence_gc(root, keep=0))

            purged = purge_evidence_quarantine(root, receipt["quarantine_id"])

            self.assertEqual("pass", purged["status"])
            self.assertFalse((root / ".quarantine" / receipt["quarantine_id"]).exists())
            self.assertTrue((root / ".quarantine" / "receipts" / f"purge-{receipt['quarantine_id']}.json").is_file())


if __name__ == "__main__":
    unittest.main()

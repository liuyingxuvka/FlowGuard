import json
import hashlib
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from flowguard.evidence_receipts import RECEIPT_STATUS_PROGRESS_ONLY, fingerprint_value, list_evidence_receipts
from flowguard.spec_check_cache import (
    SPEC_CHECK_STATE_BLOCKED,
    SPEC_CHECK_STATE_EXECUTED,
    SPEC_CHECK_STATE_NOT_RUN,
    SPEC_CHECK_STATE_REUSED_CURRENT,
    SPEC_CHECK_STATE_STALE,
    SPEC_TERMINAL_BLOCKED,
    SPEC_TERMINAL_FAIL,
    SPEC_TERMINAL_NOT_RUN_DEPENDENCY,
    SPEC_TERMINAL_TIMEOUT,
    PortableSpecReceiptEnvelope,
    aggregate_spec_check_receipts,
    begin_spec_session,
    _ProcessTreeTimeout,
    _portable_envelope_path,
    _load_portable_envelope,
    _load_portable_receipt_ref,
    _portable_receipt_semantic_identity,
    _pid_alive,
    _session_record_path,
    capture_spec_input_manifest,
    capture_spec_toolchain_snapshot,
    close_spec_session,
    consume_spec_receipt,
    discover_governed_input_paths,
    project_execution_toolchain_snapshot,
    run_spec_check,
    review_spec_provider_close,
    spec_receipt_to_proof_artifact,
)
from flowguard.spec_providers import (
    PROVIDER_HASH_POLICY_RAW,
    PROVIDER_HASH_POLICY_TASK_DEFINITION,
    provider_source_sha256,
)
from flowguard.spec_work_package import SpecProviderRef, SpecWorkPackage


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _package_config(change_id: str) -> dict:
    return {
        "provider_id": "openspec",
        "work_package_id": change_id,
        "task_binding_rules": [
            {"task_prefix": "1.", "obligation_ids": ["req.one"], "binding_kind": "direct"}
        ],
        "check_policies": [
            {
                "check_id": "check.one",
                "validation_obligation_ids": ["validation:one"],
                "cross_change_safe": True,
            }
        ],
    }


def _project(change_ids: tuple[str, ...] = ("change-one",)) -> tempfile.TemporaryDirectory:
    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name)
    _write(root / "flowguard/source.py", "VALUE = 1\n")
    for change_id in change_ids:
        change = root / "openspec/changes" / change_id
        _write(change / "tasks.md", "# Tasks\n\n- [x] 1.1 Complete the work\n")
        _write(
            change / "verification-contract.yaml",
            """contract_version: 3
obligations:
  - id: req.one
    source: specs/example/spec.md
    claim: One requirement.
    evidence: [check.one]
checks:
  - id: check.one
    kind: command
    command: python
    args: [-c, 'pass']
    covers: [req.one]
    required: true
    expected:
      exit_code: 0
""",
        )
    _write(
        root / ".flowguard/spec_provider_work_packages/bindings.json",
        json.dumps({"packages": [_package_config(value) for value in change_ids]}, indent=2) + "\n",
    )
    return temporary


def _aggregate_project() -> tempfile.TemporaryDirectory:
    temporary = tempfile.TemporaryDirectory()
    root = Path(temporary.name)
    _write(root / "flowguard/source.py", "VALUE = 1\n")
    change = root / "openspec/changes/change-one"
    _write(change / "tasks.md", "# Tasks\n\n- [x] 1.1 Aggregate receipts\n")
    _write(
        change / "verification-contract.yaml",
        """contract_version: 3
evidence_roots:
  SPEC_EVIDENCE: .flowguard/evidence/spec-work-packages
obligations:
  - id: req.a
    source: specs/example/spec.md
    claim: A.
    evidence: [owner.a, owner.parent]
  - id: req.b
    source: specs/example/spec.md
    claim: B.
    evidence: [owner.b, owner.parent]
checks:
  - id: owner.a
    kind: receipt
    semantic_check_id: semantic.a
    execution_id: owner.a.v1
    receipt_ref: {provider_id: openspec, work_package_id: change-one, adapter: portable-receipt.v1, ref_path: <SPEC_EVIDENCE>/portable-refs/openspec/change-one/owner.a.json}
    consumer: openspec.change.change-one
    covers: [req.a]
  - id: owner.b
    kind: receipt
    semantic_check_id: semantic.b
    execution_id: owner.b.v1
    receipt_ref: {provider_id: openspec, work_package_id: change-one, adapter: portable-receipt.v1, ref_path: <SPEC_EVIDENCE>/portable-refs/openspec/change-one/owner.b.json}
    consumer: openspec.change.change-one
    covers: [req.b]
  - id: owner.parent
    kind: receipt
    semantic_check_id: semantic.parent
    execution_id: owner.parent.v1
    receipt_ref: {provider_id: openspec, work_package_id: change-one, adapter: portable-receipt.v1, ref_path: <SPEC_EVIDENCE>/portable-refs/openspec/change-one/owner.parent.json}
    consumer: openspec.change.change-one
    covers: [req.a, req.b]
""",
    )
    canonical = [
        {
            "check_id": "owner.a",
            "semantic_check_id": "semantic.a",
            "execution_id": "owner.a.v1",
            "command": ["python", "-c", "pass"],
            "input_paths": ["flowguard/source.py"],
            "validation_obligation_ids": ["validation:a"],
            "cross_change_safe": True,
            "snapshot_policy": "live-scoped",
        },
        {
            "check_id": "owner.b",
            "semantic_check_id": "semantic.b",
            "execution_id": "owner.b.v1",
            "command": ["python", "-c", "pass"],
            "input_paths": ["flowguard/source.py"],
            "validation_obligation_ids": ["validation:b"],
            "snapshot_policy": "live-scoped",
        },
        {
            "check_id": "owner.parent",
            "semantic_check_id": "semantic.parent",
            "execution_id": "owner.parent.v1",
            "execution_mode": "aggregate-child-receipts",
            "child_check_ids": ["owner.a", "owner.b"],
            "input_paths": ["flowguard/source.py"],
            "validation_obligation_ids": ["validation:parent"],
            "snapshot_policy": "live-scoped",
        },
    ]
    _write(
        root / ".flowguard/spec_provider_work_packages/bindings.json",
        json.dumps(
            {
                "packages": [
                    {
                        "provider_id": "openspec",
                        "work_package_id": "change-one",
                        "canonical_checks": canonical,
                        "task_binding_rules": [
                            {"task_prefix": "1.", "obligation_ids": ["req.a", "req.b"]}
                        ],
                    }
                ]
            },
            indent=2,
        )
        + "\n",
    )
    return temporary


def _counter_command(extra: str = "") -> tuple[str, ...]:
    code = (
        "from pathlib import Path; "
        "p=Path('counter.txt'); "
        "p.write_text(str(int(p.read_text())+1) if p.exists() else '1')"
    )
    if extra:
        code += f"; Path('tag.txt').write_text({extra!r})"
    return (sys.executable, "-c", code)


def _run(root: Path, **overrides):
    arguments = {
        "provider_id": "openspec",
        "work_package_id": "change-one",
        "check_id": "check.one",
        "semantic_id": "semantic:one",
        "command": _counter_command(),
        "validation_obligation_ids": ("validation:one",),
        "timeout_seconds": 5,
    }
    arguments.update(overrides)
    return run_spec_check(root, **arguments)


class SpecInputManifestTests(unittest.TestCase):
    def test_cross_change_owner_toolchain_excludes_provider_local_identity(self) -> None:
        package = SpecWorkPackage(
            provider=SpecProviderRef(
                "openspec",
                "openspec",
                provider_version="1.6.0",
                schema_version="1",
                adapter_version="1.0",
            ),
            work_package_id="change-one",
            change_id="change-one",
        )
        changed_provider = replace(
            package,
            provider=replace(
                package.provider,
                provider_version="1.7.0",
                schema_version="2",
                adapter_version="2.0",
            ),
        )

        first = capture_spec_toolchain_snapshot(package)
        second = capture_spec_toolchain_snapshot(changed_provider)
        self.assertNotEqual(first.fingerprint, second.fingerprint)

        projected_first = project_execution_toolchain_snapshot(
            first,
            cross_change_safe=True,
        )
        projected_second = project_execution_toolchain_snapshot(
            second,
            cross_change_safe=True,
        )
        self.assertEqual(projected_first, projected_second)
        self.assertFalse(
            {"provider_id", "provider_version", "provider_schema_version", "provider_adapter_version"}
            & set(projected_first.metadata)
        )

    def test_session_history_directory_is_bounded_for_long_windows_roots(self) -> None:
        root = Path("C:/") / ("nested-" * 20)
        first = _session_record_path(root, "session:" + ("owner:" * 80), "begin")
        second = _session_record_path(root, "session:" + ("owner:" * 80), "begin")
        other = _session_record_path(root, "session:" + ("other:" * 80), "begin")

        self.assertEqual(first, second)
        self.assertNotEqual(first.parent, other.parent)
        self.assertLessEqual(len(first.parent.name), 32)

    def test_derived_outputs_and_mtime_do_not_enter_input_fingerprint(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        before = capture_spec_input_manifest(root)
        derived = root / ".flowguard/evidence/spec-work-packages/outputs/run/stdout.log"
        _write(derived, "derived\n")
        for path in discover_governed_input_paths(root):
            path.touch()
        after = capture_spec_input_manifest(root)

        self.assertEqual(before.fingerprint, after.fingerprint)
        self.assertNotIn(
            derived.resolve(),
            {path.resolve() for path in discover_governed_input_paths(root)},
        )

    def test_model_result_files_cannot_make_their_own_check_stale(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        result_path = root / ".flowguard/example_model/result.json"
        _write(result_path, '{"status":"old"}\n')
        begin_spec_session(root, "openspec", "change-one")
        _write(result_path, '{"status":"new"}\n')

        result = _run(root)

        self.assertEqual(result.state, SPEC_CHECK_STATE_EXECUTED)
        self.assertNotIn(
            result_path.resolve(),
            {path.resolve() for path in discover_governed_input_paths(root)},
        )

    def test_v1_migration_evidence_is_not_runtime_input_authority(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        legacy = root / ".agents/skills/example/.skillguard/work-contract.json"
        current = root / ".agents/skills/example/.skillguard/contract-source.json"
        _write(legacy, '{"legacy":1}\n')
        _write(current, '{"schema_version":"skillguard.contract_source.v2"}\n')
        begin_spec_session(root, "openspec", "change-one")
        _write(legacy, '{"legacy":2}\n')
        self.assertEqual(SPEC_CHECK_STATE_EXECUTED, _run(root).state)

        begin_spec_session(root, "openspec", "change-one")
        _write(current, '{"schema_version":"skillguard.contract_source.v2","changed":true}\n')
        self.assertEqual(SPEC_CHECK_STATE_STALE, _run(root).state)

    def test_real_model_or_spec_contract_change_still_invalidates_session(self) -> None:
        for relative_path in (
            ".flowguard/example_model/model.py",
            "openspec/changes/change-one/verification-contract.yaml",
        ):
            with self.subTest(path=relative_path):
                temporary = _project()
                self.addCleanup(temporary.cleanup)
                root = Path(temporary.name)
                path = root / relative_path
                if not path.exists():
                    _write(path, "VALUE = 1\n")
                begin_spec_session(root, "openspec", "change-one")
                _write(path, path.read_text(encoding="utf-8") + "# changed\n")

                result = _run(root)

                self.assertEqual(result.state, SPEC_CHECK_STATE_STALE)
                self.assertIn("session_inputs_changed_before_check", result.blockers)

    def test_begin_and_post_snapshots_close_only_when_unchanged_and_complete(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begun = begin_spec_session(root, "openspec", "change-one")
        executed = _run(root)
        closed = close_spec_session(root, "openspec", "change-one")

        self.assertTrue(begun.ok)
        self.assertTrue(executed.ok)
        self.assertTrue(closed.ok, closed.blockers)
        self.assertEqual(closed.begin_fingerprint, closed.post_fingerprint)
        self.assertTrue((root / begun.begin_record_path).is_file())
        self.assertTrue((root / closed.close_record_path).is_file())

        old_close = (root / closed.close_record_path).read_bytes()
        newer = begin_spec_session(root, "openspec", "change-one")
        self.assertNotEqual(begun.session_id, newer.session_id)
        self.assertEqual(old_close, (root / closed.close_record_path).read_bytes())

    def test_source_change_after_begin_makes_check_stale_without_execution(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        _write(root / "flowguard/source.py", "VALUE = 2\n")
        result = _run(root)

        self.assertEqual(result.state, SPEC_CHECK_STATE_STALE)
        self.assertEqual(result.terminal_status, SPEC_TERMINAL_BLOCKED)
        self.assertFalse((root / "counter.txt").exists())
        self.assertIn("session_inputs_changed_before_check", result.blockers)

    def test_peer_write_after_check_blocks_session_close(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begun = begin_spec_session(root, "openspec", "change-one")
        self.assertFalse(begun.close_record_path)
        self.assertTrue(_run(root).ok)
        _write(root / "flowguard/source.py", "VALUE = 3\n")

        closed = close_spec_session(root, "openspec", "change-one")

        self.assertFalse(closed.ok)
        self.assertEqual("blocked", closed.state)
        self.assertIn("required_check_scope_stale:check.one", closed.blockers)


class PortableReceiptWireTests(unittest.TestCase):
    def test_external_owner_ref_is_verified_in_place_without_a_flowguard_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _write(root / "flowguard/source.py", "VALUE = 1\n")
            evidence_root = root / "persistent-evidence"
            fixture = Path(__file__).parent / "fixtures/portable_receipt_wire"
            target = evidence_root / "fixture"
            target.mkdir(parents=True)
            for source in fixture.iterdir():
                (target / source.name).write_bytes(source.read_bytes())

            envelope_value = json.loads((target / "envelope.json").read_text(encoding="utf-8"))
            envelope_value["provider_id"] = "skillguard"
            envelope_value["source_manifest_ref"] = envelope_value["source_manifest_ref"].replace(
                "<SPEC_EVIDENCE>", "<SKILLGUARD_EVIDENCE>"
            )
            envelope_value["sidecar_refs"] = {
                role: value.replace("<SPEC_EVIDENCE>", "<SKILLGUARD_EVIDENCE>")
                for role, value in envelope_value["sidecar_refs"].items()
            }
            receipt_id, receipt_fingerprint = _portable_receipt_semantic_identity(
                provider_id=envelope_value["provider_id"],
                work_package_id=envelope_value["work_package_id"],
                check_id=envelope_value["check_id"],
                semantic_check_id=envelope_value["semantic_check_id"],
                execution_id=envelope_value["execution_id"],
                execution_key=envelope_value["execution_key"],
                source_manifest_id=envelope_value["source_manifest_id"],
                source_manifest_hash=envelope_value["source_manifest_hash"],
                source_hash_policy=envelope_value["source_hash_policy"],
                source_fingerprint=envelope_value["source_fingerprint"],
                toolchain_fingerprint=envelope_value["toolchain_fingerprint"],
                result_fingerprint=envelope_value["result_fingerprint"],
                termination_fingerprint=envelope_value["termination_fingerprint"],
                snapshot_policy=envelope_value["snapshot_policy"],
                coverage_ids=envelope_value["coverage_ids"],
                validation_obligation_ids=envelope_value["validation_obligation_ids"],
                sidecar_hashes=envelope_value["sidecar_hashes"],
                child_receipts=(),
            )
            envelope_value["receipt_id"] = receipt_id
            envelope_value["receipt_fingerprint"] = receipt_fingerprint
            envelope_value["envelope_fingerprint"] = fingerprint_value(
                {key: value for key, value in envelope_value.items() if key != "envelope_fingerprint"}
            )
            _write(target / "envelope.json", json.dumps(envelope_value, sort_keys=True) + "\n")

            pointer = json.loads((target / "ref.json").read_text(encoding="utf-8"))
            pointer.update(
                {
                    "provider_id": "skillguard",
                    "envelope_ref": "<SKILLGUARD_EVIDENCE>/fixture/envelope.json",
                    "envelope_fingerprint": envelope_value["envelope_fingerprint"],
                    "receipt_id": receipt_id,
                    "receipt_fingerprint": receipt_fingerprint,
                }
            )
            _write(target / "ref.json", json.dumps(pointer, sort_keys=True) + "\n")

            with patch.dict(os.environ, {"FLOWGUARD_SPEC_EVIDENCE_ROOT": str(evidence_root)}):
                observed_id, observed = _load_portable_receipt_ref(
                    root,
                    "skillguard",
                    "fixture-change",
                    "owner.fixture",
                    ref_path="<SKILLGUARD_EVIDENCE>/fixture/ref.json",
                )
                self.assertEqual(receipt_id, observed_id)
                self.assertEqual("skillguard", observed.provider_id)

                _write(target / "result.json", "{\"tampered\":true}\n")
                with self.assertRaisesRegex(ValueError, "sidecar content hash mismatch"):
                    _load_portable_receipt_ref(
                        root,
                        "skillguard",
                        "fixture-change",
                        "owner.fixture",
                        ref_path="<SKILLGUARD_EVIDENCE>/fixture/ref.json",
                    )

    def test_frozen_receipts_flow_into_v3_report_then_read_only_close_review(self) -> None:
        temporary = _aggregate_project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        evidence_root = root / "persistent-evidence"
        policy = {
            "version": 2,
            "algorithm": "sha256",
            "task_checkbox_normalization": "markdown-checkbox-state-v1",
            "output_classifier_version": "verification-generated-output-v2",
        }
        with patch.dict(os.environ, {"FLOWGUARD_SPEC_EVIDENCE_ROOT": str(evidence_root)}):
            begin_spec_session(
                root,
                "openspec",
                "change-one",
                snapshot_policy="frozen-required",
            )
            for check_id, semantic_id, validation_id in (
                ("owner.a", "semantic.a", "validation:a"),
                ("owner.b", "semantic.b", "validation:b"),
            ):
                _run(
                    root,
                    check_id=check_id,
                    semantic_id=semantic_id,
                    validation_obligation_ids=(validation_id,),
                    command=(sys.executable, "-c", "pass"),
                )
            aggregate_spec_check_receipts(
                root,
                provider_id="openspec",
                work_package_id="change-one",
                check_id="owner.parent",
            )
            closed = close_spec_session(root, "openspec", "change-one")
            self.assertTrue(closed.ok, closed.blockers)

            snapshot_id = fingerprint_value({"openspec_snapshot": "fixture"})
            rows = {}
            for check_id in ("owner.a", "owner.b", "owner.parent"):
                _, envelope = _load_portable_receipt_ref(
                    root, "openspec", "change-one", check_id
                )
                rows[check_id] = {
                    "status": "passed",
                    "kind": "receipt",
                    "covers": list(envelope.coverage_ids),
                    "semantic_check_id": envelope.semantic_check_id,
                    "execution_id": envelope.execution_id,
                    "execution_owner": f"{envelope.provider_id}:{envelope.execution_id}",
                    "execution_key": envelope.execution_key,
                    "receipt_id": envelope.receipt_id,
                    "depends_on_receipt_ids": [envelope.receipt_id],
                    "result_hash": envelope.result_fingerprint,
                    "toolchain_identity": envelope.toolchain_fingerprint,
                    "input_hashes": {"source_manifest_id": envelope.source_manifest_id},
                    "accounting": "aggregated",
                    "portable_receipt_ref": (
                        f"<SPEC_EVIDENCE>/portable-refs/openspec/change-one/{check_id}.json"
                    ),
                    "envelope_fingerprint": envelope.fingerprint,
                    "source_manifest_id": envelope.source_manifest_id,
                    "source_manifest_hash": envelope.source_manifest_hash,
                    "snapshot_policy": "frozen",
                    "snapshot_manifest_id": snapshot_id,
                    "source_hash_policy": policy,
                    "validation_scope": "full",
                }
            change = root / "openspec/changes/change-one"
            tasks_path = change / "tasks.md"
            contract_path = change / "verification-contract.yaml"
            report = {
                "report_protocol_version": 3,
                "status": "pass",
                "run": {
                    "protocol_version": 3,
                    "validation_mode": "full",
                    "snapshot_manifest_id": snapshot_id,
                },
                "source_hash_policy": policy,
                "source_hashes": {
                    "openspec/changes/change-one/tasks.md": (
                        "sha256:"
                        + provider_source_sha256(
                            tasks_path, PROVIDER_HASH_POLICY_TASK_DEFINITION
                        )
                    ),
                    "openspec/changes/change-one/verification-contract.yaml": (
                        "sha256:"
                        + provider_source_sha256(contract_path, PROVIDER_HASH_POLICY_RAW)
                    ),
                },
                "contract_hash": "sha256:" + hashlib.sha256(contract_path.read_bytes()).hexdigest(),
                "checks": rows,
            }
            _write(change / "verification-report.json", json.dumps(report, sort_keys=True) + "\n")

            review = review_spec_provider_close(root, "openspec", "change-one")

        self.assertTrue(review.ok, review.findings)
        self.assertTrue(review.archive_ready)

    def test_static_wire_fixture_has_canonical_hashes_and_exact_shapes(self) -> None:
        fixture = Path(__file__).parent / "fixtures/portable_receipt_wire"
        envelope_value = json.loads((fixture / "envelope.json").read_text(encoding="utf-8"))
        envelope = PortableSpecReceiptEnvelope.from_dict(envelope_value)
        manifest = json.loads((fixture / "source-manifest.json").read_text(encoding="utf-8"))

        self.assertEqual({"stdout", "stderr", "result", "termination"}, set(envelope.sidecar_refs))
        self.assertEqual([], list(envelope.child_receipt_refs))
        self.assertEqual(
            envelope.source_fingerprint,
            fingerprint_value(dict(sorted(manifest["files"].items()))),
        )
        for role, path_token in envelope.sidecar_refs.items():
            path = fixture / Path(path_token).name
            observed = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(envelope.sidecar_hashes[role], observed)
        expected_id, expected_fingerprint = _portable_receipt_semantic_identity(
            provider_id=envelope.provider_id,
            work_package_id=envelope.work_package_id,
            check_id=envelope.check_id,
            semantic_check_id=envelope.semantic_check_id,
            execution_id=envelope.execution_id,
            execution_key=envelope.execution_key,
            source_manifest_id=envelope.source_manifest_id,
            source_manifest_hash=envelope.source_manifest_hash,
            source_hash_policy=envelope.source_hash_policy,
            source_fingerprint=envelope.source_fingerprint,
            toolchain_fingerprint=envelope.toolchain_fingerprint,
            result_fingerprint=envelope.result_fingerprint,
            termination_fingerprint=envelope.termination_fingerprint,
            snapshot_policy=envelope.snapshot_policy,
            coverage_ids=envelope.coverage_ids,
            validation_obligation_ids=envelope.validation_obligation_ids,
            sidecar_hashes=envelope.sidecar_hashes,
            child_receipts=(),
        )
        self.assertEqual((envelope.receipt_id, envelope.receipt_fingerprint), (expected_id, expected_fingerprint))

    def test_missing_or_extra_sidecar_is_rejected(self) -> None:
        fixture = Path(__file__).parent / "fixtures/portable_receipt_wire/envelope.json"
        original = json.loads(fixture.read_text(encoding="utf-8"))
        for mutate in ("missing", "extra"):
            with self.subTest(mutate=mutate):
                value = json.loads(json.dumps(original))
                if mutate == "missing":
                    value["sidecar_refs"].pop("stdout")
                    value["sidecar_hashes"].pop("stdout")
                else:
                    value["sidecar_refs"]["receipt"] = "<SPEC_EVIDENCE>/fixture/receipt.json"
                    value["sidecar_hashes"]["receipt"] = fingerprint_value({"receipt": True})
                value["envelope_fingerprint"] = fingerprint_value(
                    {key: item for key, item in value.items() if key != "envelope_fingerprint"}
                )
                with self.assertRaises(ValueError):
                    PortableSpecReceiptEnvelope.from_dict(value)

    def test_resigned_semantic_identity_tamper_is_rejected(self) -> None:
        for field_name in ("receipt_id", "receipt_fingerprint"):
            with self.subTest(field=field_name):
                temporary = _project()
                self.addCleanup(temporary.cleanup)
                root = Path(temporary.name)
                begin_spec_session(root, "openspec", "change-one")
                executed = _run(root)
                envelope_path = _portable_envelope_path(root, executed.receipt_id)
                value = json.loads(envelope_path.read_text(encoding="utf-8"))
                value[field_name] = fingerprint_value({"tampered": field_name})
                value["envelope_fingerprint"] = fingerprint_value(
                    {key: item for key, item in value.items() if key != "envelope_fingerprint"}
                )
                _write(envelope_path, json.dumps(value, sort_keys=True) + "\n")

                from flowguard.spec_check_cache import consume_spec_receipt

                review = consume_spec_receipt(root, receipt_id=executed.receipt_id)
                self.assertFalse(review.ok)
                self.assertIn(f"portable_{field_name}_semantic_mismatch", review.findings)

    def test_run_id_and_timestamps_do_not_change_semantic_receipt_identity(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        failing = (sys.executable, "-c", "raise SystemExit(7)")

        first = _run(root, command=failing)
        first_envelope = _load_portable_envelope(root, first.receipt_id)
        second = _run(root, command=failing)
        second_envelope = _load_portable_envelope(root, second.receipt_id)

        self.assertNotEqual(first.receipt_id, second.receipt_id)
        self.assertEqual(first_envelope.receipt_id, second_envelope.receipt_id)
        self.assertEqual(first_envelope.receipt_fingerprint, second_envelope.receipt_fingerprint)


class SpecReceiptReuseTests(unittest.TestCase):
    def test_parent_accepts_current_scoped_children_from_an_earlier_global_snapshot(self) -> None:
        temporary = _aggregate_project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        first_a = _run(
            root,
            check_id="owner.a",
            semantic_id="semantic.a",
            validation_obligation_ids=("validation:a",),
            command=(sys.executable, "-c", "pass"),
            cross_change_safe=True,
        )
        first_b = _run(
            root,
            check_id="owner.b",
            semantic_id="semantic.b",
            validation_obligation_ids=("validation:b",),
            command=(sys.executable, "-c", "pass"),
        )

        _write(root / "docs/unrelated.md", "Unrelated provider note.\n")
        begin_spec_session(root, "openspec", "change-one")
        reused_a = _run(
            root,
            check_id="owner.a",
            semantic_id="semantic.a",
            validation_obligation_ids=("validation:a",),
            command=(sys.executable, "-c", "pass"),
            cross_change_safe=True,
        )
        reused_b = _run(
            root,
            check_id="owner.b",
            semantic_id="semantic.b",
            validation_obligation_ids=("validation:b",),
            command=(sys.executable, "-c", "pass"),
        )
        parent = aggregate_spec_check_receipts(
            root,
            provider_id="openspec",
            work_package_id="change-one",
            check_id="owner.parent",
        )

        self.assertEqual(SPEC_CHECK_STATE_REUSED_CURRENT, reused_a.state)
        self.assertEqual(SPEC_CHECK_STATE_REUSED_CURRENT, reused_b.state)
        self.assertEqual(first_a.receipt_id, reused_a.receipt_id)
        self.assertEqual(first_b.receipt_id, reused_b.receipt_id)
        self.assertEqual(SPEC_CHECK_STATE_EXECUTED, parent.state)
        self.assertTrue(parent.ok, parent.blockers)

    def test_orchestrator_evidence_root_is_not_inherited_by_check_process(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        evidence_root = (root / ".persistent-spec-evidence").resolve()
        command = (
            sys.executable,
            "-c",
            "import os; raise SystemExit('FLOWGUARD_SPEC_EVIDENCE_ROOT' in os.environ)",
        )

        with patch.dict(
            os.environ,
            {"FLOWGUARD_SPEC_EVIDENCE_ROOT": str(evidence_root)},
            clear=False,
        ):
            begin_spec_session(root, "openspec", "change-one")
            result = _run(root, command=command)

        self.assertEqual(SPEC_CHECK_STATE_EXECUTED, result.state)
        self.assertEqual(0, result.exit_code)

    def test_parent_aggregation_verifies_exact_children_and_reuses_only_identical_parent(self) -> None:
        temporary = _aggregate_project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        child_a = _run(
            root,
            check_id="owner.a",
            semantic_id="semantic.a",
            validation_obligation_ids=("validation:a",),
            command=(sys.executable, "-c", "pass"),
        )
        child_b = _run(
            root,
            check_id="owner.b",
            semantic_id="semantic.b",
            validation_obligation_ids=("validation:b",),
            command=(sys.executable, "-c", "pass"),
        )

        first = aggregate_spec_check_receipts(
            root,
            provider_id="openspec",
            work_package_id="change-one",
            check_id="owner.parent",
        )
        second = aggregate_spec_check_receipts(
            root,
            provider_id="openspec",
            work_package_id="change-one",
            check_id="owner.parent",
        )
        missing = aggregate_spec_check_receipts(
            root,
            provider_id="openspec",
            work_package_id="change-one",
            check_id="owner.parent",
            child_receipt_ids=(child_a.receipt_id,),
        )

        self.assertEqual(SPEC_CHECK_STATE_EXECUTED, first.state)
        self.assertEqual(SPEC_CHECK_STATE_REUSED_CURRENT, second.state)
        self.assertEqual(first.receipt_id, second.receipt_id)
        self.assertEqual(SPEC_CHECK_STATE_BLOCKED, missing.state)
        self.assertIn("aggregate_child_receipt_set_not_declared", missing.blockers)
        self.assertEqual({child_a.receipt_id, child_b.receipt_id}, set(first.child_receipt_ids))

    def test_swapped_child_envelope_is_fail_closed(self) -> None:
        temporary = _aggregate_project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        child_a = _run(
            root,
            check_id="owner.a",
            semantic_id="semantic.a",
            validation_obligation_ids=("validation:a",),
            command=(sys.executable, "-c", "pass"),
        )
        _run(
            root,
            check_id="owner.b",
            semantic_id="semantic.b",
            validation_obligation_ids=("validation:b",),
            command=(sys.executable, "-c", "pass"),
        )
        envelope_path = _portable_envelope_path(root, child_a.receipt_id)
        value = json.loads(envelope_path.read_text(encoding="utf-8"))
        value["check_id"] = "owner.b"
        value["envelope_fingerprint"] = fingerprint_value(
            {key: item for key, item in value.items() if key != "envelope_fingerprint"}
        )
        _write(envelope_path, json.dumps(value, sort_keys=True) + "\n")

        parent = aggregate_spec_check_receipts(
            root,
            provider_id="openspec",
            work_package_id="change-one",
            check_id="owner.parent",
        )

        self.assertEqual(SPEC_CHECK_STATE_BLOCKED, parent.state)
        self.assertTrue(any(item.startswith("child_receipt_not_current_pass:owner.a") for item in parent.blockers))

    def test_upstream_receipt_change_marks_parent_for_minimum_revalidation(self) -> None:
        temporary = _aggregate_project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        for check_id, semantic_id, validation_id in (
            ("owner.a", "semantic.a", "validation:a"),
            ("owner.b", "semantic.b", "validation:b"),
        ):
            _run(
                root,
                check_id=check_id,
                semantic_id=semantic_id,
                validation_obligation_ids=(validation_id,),
                command=(sys.executable, "-c", "pass"),
            )
        aggregate_spec_check_receipts(
            root,
            provider_id="openspec",
            work_package_id="change-one",
            check_id="owner.parent",
        )

        _run(
            root,
            check_id="owner.a",
            semantic_id="semantic.a",
            validation_obligation_ids=("validation:a",),
            command=(sys.executable, "-c", "print('new execution definition')"),
        )
        closed = close_spec_session(root, "openspec", "change-one")

        self.assertIn("owner.a", closed.minimum_revalidation)
        self.assertIn("owner.parent", closed.minimum_revalidation)
        self.assertIn("required_check_not_passed:owner.parent", closed.blockers)

    def test_pid_probe_is_safe_for_the_current_process(self) -> None:
        self.assertTrue(_pid_alive(os.getpid()))
        self.assertFalse(_pid_alive(-1))

    def test_same_execution_key_runs_once_then_reuses_current_receipt(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")

        first = _run(root)
        second = _run(root)

        self.assertEqual(first.state, SPEC_CHECK_STATE_EXECUTED)
        self.assertEqual(second.state, SPEC_CHECK_STATE_REUSED_CURRENT)
        self.assertEqual(first.receipt_id, second.receipt_id)
        self.assertEqual((root / "counter.txt").read_text(), "1")

    def test_cross_change_reuse_requires_explicit_authorization(self) -> None:
        for authorized, expected_state in (
            (False, SPEC_CHECK_STATE_EXECUTED),
            (True, SPEC_CHECK_STATE_REUSED_CURRENT),
        ):
            with self.subTest(authorized=authorized):
                temporary = _project(("change-one", "change-two"))
                self.addCleanup(temporary.cleanup)
                root = Path(temporary.name)
                begin_spec_session(root, "openspec", "change-one")
                first = _run(root, cross_change_safe=authorized)
                begin_spec_session(root, "openspec", "change-two")
                second = _run(
                    root,
                    work_package_id="change-two",
                    cross_change_safe=authorized,
                )
                self.assertEqual(first.state, SPEC_CHECK_STATE_EXECUTED)
                self.assertEqual(second.state, expected_state)
                self.assertEqual((root / "counter.txt").read_text(), "1" if authorized else "2")
                if authorized:
                    portable_id, envelope = _load_portable_receipt_ref(
                        root,
                        "openspec",
                        "change-two",
                        "check.one",
                    )
                    self.assertEqual(portable_id, envelope.receipt_id)
                    self.assertEqual(envelope.work_package_id, "change-one")
                    consumed = consume_spec_receipt(
                        root,
                        provider_id="openspec",
                        work_package_id="change-two",
                        check_id="check.one",
                    )
                    self.assertTrue(consumed.ok, consumed.findings)

    def test_cross_change_reuse_keeps_coverage_in_the_consumer_pointer(self) -> None:
        temporary = _project(("change-one", "change-two"))
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        second_contract = root / "openspec/changes/change-two/verification-contract.yaml"
        second_contract.write_text(
            second_contract.read_text(encoding="utf-8").replace("req.one", "req.two"),
            encoding="utf-8",
            newline="\n",
        )
        bindings_path = root / ".flowguard/spec_provider_work_packages/bindings.json"
        bindings = json.loads(bindings_path.read_text(encoding="utf-8"))
        bindings["packages"][1]["task_binding_rules"][0]["obligation_ids"] = ["req.two"]
        _write(bindings_path, json.dumps(bindings, indent=2) + "\n")

        begin_spec_session(root, "openspec", "change-one")
        first = _run(root, cross_change_safe=True)
        begin_spec_session(root, "openspec", "change-two")
        second = _run(
            root,
            work_package_id="change-two",
            cross_change_safe=True,
        )

        self.assertEqual(SPEC_CHECK_STATE_EXECUTED, first.state)
        self.assertEqual(SPEC_CHECK_STATE_REUSED_CURRENT, second.state)
        self.assertEqual(first.receipt_id, second.receipt_id)
        self.assertEqual("1", (root / "counter.txt").read_text())
        pointer_path = (
            root
            / ".flowguard/evidence/spec-work-packages/portable-refs/openspec/change-two/check.one.json"
        )
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        self.assertEqual(["req.two"], pointer["coverage_ids"])

    def test_caller_cannot_expand_provider_cross_change_authority(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        bindings_path = root / ".flowguard/spec_provider_work_packages/bindings.json"
        payload = json.loads(bindings_path.read_text(encoding="utf-8"))
        payload["packages"][0]["check_policies"][0]["cross_change_safe"] = False
        _write(bindings_path, json.dumps(payload, indent=2) + "\n")
        begin_spec_session(root, "openspec", "change-one")

        result = _run(root, cross_change_safe=True)

        self.assertEqual(result.state, SPEC_CHECK_STATE_BLOCKED)
        self.assertIn("cross_change_safe_not_authorized_by_provider", result.blockers)

    def test_command_input_tool_or_coverage_change_cannot_reuse(self) -> None:
        # Command definition changes.
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        first = _run(root)
        command_changed = _run(root, command=_counter_command("changed"))
        self.assertEqual(first.state, SPEC_CHECK_STATE_EXECUTED)
        self.assertEqual(command_changed.state, SPEC_CHECK_STATE_EXECUTED)

        # Coverage changes.
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        _run(root, coverage=("cell:a",))
        coverage_changed = _run(root, coverage=("cell:b",))
        self.assertEqual(coverage_changed.state, SPEC_CHECK_STATE_EXECUTED)

        # Governed input changes between independently begun sessions.
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        _run(root)
        _write(root / "flowguard/source.py", "VALUE = 2\n")
        begin_spec_session(root, "openspec", "change-one")
        input_changed = _run(root)
        self.assertEqual(input_changed.state, SPEC_CHECK_STATE_EXECUTED)

        # Tool identity changes even when command text does not.
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        with patch("flowguard.spec_check_cache._tool_fingerprint", return_value=({"python": "a"}, "tool:a")):
            _run(root)
        with patch("flowguard.spec_check_cache._tool_fingerprint", return_value=({"python": "b"}, "tool:b")):
            tool_changed = _run(root)
        self.assertEqual(tool_changed.state, SPEC_CHECK_STATE_EXECUTED)

    def test_dependency_failure_is_not_run_and_inner_command_never_starts(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        result = _run(root, depends_on=("check.parent",))

        self.assertEqual(result.state, SPEC_CHECK_STATE_NOT_RUN)
        self.assertEqual(result.terminal_status, SPEC_TERMINAL_NOT_RUN_DEPENDENCY)
        self.assertFalse((root / "counter.txt").exists())

    def test_failure_timeout_and_progress_receipts_are_never_reused(self) -> None:
        # A terminal failure is executed again.
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        failing = (sys.executable, "-c", "from pathlib import Path; p=Path('counter.txt'); p.write_text(str(int(p.read_text())+1) if p.exists() else '1'); raise SystemExit(7)")
        first = _run(root, command=failing)
        second = _run(root, command=failing)
        self.assertEqual(first.terminal_status, SPEC_TERMINAL_FAIL)
        self.assertEqual(second.terminal_status, SPEC_TERMINAL_FAIL)
        self.assertEqual((root / "counter.txt").read_text(), "2")

        # A timeout is executed again rather than reused.
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        timeout_error = _ProcessTreeTimeout(
            cmd=(sys.executable, "-c", "pass"),
            timeout=1,
            cleanup_confirmed=True,
        )
        with patch("flowguard.spec_check_cache._run_command_tree", side_effect=timeout_error) as mocked:
            first = _run(root)
            second = _run(root)
        self.assertEqual(first.terminal_status, SPEC_TERMINAL_TIMEOUT)
        self.assertEqual(second.terminal_status, SPEC_TERMINAL_TIMEOUT)
        self.assertEqual(mocked.call_count, 2)

        # A stored progress-only receipt cannot be consumed as completion.
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        _run(root)
        receipt_path = next((root / ".flowguard/evidence/spec-work-packages/receipts").glob("*.json"))
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        payload["result_status"] = RECEIPT_STATUS_PROGRESS_ONLY
        receipt_path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
        rerun = _run(root)
        self.assertEqual(rerun.state, SPEC_CHECK_STATE_EXECUTED)
        self.assertEqual((root / "counter.txt").read_text(), "2")

    def test_identical_concurrent_execution_is_locked(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        entered = threading.Event()
        release = threading.Event()

        def slow_run(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(timeout=3))
            return subprocess.CompletedProcess(args=args[0], returncode=0, stdout=b"", stderr=b"")

        with patch("flowguard.spec_check_cache._run_command_tree", side_effect=slow_run), patch(
            "flowguard.spec_check_cache._pid_alive", return_value=True
        ):
            with ThreadPoolExecutor(max_workers=1) as executor:
                first_future = executor.submit(_run, root)
                self.assertTrue(entered.wait(timeout=3))
                second = _run(root)
                release.set()
                first = first_future.result(timeout=3)

        self.assertEqual(first.state, SPEC_CHECK_STATE_EXECUTED)
        self.assertEqual(second.state, SPEC_CHECK_STATE_BLOCKED)
        self.assertIn("identical spec check is already executing", second.blockers)

    def test_input_mutation_during_check_blocks_receipt(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        command = (
            sys.executable,
            "-c",
            "from pathlib import Path; Path('flowguard/source.py').write_text('VALUE = 99\\n')",
        )
        result = _run(root, command=command)

        self.assertEqual(result.state, SPEC_CHECK_STATE_BLOCKED)
        self.assertEqual(result.terminal_status, SPEC_TERMINAL_BLOCKED)
        self.assertIn("check_input_changed_during_run", result.blockers)

    def test_timeout_terminates_descendant_process_tree(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        child = (
            "import time; from pathlib import Path; "
            "time.sleep(1); Path('descendant-survived.txt').write_text('bad')"
        )
        parent = (
            "import subprocess,sys,time; "
            f"subprocess.Popen([sys.executable,'-c',{child!r}]); time.sleep(5)"
        )

        result = _run(
            root,
            command=(sys.executable, "-c", parent),
            timeout_seconds=0.2,
        )
        import time

        time.sleep(1.3)
        self.assertEqual(SPEC_TERMINAL_TIMEOUT, result.terminal_status)
        self.assertFalse((root / "descendant-survived.txt").exists())

    def test_unconfirmed_process_cleanup_blocks_and_cannot_reuse(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        timeout = _ProcessTreeTimeout(
            cmd=(sys.executable, "-c", "pass"),
            timeout=1,
            cleanup_confirmed=False,
        )
        with patch("flowguard.spec_check_cache._run_command_tree", side_effect=timeout) as mocked:
            first = _run(root)
            second = _run(root)

        self.assertEqual(SPEC_TERMINAL_BLOCKED, first.terminal_status)
        self.assertEqual(SPEC_TERMINAL_BLOCKED, second.terminal_status)
        self.assertIn("process_tree_cleanup_unconfirmed", first.blockers)
        self.assertEqual(2, mocked.call_count)

    def test_abandoned_execution_lock_is_recovered_with_visible_evidence(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        failing = (sys.executable, "-c", "raise SystemExit(3)")
        first = _run(root, command=failing)
        lock = root / ".flowguard/evidence/spec-work-packages/locks" / f"{first.execution_key.removeprefix('sha256:')}.lock"
        _write(lock, json.dumps({"pid": -1, "started_at": "old"}) + "\n")
        old = 1
        os.utime(lock, (old, old))

        recovered = _run(root, command=failing)

        receipts = list_evidence_receipts(
            root,
            output_directory=root / ".flowguard/evidence/spec-work-packages/receipts",
        )
        matching = next(item for item in reversed(receipts) if item.receipt_id == recovered.receipt_id)
        self.assertTrue(dict(matching.metadata).get("recovered_abandoned_lock"))

    def test_confirmed_dead_execution_lock_is_recovered_without_age_delay(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        failing = (sys.executable, "-c", "raise SystemExit(3)")
        first = _run(root, command=failing)
        lock = root / ".flowguard/evidence/spec-work-packages/locks" / f"{first.execution_key.removeprefix('sha256:')}.lock"
        _write(lock, json.dumps({"pid": 999999, "started_at": "current"}) + "\n")

        with patch("flowguard.spec_check_cache._pid_alive", return_value=False):
            recovered = _run(root, command=failing)

        receipts = list_evidence_receipts(
            root,
            output_directory=root / ".flowguard/evidence/spec-work-packages/receipts",
        )
        matching = next(item for item in reversed(receipts) if item.receipt_id == recovered.receipt_id)
        self.assertTrue(dict(matching.metadata).get("recovered_abandoned_lock"))

    def test_proof_projection_binds_exact_execution_session(self) -> None:
        temporary = _project()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        begin_spec_session(root, "openspec", "change-one")
        result = _run(root)
        receipts = list_evidence_receipts(
            root,
            output_directory=root / ".flowguard/evidence/spec-work-packages/receipts",
        )
        receipt = next(item for item in receipts if item.receipt_id == result.receipt_id)
        proof = spec_receipt_to_proof_artifact(receipt)
        self.assertEqual(result.session_id, proof.metadata["session_id"])
        self.assertTrue(proof.artifact_fingerprints["session_begin"])
        self.assertEqual(
            proof.artifact_fingerprints["session_begin"],
            proof.artifact_fingerprints["session_post"],
        )


if __name__ == "__main__":
    unittest.main()

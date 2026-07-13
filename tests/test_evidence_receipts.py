import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

from flowguard.evidence_receipts import (
    ChildReceiptRequirement,
    ConsumedChildReceipt,
    EvidenceReceipt,
    INPUT_HASH_BOTH,
    INPUT_HASH_RAW,
    INPUT_HASH_SEMANTIC,
    RECEIPT_STATUS_PASS,
    ReceiptValidationError,
    ReceiptVerificationContext,
    build_environment_fingerprint,
    canonical_receipt_json,
    fingerprint_value,
    import_legacy_report,
    load_evidence_receipt,
    receipt_fingerprint,
    save_evidence_receipt,
    snapshot_bytes,
    tokenize_command,
    tokenize_path,
    verify_evidence_receipt,
)


def digest(label):
    return fingerprint_value({"label": label})


def environment(label="default"):
    return build_environment_fingerprint(
        {
            "python_implementation": "CPython",
            "python_version": "3.12.10",
            "platform_system": "Windows",
            "platform_machine": f"AMD64-{label}",
            "flowguard_version": "0.54.0",
        }
    )


def receipt(
    receipt_id="receipt:skillguard:1",
    *,
    subject_id="skillguard",
    snapshot=None,
    environment_value=None,
    required_children=(),
    consumed_children=(),
    supersedes=(),
    claim_scope="full",
    covered=("req.skillguard.deep",),
    **updates,
):
    snapshot = snapshot or snapshot_bytes(
        "skill-source",
        b"alpha\n",
        path_token="<WORKSPACE>/.agents/skills/skillguard/SKILL.md",
        hash_policy=INPUT_HASH_BOTH,
        obligation_ids=covered,
    )
    environment_value = environment_value or environment()
    values = {
        "receipt_id": receipt_id,
        "subject_id": subject_id,
        "subject_kind": "skill_check",
        "producer_id": "flowguard.skillguard",
        "producer_version": "0.54.0",
        "claim_scope": claim_scope,
        "command": ("python", "scripts/check_flowguard_skill_suite.py", "--json"),
        "working_directory_token": "<WORKSPACE>",
        "started_at": "2026-07-10T08:00:00+00:00",
        "finished_at": "2026-07-10T08:00:01+00:00",
        "exit_code": 0,
        "environment_fingerprint": environment_value.fingerprint,
        "environment_metadata": environment_value.metadata,
        "contract_hash": digest("contract"),
        "check_manifest_hash": digest("check-manifest"),
        "suite_map_hash": digest("suite-map"),
        "input_snapshots": (snapshot,),
        "proof_artifact_id": "proof:skillguard:1",
        "proof_artifact_fingerprint": digest("proof"),
        "result_status": RECEIPT_STATUS_PASS,
        "result_fingerprint": digest("result"),
        "covered_obligations": tuple(covered),
        "required_child_receipts": tuple(required_children),
        "consumed_child_receipts": tuple(consumed_children),
        "supersedes_receipt_ids": tuple(supersedes),
        "claim_boundary": "Only the named skill contract obligations in this repository run.",
    }
    values.update(updates)
    return EvidenceReceipt(**values)


def current_context(value, **updates):
    values = {
        "input_snapshots": {item.artifact_id: item for item in value.input_snapshots},
        "contract_hash": value.contract_hash,
        "check_manifest_hash": value.check_manifest_hash,
        "suite_map_hash": value.suite_map_hash,
        "producer_id": value.producer_id,
        "producer_version": value.producer_version,
        "environment_fingerprint": value.environment_fingerprint,
        "proof_artifact_fingerprint": value.proof_artifact_fingerprint,
        "result_fingerprint": value.result_fingerprint,
        "command": value.command,
        "working_directory_token": value.working_directory_token,
        "proof_artifact_id": value.proof_artifact_id,
        "required_obligation_ids": value.covered_obligations,
        "eligible_claim_scopes": ("full",),
    }
    values.update(updates)
    return ReceiptVerificationContext(**values)


class EvidenceReceiptSchemaTests(unittest.TestCase):
    def test_canonical_serialization_round_trip_and_fingerprint_are_deterministic(self):
        value = receipt(metadata={"z": [2, 1], "a": {"x": True}})

        first = canonical_receipt_json(value)
        second = canonical_receipt_json(EvidenceReceipt.from_dict(json.loads(first)))

        self.assertEqual(first, second)
        self.assertEqual(receipt_fingerprint(value), receipt_fingerprint(EvidenceReceipt.from_dict(json.loads(first))))
        self.assertNotIn("current", value.to_dict())
        with self.assertRaises(TypeError):
            value.metadata["new"] = "forbidden"

    def test_required_identity_and_coverage_are_hard_schema_gates(self):
        data = receipt().to_dict()
        data["subject_id"] = ""
        with self.assertRaisesRegex(ReceiptValidationError, "subject_id"):
            EvidenceReceipt.from_dict(data)

        data = receipt().to_dict()
        data["covered_obligations"] = []
        with self.assertRaisesRegex(ReceiptValidationError, "covered_obligations"):
            EvidenceReceipt.from_dict(data)

    def test_authoritative_current_is_rejected_even_if_true(self):
        data = receipt().to_dict()
        data["current"] = True

        with self.assertRaisesRegex(ReceiptValidationError, "current"):
            EvidenceReceipt.from_dict(data)

        data["contract_hash"] = digest("forged-contract")
        result = verify_evidence_receipt(data, current_context(receipt()))
        self.assertFalse(result.current)
        self.assertFalse(result.eligible)
        self.assertEqual("invalid", result.status)

    def test_paths_and_commands_are_tokenized_without_home_leakage(self):
        private_root = Path.home() / "secret-workspace"
        private_file = private_root / "skills" / "SKILL.md"

        path_token = tokenize_path(private_file, workspace_root=private_root)
        command = tokenize_command(
            ("python", str(private_root / "scripts" / "check.py"), "--root", str(private_root)),
            workspace_root=private_root,
        )
        serialized = json.dumps({"path": path_token, "command": command})

        self.assertEqual("<WORKSPACE>/skills/SKILL.md", path_token)
        self.assertEqual("<WORKSPACE>/scripts/check.py", command[1])
        self.assertNotIn(str(Path.home()), serialized)
        self.assertNotIn(Path.home().name, serialized)

    def test_environment_rejects_non_allowlisted_machine_identity(self):
        with self.assertRaisesRegex(ReceiptValidationError, "unsafe environment"):
            build_environment_fingerprint({"hostname": "private-host"})

        with self.assertRaisesRegex(ReceiptValidationError, "absolute path"):
            receipt(metadata={"raw_log_path": str(Path.home() / "private.log")})

    def test_relative_glob_metadata_is_not_mistaken_for_an_absolute_path(self):
        value = receipt(
            metadata={
                "input_paths": [
                    "flowguard/**/*.py",
                    ".flowguard/**/model.py",
                    "tests/test_*.py",
                ]
            }
        )

        self.assertEqual("flowguard/**/*.py", value.metadata["input_paths"][0])
        with self.assertRaisesRegex(ReceiptValidationError, "absolute path"):
            receipt(metadata={"input_paths": ["/private/**/*.py"]})

    def test_default_storage_round_trip_is_repository_local_and_private_path_free(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            value = receipt()
            path = save_evidence_receipt(value, root)
            payload = path.read_text(encoding="utf-8")

            self.assertEqual(root / ".flowguard/evidence/skill-suite", path.parent)
            self.assertEqual(value, load_evidence_receipt(path))
            self.assertNotIn(str(Path.home()), payload)
            self.assertNotIn("\"current\"", payload)

            with self.assertRaisesRegex(ReceiptValidationError, "skill package"):
                save_evidence_receipt(value, root, output_directory=root / ".agents/skills/demo/evidence")

    def test_legacy_report_is_diagnostic_only_and_covers_nothing(self):
        legacy = import_legacy_report({"status": "pass", "current": True, "path": str(Path.home())})

        self.assertFalse(legacy.current)
        self.assertFalse(legacy.eligible)
        self.assertEqual("unbound_historical_evidence", legacy.classification)
        self.assertEqual((), legacy.covered_obligations)
        self.assertNotIn(str(Path.home()), json.dumps(legacy.to_dict()))


class ReceiptFreshnessTests(unittest.TestCase):
    def test_exact_current_receipt_is_eligible_pass(self):
        value = receipt()
        result = verify_evidence_receipt(value, current_context(value))

        self.assertTrue(result.current)
        self.assertTrue(result.eligible)
        self.assertEqual("pass", result.status)
        self.assertEqual((), result.finding_codes)
        self.assertEqual(value.covered_obligations, result.satisfied_obligations)

    def test_missing_context_never_defaults_to_current(self):
        result = verify_evidence_receipt(receipt(), None)

        self.assertFalse(result.current)
        self.assertFalse(result.eligible)
        self.assertEqual("stale", result.status)
        self.assertIn("verification_context_missing", result.finding_codes)

    def test_partial_scoped_and_gap_statuses_remain_visible_and_never_eligible(self):
        for status in ("pass_with_gaps", "scoped", "stale", "skipped", "not_run", "progress_only", "blocked"):
            with self.subTest(status=status):
                value = receipt(result_status=status)
                result = verify_evidence_receipt(value, current_context(value))
                self.assertTrue(result.current, result.to_dict())
                self.assertFalse(result.eligible)
                self.assertEqual(status, result.status)
                self.assertEqual((), result.satisfied_obligations)

    def test_each_bound_fingerprint_change_invalidates_current(self):
        value = receipt()
        mutations = {
            "contract_hash": digest("changed-contract"),
            "check_manifest_hash": digest("changed-check"),
            "suite_map_hash": digest("changed-suite"),
            "producer_id": "another.producer",
            "producer_version": "99.0.0",
            "environment_fingerprint": environment("changed").fingerprint,
            "proof_artifact_fingerprint": digest("changed-proof"),
            "result_fingerprint": digest("changed-result"),
            "command": ("python", "changed-check.py"),
            "working_directory_token": "<WORKSPACE>/other",
            "proof_artifact_id": "proof:changed",
        }
        for field_name, changed in mutations.items():
            with self.subTest(field_name=field_name):
                result = verify_evidence_receipt(value, current_context(value, **{field_name: changed}))
                self.assertFalse(result.current, result.to_dict())
                self.assertFalse(result.eligible)
                expected_code = "command_mismatch" if field_name == "command" else f"{field_name}_mismatch"
                self.assertIn(expected_code, result.finding_codes)
                self.assertIn(f"rerun-producer:{value.subject_id}", result.minimum_revalidation)

    def test_raw_semantic_and_both_hash_policies_are_not_interchangeable(self):
        cases = (
            (INPUT_HASH_RAW, False),
            (INPUT_HASH_SEMANTIC, True),
            (INPUT_HASH_BOTH, False),
        )
        for policy, expected_current in cases:
            with self.subTest(policy=policy):
                before = snapshot_bytes(
                    "prompt",
                    b"line one\r\nline two\r\n",
                    path_token="<WORKSPACE>/prompt.md",
                    hash_policy=policy,
                    obligation_ids=("req.prompt",),
                )
                after = snapshot_bytes(
                    "prompt",
                    b"line one\nline two\n",
                    path_token="<WORKSPACE>/prompt.md",
                    hash_policy=policy,
                    obligation_ids=("req.prompt",),
                )
                value = receipt(snapshot=before, covered=("req.prompt",))
                result = verify_evidence_receipt(
                    value,
                    current_context(value, input_snapshots={"prompt": after}),
                )
                self.assertEqual(expected_current, result.current, result.to_dict())
                if policy in {INPUT_HASH_RAW, INPUT_HASH_BOTH}:
                    self.assertIn("input_raw_hash_mismatch", result.finding_codes)
                    raw_finding = next(item for item in result.findings if item.code == "input_raw_hash_mismatch")
                    self.assertTrue(raw_finding.details["semantic_equal"])

    def test_input_path_or_obligation_binding_change_is_stale_even_with_same_bytes(self):
        before = snapshot_bytes(
            "prompt",
            b"same\n",
            path_token="<WORKSPACE>/source/prompt.md",
            obligation_ids=("req.prompt",),
        )
        moved = snapshot_bytes(
            "prompt",
            b"same\n",
            path_token="<WORKSPACE>/installed/prompt.md",
            obligation_ids=("req.prompt.other",),
        )
        value = receipt(snapshot=before, covered=("req.prompt",))

        result = verify_evidence_receipt(value, current_context(value, input_snapshots={"prompt": moved}))

        self.assertFalse(result.current)
        self.assertIn("input_path_token_mismatch", result.finding_codes)
        self.assertIn("input_obligation_scope_mismatch", result.finding_codes)


class ParentChildReceiptTests(unittest.TestCase):
    def _child_and_result(self, *, receipt_id="receipt:child:1", supersedes=(), claim_scope="full", covered=("req.child",)):
        child = receipt(
            receipt_id,
            subject_id="child-subject",
            claim_scope=claim_scope,
            covered=covered,
            supersedes=supersedes,
        )
        child_result = verify_evidence_receipt(child, current_context(child))
        self.assertTrue(child_result.eligible, child_result.to_dict())
        return child, child_result

    def _parent(self, child, *, consumed=True, obligation="req.child", scopes=("full",), expected_fingerprint=True):
        requirement = ChildReceiptRequirement(
            receipt_id=child.receipt_id,
            subject_id=child.subject_id,
            obligation_ids=(obligation,),
            eligible_claim_scopes=scopes,
            expected_receipt_fingerprint=child.fingerprint if expected_fingerprint else "",
        )
        links = (ConsumedChildReceipt(child.receipt_id, child.fingerprint),) if consumed else ()
        return receipt(
            "receipt:parent:1",
            subject_id="parent",
            required_children=(requirement,),
            consumed_children=links,
            covered=("req.parent",),
        )

    def _verify_parent(self, parent, child=None, child_result=None, **context_updates):
        children = {} if child is None else {child.receipt_id: child}
        results = {} if child_result is None else {child_result.receipt_id: child_result}
        return verify_evidence_receipt(
            parent,
            current_context(
                parent,
                child_receipts=children,
                child_verification_results=results,
                **context_updates,
            ),
        )

    def test_exact_required_current_consumed_child_satisfies_parent(self):
        child, child_result = self._child_and_result()
        parent = self._parent(child)

        result = self._verify_parent(parent, child, child_result)

        self.assertTrue(result.eligible, result.to_dict())
        self.assertIn("req.child", result.satisfied_obligations)

    def test_present_but_unconsumed_child_blocks_parent(self):
        child, child_result = self._child_and_result()
        parent = self._parent(child, consumed=False)

        result = self._verify_parent(parent, child, child_result)

        self.assertFalse(result.current)
        self.assertIn("required_child_not_consumed", result.finding_codes)
        self.assertIn("reconsume-children:parent", result.minimum_revalidation)

    def test_missing_child_and_missing_child_verification_are_visible(self):
        child, _ = self._child_and_result()
        parent = self._parent(child)
        missing = self._verify_parent(parent)
        unverified = self._verify_parent(parent, child)

        self.assertIn("required_child_receipt_missing", missing.finding_codes)
        self.assertIn("child_verification_result_missing", unverified.finding_codes)
        self.assertFalse(missing.eligible)
        self.assertFalse(unverified.eligible)

    def test_wrong_child_obligation_or_scope_cannot_be_promoted(self):
        child, child_result = self._child_and_result()
        for parent in (
            self._parent(child, obligation="req.child.missing"),
            self._parent(child, scopes=("diagnostic",)),
        ):
            with self.subTest(requirement=parent.required_child_receipts[0].to_dict()):
                result = self._verify_parent(parent, child, child_result)
                self.assertFalse(result.eligible)
                self.assertTrue(
                    {"child_obligation_missing", "child_claim_scope_ineligible"} & set(result.finding_codes),
                    result.to_dict(),
                )

    def test_superseded_child_invalidates_parent_until_new_id_is_consumed(self):
        old_child, old_result = self._child_and_result(receipt_id="receipt:child:1")
        new_child, _ = self._child_and_result(receipt_id="receipt:child:2", supersedes=(old_child.receipt_id,))
        parent = self._parent(old_child)

        result = verify_evidence_receipt(
            parent,
            current_context(
                parent,
                child_receipts={old_child.receipt_id: old_child, new_child.receipt_id: new_child},
                child_verification_results={old_child.receipt_id: old_result},
                latest_child_receipt_ids={old_child.subject_id: new_child.receipt_id},
            ),
        )

        self.assertFalse(result.current)
        self.assertIn("superseded_child_receipt", result.finding_codes)
        self.assertIn("rerun-parent:parent", result.minimum_revalidation)

    def test_stale_or_fingerprint_mismatched_child_cannot_support_parent(self):
        child, _ = self._child_and_result()
        stale_child_result = verify_evidence_receipt(
            child,
            current_context(child, contract_hash=digest("changed-child-contract")),
        )
        self.assertFalse(stale_child_result.current)
        parent = self._parent(child)
        stale_parent = self._verify_parent(parent, child, stale_child_result)

        bad_link_parent = dataclasses.replace(
            parent,
            consumed_child_receipts=(ConsumedChildReceipt(child.receipt_id, digest("wrong-child")),),
        )
        wrong_fingerprint = self._verify_parent(
            bad_link_parent,
            child,
            verify_evidence_receipt(child, current_context(child)),
        )

        self.assertIn("child_receipt_not_current_pass", stale_parent.finding_codes)
        self.assertFalse(stale_parent.eligible)
        self.assertIn("consumed_child_fingerprint_mismatch", wrong_fingerprint.finding_codes)
        self.assertFalse(wrong_fingerprint.eligible)


if __name__ == "__main__":
    unittest.main()

import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

from flowguard.evidence_receipts import (
    EvidenceReceipt,
    ReceiptVerificationContext,
    build_environment_fingerprint,
    fingerprint_value,
    list_evidence_receipts,
    save_evidence_receipt,
    snapshot_bytes,
    verify_evidence_receipt,
)
from flowguard.self_maintenance import SelfMaintenanceChildReport
from flowguard.skill_self_governance import (
    LAYER_ENGINE_AND_CORE,
    LAYER_FULL_SELF_GOVERNANCE,
    LAYER_SKILL_CONTRACTS,
    SELF_GOVERNANCE_SUBJECT,
    load_governance_requirements,
    run_skill_self_governance,
    skill_contract_obligation_id,
)


ROOT = Path(__file__).resolve().parents[1]


def digest(label):
    return fingerprint_value({"label": label})


def environment():
    return build_environment_fingerprint(
        {
            "python_implementation": "CPython",
            "python_version": "3.12.10",
            "platform_system": "Windows",
            "platform_machine": "AMD64-test",
            "flowguard_version": "0.54.0",
        }
    )


def child_receipt(subject_id, index, *, status="pass", claim_scope="full"):
    obligation = skill_contract_obligation_id(subject_id)
    snapshot = snapshot_bytes(
        f"source:{subject_id}",
        f"source-{subject_id}".encode(),
        path_token=f"<WORKSPACE>/.agents/skills/{subject_id}/SKILL.md",
        obligation_ids=(obligation,),
    )
    env = environment()
    return EvidenceReceipt(
        receipt_id=f"receipt:{subject_id}:{index}",
        subject_id=subject_id,
        subject_kind="skill_deep_contract",
        producer_id="flowguard.skill_contracts",
        producer_version="0.54.0",
        claim_scope=claim_scope,
        command=("python", "scripts/check_flowguard_skill_suite.py", "--skill", subject_id),
        working_directory_token="<WORKSPACE>",
        started_at=f"2026-07-10T08:{index:02d}:00+00:00",
        finished_at=f"2026-07-10T08:{index:02d}:01+00:00",
        exit_code=0,
        environment_fingerprint=env.fingerprint,
        environment_metadata=env.metadata,
        contract_hash=digest(f"contract:{subject_id}"),
        check_manifest_hash=digest(f"checks:{subject_id}"),
        suite_map_hash=digest("suite"),
        input_snapshots=(snapshot,),
        proof_artifact_id=f"proof:{subject_id}",
        proof_artifact_fingerprint=digest(f"proof:{subject_id}"),
        result_status=status,
        result_fingerprint=digest(f"result:{subject_id}:{status}"),
        covered_obligations=(obligation,),
        claim_boundary="Only this skill's current deep contract.",
    )


def current_context(receipt, *, contract_hash=None):
    return ReceiptVerificationContext(
        input_snapshots={item.artifact_id: item for item in receipt.input_snapshots},
        contract_hash=contract_hash or receipt.contract_hash,
        check_manifest_hash=receipt.check_manifest_hash,
        suite_map_hash=receipt.suite_map_hash,
        producer_id=receipt.producer_id,
        producer_version=receipt.producer_version,
        environment_fingerprint=receipt.environment_fingerprint,
        proof_artifact_fingerprint=receipt.proof_artifact_fingerprint,
        result_fingerprint=receipt.result_fingerprint,
        command=receipt.command,
        working_directory_token=receipt.working_directory_token,
        proof_artifact_id=receipt.proof_artifact_id,
        required_obligation_ids=receipt.covered_obligations,
        eligible_claim_scopes=("full",),
    )


def full_children():
    requirements = load_governance_requirements(ROOT)
    receipts = tuple(child_receipt(item.subject_id, index) for index, item in enumerate(requirements))
    contexts = {item.receipt_id: current_context(item) for item in receipts}
    return requirements, receipts, contexts


class SkillSelfGovernanceTests(unittest.TestCase):
    def test_canonical_inventory_has_exact_fifteen_receipt_requirements(self):
        requirements = load_governance_requirements(ROOT)

        self.assertEqual(15, len(requirements))
        self.assertEqual(15, len({item.subject_id for item in requirements}))
        self.assertTrue(all(item.obligation_id.endswith(".deep") for item in requirements))

    def test_exact_current_eligible_children_emit_bound_parent_receipt(self):
        requirements, receipts, contexts = full_children()

        report = run_skill_self_governance(
            ROOT,
            receipts=receipts,
            verification_contexts=contexts,
            save_parent_receipt=False,
        )

        self.assertTrue(report.ok, report.to_json_text())
        self.assertEqual("pass", report.status)
        self.assertEqual(15, len(report.child_reports))
        self.assertTrue(all(item.is_current_pass() for item in report.child_reports))
        self.assertTrue(report.self_governance_receipt_hash.startswith("sha256:"))
        parent = report.self_governance_receipt
        self.assertIsNotNone(parent)
        self.assertEqual(15, len(parent.required_child_receipts))
        self.assertEqual(15, len(parent.consumed_child_receipts))
        self.assertEqual(
            {item.receipt_id for item in receipts},
            {item.receipt_id for item in parent.consumed_child_receipts},
        )
        self.assertTrue(report.minimum_revalidation == ())
        self.assertTrue(all(hasattr(item, "target_kind") for item in report.typed_downstream))
        self.assertEqual(
            {item.obligation_id for item in requirements},
            {item.obligation_ids[0] for item in parent.required_child_receipts},
        )
        parent_context = ReceiptVerificationContext(
            input_snapshots={item.artifact_id: item for item in parent.input_snapshots},
            contract_hash=parent.contract_hash,
            check_manifest_hash=parent.check_manifest_hash,
            suite_map_hash=parent.suite_map_hash,
            producer_id=parent.producer_id,
            producer_version=parent.producer_version,
            environment_fingerprint=parent.environment_fingerprint,
            proof_artifact_fingerprint=parent.proof_artifact_fingerprint,
            result_fingerprint=parent.result_fingerprint,
            command=parent.command,
            working_directory_token=parent.working_directory_token,
            proof_artifact_id=parent.proof_artifact_id,
            required_obligation_ids=parent.covered_obligations,
            eligible_claim_scopes=("full",),
            child_receipts={item.receipt_id: item for item in receipts},
            child_verification_results={item.receipt_id: item for item in report.child_verification_results},
            latest_child_receipt_ids={item.subject_id: item.receipt_id for item in receipts},
        )
        self.assertTrue(verify_evidence_receipt(parent, parent_context).ok)

    def test_missing_child_blocks_full_and_names_minimum_revalidation(self):
        requirements, receipts, contexts = full_children()
        missing = requirements[5]
        receipts = tuple(item for item in receipts if item.subject_id != missing.subject_id)

        report = run_skill_self_governance(
            ROOT,
            receipts=receipts,
            verification_contexts=contexts,
            save_parent_receipt=False,
        )

        self.assertFalse(report.ok)
        self.assertIn(f"missing_child_receipt:{missing.subject_id}", report.blockers)
        self.assertIn(f"run-child:{missing.subject_id}", report.minimum_revalidation)
        self.assertIsNone(report.self_governance_receipt)

    def test_stale_and_partial_statuses_cannot_be_promoted_to_full(self):
        _, receipts, contexts = full_children()
        target = receipts[7]
        stale_contexts = dict(contexts)
        stale_contexts[target.receipt_id] = current_context(target, contract_hash=digest("changed"))

        stale = run_skill_self_governance(
            ROOT,
            receipts=receipts,
            verification_contexts=stale_contexts,
            save_parent_receipt=False,
        )
        self.assertFalse(stale.ok)
        stale_child = next(item for item in stale.child_reports if item.child_id == target.subject_id)
        self.assertFalse(stale_child.current)

        for status in ("pass_with_gaps", "scoped", "stale", "skipped", "not_run", "progress_only", "blocked"):
            with self.subTest(status=status):
                partial_receipt = dataclasses.replace(target, result_status=status)
                changed = tuple(partial_receipt if item.receipt_id == target.receipt_id else item for item in receipts)
                changed_contexts = dict(contexts)
                changed_contexts[target.receipt_id] = current_context(partial_receipt)
                report = run_skill_self_governance(
                    ROOT,
                    receipts=changed,
                    verification_contexts=changed_contexts,
                    save_parent_receipt=False,
                )
                self.assertFalse(report.ok, status)
                self.assertIsNone(report.self_governance_receipt)

    def test_three_layer_matrix_keeps_engine_green_contract_failure_and_full_block_separate(self):
        _, receipts, contexts = full_children()
        target = next(item for item in receipts if item.subject_id != "flowguard")
        broken_contexts = dict(contexts)
        broken_contexts[target.receipt_id] = current_context(target, contract_hash=digest("changed-contract"))

        report = run_skill_self_governance(
            ROOT,
            receipts=receipts,
            verification_contexts=broken_contexts,
            save_parent_receipt=False,
        )
        layers = {item.layer_id: item for item in report.layers}

        self.assertEqual("pass", layers[LAYER_ENGINE_AND_CORE].status)
        self.assertEqual("fail", layers[LAYER_SKILL_CONTRACTS].status)
        self.assertEqual("blocked", layers[LAYER_FULL_SELF_GOVERNANCE].status)

    def test_manufactured_or_legacy_child_report_is_unbound(self):
        manufactured = SelfMaintenanceChildReport(
            "fake",
            "fake-owner",
            "skill_contract",
            verification_status="pass",
            verification_current=True,
            verification_eligible=True,
        )
        legacy = SelfMaintenanceChildReport.from_dict(
            {
                "child_id": "legacy",
                "owner_guard": "legacy-owner",
                "artifact_kind": "skill_contract",
                "closure_status": "pass",
                "current": True,
            }
        )

        self.assertFalse(manufactured.is_current_pass())
        self.assertFalse(legacy.is_current_pass())
        self.assertEqual("blocked", legacy.closure_status)
        self.assertTrue(legacy.metadata["legacy_authority_rejected"])

    def test_omitted_inventory_member_is_not_silently_accepted(self):
        data = json.loads((ROOT / ".skillguard/flowguard-suite/suite-map.json").read_text(encoding="utf-8"))
        data["included_skills"] = data["included_skills"][:-1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "suite-map.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exactly 15"):
                load_governance_requirements(root, suite_map_path=path)

    def test_default_storage_loads_children_and_saves_parent_outside_skill_packages(self):
        _, receipts, contexts = full_children()
        suite_map_text = (ROOT / ".skillguard/flowguard-suite/suite-map.json").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".skillguard/flowguard-suite").mkdir(parents=True)
            (root / ".skillguard/flowguard-suite/suite-map.json").write_text(suite_map_text, encoding="utf-8")
            (root / "flowguard").mkdir()
            (root / "flowguard/skill_self_governance.py").write_text("# parent source\n", encoding="utf-8")
            for receipt in receipts:
                save_evidence_receipt(receipt, root)

            report = run_skill_self_governance(root, verification_contexts=contexts)
            stored = list_evidence_receipts(root)

            self.assertTrue(report.ok, report.to_json_text())
            self.assertIn(SELF_GOVERNANCE_SUBJECT, {item.subject_id for item in stored})
            self.assertEqual(16, len(stored))
            self.assertTrue((root / ".flowguard/evidence/skill-suite").is_dir())


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest

from flowguard.contract_exhaustion import (
    CONTRACT_ORACLE_PASS_ALLOWED,
    ContractCoverageUniverse,
    ContractExhaustionPlan,
    ContractMutationCase,
    ModelContractCoverageReceipt,
    NativeChildEvidenceBinding,
    review_contract_exhaustion,
)
from flowguard.evidence_receipts import (
    RECEIPT_STATUS_PASS,
    EvidenceReceipt,
    ReceiptVerificationContext,
    build_environment_fingerprint,
    fingerprint_value,
    save_evidence_receipt,
    snapshot_bytes,
)


def _digest(label: str) -> str:
    return fingerprint_value({"label": label})


def _native_child(
    *,
    model_id: str = "child-model",
    owner_id: str = "owner:child",
    parent_model_id: str = "parent-model",
    subject_id: str = "validation-owner:child",
    claim_scope: str = "full",
) -> tuple[EvidenceReceipt, ReceiptVerificationContext]:
    obligation_ids = ("obligation:child",)
    snapshot = snapshot_bytes(
        "input:child",
        b"child-input\n",
        path_token="<WORKSPACE>/child-input",
        obligation_ids=obligation_ids,
    )
    environment = build_environment_fingerprint(
        {
            "python_implementation": "CPython",
            "python_version": "3.12.10",
            "platform_system": "Windows",
            "platform_machine": "AMD64",
            "flowguard_version": "0.68.16",
        }
    )
    receipt = EvidenceReceipt(
        receipt_id="evidence:child:1",
        subject_id=subject_id,
        subject_kind="validation-owner",
        producer_id="flowguard.test.native-child",
        producer_version="0.68.16",
        claim_scope=claim_scope,
        command=("python", "-m", "flowguard", "native-child"),
        working_directory_token="<WORKSPACE>",
        started_at="2026-09-02T08:00:00+00:00",
        finished_at="2026-09-02T08:00:01+00:00",
        exit_code=0,
        environment_fingerprint=environment.fingerprint,
        environment_metadata=environment.metadata,
        contract_hash=_digest("contract:child"),
        check_manifest_hash=_digest("checks:child"),
        suite_map_hash=_digest("suite:child"),
        input_snapshots=(snapshot,),
        proof_artifact_id="proof:child:1",
        proof_artifact_fingerprint=_digest("proof:child"),
        result_status=RECEIPT_STATUS_PASS,
        result_fingerprint=_digest("result:child"),
        covered_obligations=obligation_ids,
        claim_boundary="Only the native child obligations are covered.",
        metadata={
            "model_id": model_id,
            "owner_id": owner_id,
            "parent_model_id": parent_model_id,
        },
    )
    context = ReceiptVerificationContext(
        input_snapshots={snapshot.artifact_id: snapshot},
        contract_hash=receipt.contract_hash,
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
        eligible_claim_scopes=(claim_scope,),
    )
    return receipt, context


def _parent_coverage(child: EvidenceReceipt) -> ModelContractCoverageReceipt:
    return ModelContractCoverageReceipt(
        receipt_id="coverage:parent",
        model_id="parent-model",
        parent_model_id="root-model",
        claim_scope="full",
        required_child_receipt_ids=("coverage:child",),
        consumed_child_receipt_ids=("coverage:child",),
        covered_case_ids=("case:parent",),
        native_child_evidence_bindings=(
            NativeChildEvidenceBinding(
                coverage_receipt_id="coverage:child",
                evidence_receipt_id=child.receipt_id,
                model_id="child-model",
                owner_id="owner:child",
                parent_model_id="parent-model",
                subject_id=child.subject_id,
                claim_scope="full",
                obligation_ids=child.covered_obligations,
                expected_receipt_fingerprint=child.fingerprint,
            ),
        ),
    )


class NativeModelCoverageTests(unittest.TestCase):
    def _plan(self, parent, root, context):
        return ContractExhaustionPlan(
            "native-parent",
            claim_scope="full",
            model_id="parent-model",
            seed_cases=(
                ContractMutationCase(
                    "case:parent",
                    required=False,
                    expected_status=CONTRACT_ORACLE_PASS_ALLOWED,
                ),
            ),
            coverage_receipts=(parent,),
            required_coverage_receipt_ids=(parent.receipt_id,),
            coverage_universe=ContractCoverageUniverse(
                "native-universe",
                claim_scope="full",
                required_case_ids=("case:parent",),
                required_coverage_receipt_ids=(parent.receipt_id,),
                require_full_product=False,
            ),
            native_receipt_store_repository_root=root,
            native_receipt_verification_contexts={
                "evidence:child:1": context,
            },
        )

    def test_strict_parent_resolves_and_verifies_real_native_child(self):
        child, context = _native_child()
        parent = _parent_coverage(child)
        with tempfile.TemporaryDirectory() as root:
            save_evidence_receipt(child, root)
            report = review_contract_exhaustion(self._plan(parent, root, context))

        self.assertTrue(report.ok, report.format_text())
        self.assertNotIn(
            "contract_native_child_verification_failed",
            {finding.code for finding in report.findings},
        )

    def test_strict_parent_blocks_id_only_child_projection(self):
        child, context = _native_child()
        parent = _parent_coverage(child)
        parent = ModelContractCoverageReceipt(
            **{
                **parent.to_dict(),
                "native_child_evidence_bindings": [],
            }
        )
        with tempfile.TemporaryDirectory() as root:
            save_evidence_receipt(child, root)
            report = review_contract_exhaustion(self._plan(parent, root, context))

        codes = {finding.code for finding in report.findings}
        self.assertFalse(report.ok)
        self.assertIn("contract_native_child_binding_set_mismatch", codes)

    def test_strict_parent_blocks_wrong_native_identity_or_missing_context(self):
        child, _context = _native_child(parent_model_id="wrong-parent")
        parent = _parent_coverage(child)
        with tempfile.TemporaryDirectory() as root:
            save_evidence_receipt(child, root)
            report = review_contract_exhaustion(
                self._plan(parent, root, context=None)
            )

        codes = {finding.code for finding in report.findings}
        self.assertFalse(report.ok)
        self.assertIn("contract_native_child_parent_model_id_mismatch", codes)
        self.assertIn("contract_native_child_verification_context_missing", codes)


if __name__ == "__main__":
    unittest.main()

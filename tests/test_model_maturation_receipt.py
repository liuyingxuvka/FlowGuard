from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from flowguard.evidence_receipts import (
    ReceiptVerificationContext,
    fingerprint_value,
    receipt_path,
    save_evidence_receipt,
    snapshot_bytes,
)
from flowguard.model_maturation import (
    MODEL_MATURATION_CONFIDENCE_FULL,
    MODEL_MATURATION_DECISION_CLOSED_FOR_TASK,
    ModelMaturationReport,
)
from flowguard.model_maturation_receipt import (
    MODEL_MATURATION_RECEIPT_CLAIM_SCOPE,
    ModelMaturationReceiptPublication,
    ModelMaturationReceiptRef,
    ModelMaturationVerificationContext,
    VerifiedModelMaturation,
    build_model_maturation_receipt,
    verify_model_maturation_receipt,
)
from flowguard.__main__ import main


class ModelMaturationReceiptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.report = ModelMaturationReport(
            ok=True,
            plan_id="plan:receipt",
            decision=MODEL_MATURATION_DECISION_CLOSED_FOR_TASK,
            confidence=MODEL_MATURATION_CONFIDENCE_FULL,
            model_id="model:receipt",
            task_id="task:receipt",
            coverage_universe_id="demand:receipt",
            coverage_demand_fingerprint="sha256:demand",
            coverage_universe_fingerprint="sha256:coverage",
            base_model_fingerprint="sha256:base",
            candidate_model_fingerprint="sha256:candidate",
            evidence_fingerprint="sha256:evidence",
            evidence_id="evidence:maturation",
            terminal_reason=MODEL_MATURATION_DECISION_CLOSED_FOR_TASK,
            input_fingerprint="sha256:input",
        )
        self.snapshot = snapshot_bytes(
            "artifact:model",
            b"model",
            path_token="<WORKSPACE>/model.py",
            obligation_ids=("obligation:model-maturation",),
        )
        self.environment = {"python_version": "test"}
        self.publication = ModelMaturationReceiptPublication(
            producer_id="flowguard.model_maturation",
            producer_version="test",
            command=("python", "model.py"),
            started_at="2026-08-02T00:00:00+00:00",
            finished_at="2026-08-02T00:00:01+00:00",
            environment_metadata=self.environment,
            contract_hash="sha256:contract",
            check_manifest_hash="sha256:manifest",
            suite_map_hash="sha256:suite",
            input_snapshots=(self.snapshot,),
            covered_obligation_ids=("obligation:model-maturation",),
        )

    def _contexts(self, output: Path, **overrides):
        receipt_context = ReceiptVerificationContext(
            input_snapshots={self.snapshot.artifact_id: self.snapshot},
            contract_hash=self.publication.contract_hash,
            check_manifest_hash=self.publication.check_manifest_hash,
            suite_map_hash=self.publication.suite_map_hash,
            producer_id=self.publication.producer_id,
            producer_version=self.publication.producer_version,
            environment_fingerprint=fingerprint_value(self.environment),
            proof_artifact_fingerprint=self.report.evidence_fingerprint,
            result_fingerprint=fingerprint_value(self.report.to_dict()),
            command=self.publication.command,
            working_directory_token=self.publication.working_directory_token,
            proof_artifact_id=self.report.evidence_id,
            required_obligation_ids=self.publication.covered_obligation_ids,
            eligible_claim_scopes=(MODEL_MATURATION_RECEIPT_CLAIM_SCOPE,),
            receipt_store_output_directory=str(output),
        )
        values = {
            "receipt_context": receipt_context,
            "task_id": self.report.task_id,
            "model_id": self.report.model_id,
            "candidate_model_fingerprint": self.report.candidate_model_fingerprint,
            "coverage_demand_fingerprint": self.report.coverage_demand_fingerprint,
            "coverage_universe_id": self.report.coverage_universe_id,
            "coverage_universe_fingerprint": self.report.coverage_universe_fingerprint,
            "input_fingerprint": self.report.input_fingerprint,
            "evidence_fingerprint": self.report.evidence_fingerprint,
        }
        values.update(overrides)
        return ModelMaturationVerificationContext(**values)

    def test_verified_projection_requires_canonical_receipt(self) -> None:
        with self.assertRaises(TypeError):
            VerifiedModelMaturation()  # type: ignore[call-arg]
        with TemporaryDirectory() as directory:
            output = Path(directory)
            receipt = build_model_maturation_receipt(self.report, self.publication)
            save_evidence_receipt(receipt, output_directory=output)
            result = verify_model_maturation_receipt(
                ModelMaturationReceiptRef(receipt.receipt_id, receipt.fingerprint),
                self._contexts(output, required_receipt_fingerprint=receipt.fingerprint),
                output_directory=output,
            )
        self.assertTrue(result.ok)
        self.assertTrue(result.verified_maturation.supports_full_confidence())

    def test_foreign_task_and_demand_are_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory)
            receipt = build_model_maturation_receipt(self.report, self.publication)
            save_evidence_receipt(receipt, output_directory=output)
            result = verify_model_maturation_receipt(
                ModelMaturationReceiptRef(receipt.receipt_id, receipt.fingerprint),
                self._contexts(
                    output,
                    task_id="task:other",
                    coverage_demand_fingerprint="sha256:other-demand",
                ),
                output_directory=output,
            )
        self.assertIsNone(result.verified_maturation)
        self.assertIn("maturation_receipt_subject_mismatch", result.semantic_finding_codes)
        self.assertIn("maturation_coverage_demand_fingerprint_mismatch", result.semantic_finding_codes)

    def test_stale_snapshot_produces_no_verified_projection(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory)
            receipt = build_model_maturation_receipt(self.report, self.publication)
            save_evidence_receipt(receipt, output_directory=output)
            stale = snapshot_bytes(
                "artifact:model",
                b"changed",
                path_token="<WORKSPACE>/model.py",
                obligation_ids=("obligation:model-maturation",),
            )
            base = self._contexts(output)
            context = ModelMaturationVerificationContext(
                receipt_context=ReceiptVerificationContext(
                    **{**base.receipt_context.__dict__, "input_snapshots": {stale.artifact_id: stale}}
                ),
                task_id=base.task_id,
                model_id=base.model_id,
                candidate_model_fingerprint=base.candidate_model_fingerprint,
                coverage_demand_fingerprint=base.coverage_demand_fingerprint,
                coverage_universe_id=base.coverage_universe_id,
                coverage_universe_fingerprint=base.coverage_universe_fingerprint,
                input_fingerprint=base.input_fingerprint,
                evidence_fingerprint=base.evidence_fingerprint,
            )
            result = verify_model_maturation_receipt(
                ModelMaturationReceiptRef(receipt.receipt_id, receipt.fingerprint),
                context,
                output_directory=output,
            )
        self.assertFalse(result.current)
        self.assertIsNone(result.verified_maturation)

    def test_missing_required_obligation_produces_no_verified_projection(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory)
            receipt = build_model_maturation_receipt(self.report, self.publication)
            save_evidence_receipt(receipt, output_directory=output)
            base = self._contexts(output)
            receipt_context = ReceiptVerificationContext(
                **{
                    **base.receipt_context.__dict__,
                    "required_obligation_ids": ("obligation:not-covered",),
                }
            )
            result = verify_model_maturation_receipt(
                ModelMaturationReceiptRef(receipt.receipt_id, receipt.fingerprint),
                ModelMaturationVerificationContext(
                    receipt_context=receipt_context,
                    task_id=base.task_id,
                    model_id=base.model_id,
                    candidate_model_fingerprint=base.candidate_model_fingerprint,
                    coverage_demand_fingerprint=base.coverage_demand_fingerprint,
                    coverage_universe_id=base.coverage_universe_id,
                    coverage_universe_fingerprint=base.coverage_universe_fingerprint,
                    input_fingerprint=base.input_fingerprint,
                    evidence_fingerprint=base.evidence_fingerprint,
                ),
                output_directory=output,
            )
        self.assertFalse(result.current)
        self.assertIsNone(result.verified_maturation)
        self.assertIn(
            "proof_artifact_missing_required_obligation",
            result.receipt_verification.finding_codes,
        )

    def test_cli_independently_verifies_canonical_receipt(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory)
            receipt = build_model_maturation_receipt(self.report, self.publication)
            save_evidence_receipt(receipt, output_directory=output)
            context = self._contexts(
                output,
                required_receipt_fingerprint=receipt.fingerprint,
            )
            receipt_context = context.receipt_context
            payload = {
                "receipt_ref": ModelMaturationReceiptRef(
                    receipt.receipt_id,
                    receipt.fingerprint,
                ).to_dict(),
                "verification_context": {
                    "receipt_context": {
                        "input_snapshots": [
                            item.to_dict()
                            for item in receipt_context.input_snapshots.values()
                        ],
                        "contract_hash": receipt_context.contract_hash,
                        "check_manifest_hash": receipt_context.check_manifest_hash,
                        "suite_map_hash": receipt_context.suite_map_hash,
                        "producer_id": receipt_context.producer_id,
                        "producer_version": receipt_context.producer_version,
                        "environment_fingerprint": receipt_context.environment_fingerprint,
                        "proof_artifact_fingerprint": receipt_context.proof_artifact_fingerprint,
                        "result_fingerprint": receipt_context.result_fingerprint,
                        "command": list(receipt_context.command),
                        "working_directory_token": receipt_context.working_directory_token,
                        "proof_artifact_id": receipt_context.proof_artifact_id,
                        "required_obligation_ids": list(receipt_context.required_obligation_ids),
                        "eligible_claim_scopes": list(receipt_context.eligible_claim_scopes),
                    },
                    "task_id": context.task_id,
                    "model_id": context.model_id,
                    "candidate_model_fingerprint": context.candidate_model_fingerprint,
                    "coverage_demand_fingerprint": context.coverage_demand_fingerprint,
                    "coverage_universe_id": context.coverage_universe_id,
                    "coverage_universe_fingerprint": context.coverage_universe_fingerprint,
                    "input_fingerprint": context.input_fingerprint,
                    "evidence_fingerprint": context.evidence_fingerprint,
                    "required_receipt_fingerprint": receipt.fingerprint,
                },
            }
            context_path = output / "verification-context.json"
            context_path.write_text(json.dumps(payload), encoding="utf-8")
            exit_code = main(
                [
                    "model-maturation-receipt-verify",
                    "--context",
                    str(context_path),
                    "--receipt-root",
                    str(output),
                    "--json",
                ]
            )
        self.assertEqual(0, exit_code)

    def test_reference_fingerprint_mismatch_is_visible(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory)
            receipt = build_model_maturation_receipt(self.report, self.publication)
            save_evidence_receipt(receipt, output_directory=output)
            result = verify_model_maturation_receipt(
                ModelMaturationReceiptRef(receipt.receipt_id, "sha256:wrong"),
                self._contexts(output),
                output_directory=output,
            )
        self.assertIsNone(result.verified_maturation)
        self.assertIn(
            "maturation_receipt_reference_fingerprint_mismatch",
            result.semantic_finding_codes,
        )

    def test_receipt_store_tamper_cannot_be_loaded_as_authority(self) -> None:
        with TemporaryDirectory() as directory:
            output = Path(directory)
            receipt = build_model_maturation_receipt(self.report, self.publication)
            save_evidence_receipt(receipt, output_directory=output)
            path = receipt_path(receipt.receipt_id, output_directory=output)
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["metadata"]["model_maturation"]["decision"] = "fabricated"
            path.write_text(json.dumps(payload), encoding="utf-8")
            result = verify_model_maturation_receipt(
                ModelMaturationReceiptRef(receipt.receipt_id, receipt.fingerprint),
                self._contexts(output),
                output_directory=output,
            )
            self.assertIsNone(result.verified_maturation)
            self.assertIn(
                "maturation_receipt_reference_fingerprint_mismatch",
                result.semantic_finding_codes,
            )


if __name__ == "__main__":
    unittest.main()

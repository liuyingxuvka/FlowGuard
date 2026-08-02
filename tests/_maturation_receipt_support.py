from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from flowguard.evidence_receipts import (
    ReceiptVerificationContext,
    fingerprint_value,
    save_evidence_receipt,
    snapshot_bytes,
)
from flowguard.model_maturation import (
    MODEL_MATURATION_CONFIDENCE_BLOCKED,
    MODEL_MATURATION_CONFIDENCE_FULL,
    MODEL_MATURATION_DECISION_CLOSED_FOR_TASK,
    MODEL_MATURATION_DECISION_PROGRESS_STALLED,
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


def verified_maturation(
    *,
    closed: bool = True,
    task_id: str = "task:test",
    evidence_id: str = "maturation:test",
    model_id: str = "model:test",
    gap: str = "gap:test",
) -> VerifiedModelMaturation:
    decision = (
        MODEL_MATURATION_DECISION_CLOSED_FOR_TASK
        if closed
        else MODEL_MATURATION_DECISION_PROGRESS_STALLED
    )
    confidence = MODEL_MATURATION_CONFIDENCE_FULL if closed else MODEL_MATURATION_CONFIDENCE_BLOCKED
    gaps = () if closed else (gap,)
    report = ModelMaturationReport(
        ok=closed,
        plan_id="plan:test",
        decision=decision,
        confidence=confidence,
        model_id=model_id,
        task_id=task_id,
        coverage_universe_id="coverage:test",
        coverage_demand_fingerprint="sha256:demand",
        coverage_universe_fingerprint="sha256:coverage",
        base_model_fingerprint="sha256:base",
        candidate_model_fingerprint="sha256:candidate",
        evidence_fingerprint="sha256:evidence",
        evidence_id=evidence_id,
        terminal_reason=decision,
        open_gap_fingerprints=gaps,
        input_fingerprint="sha256:input",
    )
    snapshot = snapshot_bytes(
        "artifact:model",
        b"model",
        path_token="<WORKSPACE>/model.py",
        obligation_ids=("obligation:model-maturation",),
    )
    environment = {"python_version": "test"}
    publication = ModelMaturationReceiptPublication(
        producer_id="flowguard.model_maturation",
        producer_version="test",
        command=("python", "model.py"),
        started_at="2026-08-02T00:00:00+00:00",
        finished_at="2026-08-02T00:00:01+00:00",
        environment_metadata=environment,
        contract_hash="sha256:contract",
        check_manifest_hash="sha256:manifest",
        suite_map_hash="sha256:suite",
        input_snapshots=(snapshot,),
        covered_obligation_ids=("obligation:model-maturation",),
    )
    receipt = build_model_maturation_receipt(report, publication)
    with TemporaryDirectory() as directory:
        output = Path(directory)
        save_evidence_receipt(receipt, output_directory=output)
        receipt_context = ReceiptVerificationContext(
            input_snapshots={snapshot.artifact_id: snapshot},
            contract_hash=publication.contract_hash,
            check_manifest_hash=publication.check_manifest_hash,
            suite_map_hash=publication.suite_map_hash,
            producer_id=publication.producer_id,
            producer_version=publication.producer_version,
            environment_fingerprint=fingerprint_value(environment),
            proof_artifact_fingerprint=report.evidence_fingerprint,
            result_fingerprint=fingerprint_value(report.to_dict()),
            command=publication.command,
            working_directory_token=publication.working_directory_token,
            proof_artifact_id=report.evidence_id,
            required_obligation_ids=publication.covered_obligation_ids,
            eligible_claim_scopes=(MODEL_MATURATION_RECEIPT_CLAIM_SCOPE,),
            receipt_store_output_directory=str(output),
        )
        context = ModelMaturationVerificationContext(
            receipt_context=receipt_context,
            task_id=report.task_id,
            model_id=report.model_id,
            candidate_model_fingerprint=report.candidate_model_fingerprint,
            coverage_demand_fingerprint=report.coverage_demand_fingerprint,
            coverage_universe_id=report.coverage_universe_id,
            coverage_universe_fingerprint=report.coverage_universe_fingerprint,
            input_fingerprint=report.input_fingerprint,
            evidence_fingerprint=report.evidence_fingerprint,
            required_receipt_fingerprint=receipt.fingerprint,
        )
        result = verify_model_maturation_receipt(
            ModelMaturationReceiptRef(receipt.receipt_id, receipt.fingerprint),
            context,
            output_directory=output,
        )
    assert result.verified_maturation is not None
    return result.verified_maturation

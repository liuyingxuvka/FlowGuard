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
from flowguard.model_path_quality import (
    PathQualityResult,
    PathQualitySubject,
    canonical_fingerprint,
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


def _path_quality_material(model_id: str, model_fingerprint: str):
    identity = lambda name: canonical_fingerprint(
        {"model_id": model_id, "identity": name}
    )
    subject = PathQualitySubject(
        model_id=model_id,
        boundary_id=f"behavior:{model_id}",
        model_fingerprint=model_fingerprint,
        normalized_facts_fingerprint=identity("normalized-facts"),
        retained_element_inventory_fingerprint=identity("retained-elements"),
        purpose_fingerprint=identity("purpose"),
        intent_fingerprint=identity("intent"),
        obligation_fingerprint=identity("obligations"),
        provider_fingerprint=identity("provider"),
        dependency_fingerprint=identity("dependencies"),
        code_fingerprint=identity("code"),
        test_fingerprint=identity("tests"),
        oracle_fingerprint=identity("oracles"),
        evidence_fingerprint=identity("evidence"),
        currentness_id="revision:test",
    )
    result = PathQualityResult(
        result_id=f"path-quality:{model_id}",
        subject_fingerprint=subject.fingerprint,
        mode="lightweight",
        trigger_ids=(),
        finding_ids=(),
        candidate_ids=(),
        rewrite_rule_ids=(),
        conclusion="single_clear_path",
        unresolved_ids=(),
        selected_candidate_id="",
        selected_candidate_lane="",
        comparison_boundary_id="",
        candidate_set_fingerprint="",
        rewrite_set_fingerprint="",
        necessity_witness_set_fingerprint=identity("necessity-witnesses"),
        detail_evidence_fingerprint=identity("path-detail"),
        producer_id="model_maturation:path-quality",
        currentness_id=subject.currentness_id,
    )
    return subject, result


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
    candidate_fingerprint = canonical_fingerprint(
        {"candidate": model_id, "task_id": task_id}
    )
    subject, path_result = _path_quality_material(
        model_id, candidate_fingerprint
    )
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
        candidate_model_fingerprint=candidate_fingerprint,
        evidence_fingerprint="sha256:evidence",
        evidence_id=evidence_id,
        terminal_reason=decision,
        open_gap_fingerprints=gaps,
        input_fingerprint="sha256:input",
        required_path_quality_model_ids=(model_id,),
        path_quality_subjects=(subject,),
        path_quality_results=(path_result,),
        owner_resolution_ids=("resolution:test",),
        owner_resolution_fingerprints=("sha256:resolution-test",),
        owner_resolution_owner_ids=("model_first_function_flow",),
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
            required_path_quality_model_ids=(
                report.required_path_quality_model_ids
            ),
            path_quality_subjects=report.path_quality_subjects,
            path_quality_results=report.path_quality_results,
            path_quality_result_set_fingerprint=(
                report.path_quality_result_set_fingerprint
            ),
            owner_resolution_ids=report.owner_resolution_ids,
            owner_resolution_fingerprints=report.owner_resolution_fingerprints,
            owner_resolution_owner_ids=report.owner_resolution_owner_ids,
            required_receipt_fingerprint=receipt.fingerprint,
        )
        result = verify_model_maturation_receipt(
            ModelMaturationReceiptRef(receipt.receipt_id, receipt.fingerprint),
            context,
            output_directory=output,
        )
    assert result.verified_maturation is not None
    return result.verified_maturation

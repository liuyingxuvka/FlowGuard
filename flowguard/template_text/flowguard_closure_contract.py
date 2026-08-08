"""Template text for FlowGuard flowguard closure contract route."""

from __future__ import annotations

FLOWGUARD_CLOSURE_CONTRACT_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Reviews whether a broad done, release, publish, or production-confidence claim
has consumed current FlowGuard evidence from runtime traces, artifact
freshness, model quality, same-class misses, runtime gateway inventory, and the
risk ledger.

Guards against:
- treating a model pass or test pass as complete FlowGuard use;
- runtime traces that are not mapped back to model obligations;
- changed artifacts that still rely on stale proof;
- unresolved model-quality or same-class model-miss gaps;
- critical runtime writes without gateway inventory evidence.
- field lifecycle, field projection, or replacement disposition evidence that
  is missing or stale before a broad confidence claim.
- UI complete/runnable/button-wired claims that lack a UI done-claim review,
  observed real-surface inventory, functional-capability coverage,
  functional-chain evidence, or native-dialog blindspot boundary.

Use before editing:
final confidence reports, runtime gateway adoption, release closure, or route
closure packages that depend on multiple FlowGuard evidence routes.

Run:
python .flowguard/closure_contract/run_checks.py

Replace the sample IDs with the project evidence IDs for the claim under
review.
"""

from __future__ import annotations

from tempfile import TemporaryDirectory

from flowguard import (
    CLOSURE_CONFIDENCE_FULL,
    CLOSURE_REPORT_FIELD_LIFECYCLE,
    CLOSURE_REPORT_RISK_LEDGER,
    CLOSURE_REPORT_RUNTIME_GATEWAY,
    CLOSURE_REPORT_UI_DONE_CLAIM,
    CLOSURE_REPORT_UI_FUNCTIONAL_CAPABILITY_COVERAGE,
    MODEL_QUALITY_HIDDEN_STATE,
    MODEL_MATURATION_CONFIDENCE_FULL,
    MODEL_MATURATION_DECISION_CLOSED_FOR_TASK,
    MODEL_MATURATION_RECEIPT_CLAIM_SCOPE,
    RISK_LEDGER_DECISION_FULL,
    ArtifactInvalidation,
    ClosureEvidenceReport,
    FlowGuardClosureContractPlan,
    ModelQualitySignal,
    ModelMaturationReceiptPublication,
    ModelMaturationReceiptRef,
    ModelMaturationReport,
    ModelMaturationVerificationContext,
    ReceiptVerificationContext,
    RuntimeGatewayInventoryClosure,
    RuntimeTraceMapping,
    SameClassMissClosure,
    build_model_maturation_receipt,
    fingerprint_value,
    review_flowguard_closure_contract,
    save_evidence_receipt,
    snapshot_bytes,
    verify_model_maturation_receipt,
)
from flowguard.model_path_quality import PathQualityResult, PathQualitySubject


def resolved_path_quality(model_id, model_fingerprint):
    def identity(name):
        return fingerprint_value({"model_id": model_id, "identity": name})

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
        currentness_id="revision:template-current",
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


def maturation_evidence():
    model_id = "model:critical-write"
    candidate_model_fingerprint = fingerprint_value(
        {"model_id": model_id, "candidate": "template-current"}
    )
    path_quality_subject, path_quality_result = resolved_path_quality(
        model_id, candidate_model_fingerprint
    )
    report = ModelMaturationReport(
        ok=True,
        plan_id="plan:sample",
        evidence_id="maturation:sample",
        task_id="task:sample",
        model_id=model_id,
        coverage_demand_fingerprint="sha256:demand",
        candidate_model_fingerprint=candidate_model_fingerprint,
        coverage_universe_id="coverage:sample",
        coverage_universe_fingerprint="sha256:coverage",
        input_fingerprint="sha256:intake",
        evidence_fingerprint="sha256:evidence",
        decision=MODEL_MATURATION_DECISION_CLOSED_FOR_TASK,
        confidence=MODEL_MATURATION_CONFIDENCE_FULL,
        terminal_reason=MODEL_MATURATION_DECISION_CLOSED_FOR_TASK,
        required_path_quality_model_ids=(model_id,),
        path_quality_subjects=(path_quality_subject,),
        path_quality_results=(path_quality_result,),
        owner_resolution_ids=("resolution:critical-write",),
        owner_resolution_fingerprints=("sha256:resolution-critical-write",),
        owner_resolution_owner_ids=("model_first_function_flow",),
    )
    snapshot = snapshot_bytes(
        "artifact:critical-write-model",
        b"critical-write-model",
        path_token="<WORKSPACE>/.flowguard/critical_write/model.py",
        obligation_ids=("obligation:critical-write-maturation",),
    )
    environment = {"python_version": "template"}
    publication = ModelMaturationReceiptPublication(
        producer_id="flowguard.model_maturation",
        producer_version="template",
        command=("python", ".flowguard/critical_write/run_checks.py"),
        started_at="2026-01-01T00:00:00+00:00",
        finished_at="2026-01-01T00:00:01+00:00",
        environment_metadata=environment,
        contract_hash="sha256:contract",
        check_manifest_hash="sha256:manifest",
        suite_map_hash="sha256:suite",
        input_snapshots=(snapshot,),
        covered_obligation_ids=("obligation:critical-write-maturation",),
    )
    receipt = build_model_maturation_receipt(report, publication)
    with TemporaryDirectory() as receipt_root:
        save_evidence_receipt(receipt, output_directory=receipt_root)
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
            receipt_store_output_directory=receipt_root,
        )
        verification = verify_model_maturation_receipt(
            ModelMaturationReceiptRef(receipt.receipt_id, receipt.fingerprint),
            ModelMaturationVerificationContext(
                receipt_context=receipt_context,
                task_id=report.task_id,
                model_id=report.model_id,
                candidate_model_fingerprint=report.candidate_model_fingerprint,
                coverage_demand_fingerprint=report.coverage_demand_fingerprint,
                coverage_universe_id=report.coverage_universe_id,
                coverage_universe_fingerprint=report.coverage_universe_fingerprint,
                input_fingerprint=report.input_fingerprint,
                evidence_fingerprint=report.evidence_fingerprint,
                required_path_quality_model_ids=report.required_path_quality_model_ids,
                path_quality_subjects=report.path_quality_subjects,
                path_quality_results=report.path_quality_results,
                path_quality_result_set_fingerprint=report.path_quality_result_set_fingerprint,
                owner_resolution_ids=report.owner_resolution_ids,
                owner_resolution_fingerprints=report.owner_resolution_fingerprints,
                owner_resolution_owner_ids=report.owner_resolution_owner_ids,
                required_receipt_fingerprint=receipt.fingerprint,
            ),
            output_directory=receipt_root,
        )
    if verification.verified_maturation is None:
        raise RuntimeError("template maturation receipt did not verify")
    return verification.verified_maturation


def evidence_report(report_id, report_kind=CLOSURE_REPORT_RISK_LEDGER, **overrides):
    maturation_identity = maturation_evidence()
    values = {
        "report_id": report_id,
        "report_kind": report_kind,
        "decision": (
            RISK_LEDGER_DECISION_FULL
            if report_kind == CLOSURE_REPORT_RISK_LEDGER
            else f"{report_kind}:green"
        ),
        "ok": True,
        "current": True,
        "confidence": CLOSURE_CONFIDENCE_FULL,
        "result_status": "passed",
        "proof_artifact_ids": (f"artifact:{report_id}",),
        "metadata": {
            "model_maturation_evidence_id": maturation_identity.evidence_id,
            "model_maturation_receipt_id": maturation_identity.receipt_id,
            "model_maturation_receipt_fingerprint": maturation_identity.receipt_fingerprint,
        },
    }
    values.update(overrides)
    return ClosureEvidenceReport(**values)


def correct_closure_plan():
    return FlowGuardClosureContractPlan(
        claim_id="release:sample",
        runtime_trace_mappings=(
            RuntimeTraceMapping(
                "trace:critical-write",
                model_obligation_id="model:critical-write",
                source_evidence_id="artifact:runtime-replay",
            ),
        ),
        artifact_invalidations=(
            ArtifactInvalidation(
                "artifact:gateway-code",
                dependent_evidence_ids=("artifact:old-runtime-gateway-proof",),
                revalidation_evidence_ids=("artifact:new-runtime-gateway-proof",),
            ),
        ),
        model_quality_signals=(
            ModelQualitySignal(
                "quality:hidden-state-reviewed",
                MODEL_QUALITY_HIDDEN_STATE,
                model_id="model:critical-write",
                resolved=True,
                resolution_evidence_ids=("artifact:model-quality-review",),
            ),
        ),
        same_class_miss_closures=(
            SameClassMissClosure(
                "miss:critical-write",
                observed_failure_evidence_id="artifact:observed-runtime-failure",
                same_class_proof_evidence_id="artifact:same-class-regression",
                model_obligation_id="model:critical-write",
            ),
        ),
        runtime_gateway_closures=(
            RuntimeGatewayInventoryClosure(
                "gateway:critical-state",
                inventory_source_evidence_ids=("inventory:static-writers", "inventory:runtime-replay"),
                gateway_report_evidence_id="report:runtime-gateway",
            ),
        ),
        evidence_reports=(
            evidence_report("report:field-lifecycle", CLOSURE_REPORT_FIELD_LIFECYCLE),
            evidence_report("report:runtime-gateway", CLOSURE_REPORT_RUNTIME_GATEWAY),
            evidence_report("report:risk-ledger", CLOSURE_REPORT_RISK_LEDGER),
            evidence_report("report:ui-capability-coverage", CLOSURE_REPORT_UI_FUNCTIONAL_CAPABILITY_COVERAGE),
            evidence_report("report:ui-done-claim", CLOSURE_REPORT_UI_DONE_CLAIM),
        ),
        model_maturation_evidence=(maturation_evidence(),),
        require_field_lifecycle=True,
        require_ui_functional_capability_coverage=True,
        require_ui_done_claim_review=True,
    )


def broken_closure_plan():
    return FlowGuardClosureContractPlan(
        claim_id="release:broken-point-evidence",
        runtime_trace_mappings=(RuntimeTraceMapping("trace:unmapped"),),
        artifact_invalidations=(
            ArtifactInvalidation(
                "artifact:changed-gateway",
                dependent_evidence_ids=("artifact:old-proof",),
                revalidation_evidence_ids=(),
            ),
        ),
        model_quality_signals=(
            ModelQualitySignal(
                "quality:hidden-state-open",
                MODEL_QUALITY_HIDDEN_STATE,
                model_id="model:critical-write",
            ),
        ),
        same_class_miss_closures=(
            SameClassMissClosure(
                "miss:no-same-class-proof",
                observed_failure_evidence_id="artifact:observed-failure",
            ),
        ),
        runtime_gateway_closures=(
            RuntimeGatewayInventoryClosure(
                "gateway:critical-state",
                gateway_report_evidence_id="report:runtime-gateway",
            ),
        ),
        evidence_reports=(
            evidence_report("report:runtime-gateway", CLOSURE_REPORT_RUNTIME_GATEWAY),
            evidence_report("report:risk-ledger", CLOSURE_REPORT_RISK_LEDGER),
        ),
    )


def run_checks():
    return (
        review_flowguard_closure_contract(correct_closure_plan()),
        review_flowguard_closure_contract(broken_closure_plan()),
    )
'''

FLOWGUARD_CLOSURE_CONTRACT_RUN_CHECKS_TEMPLATE = '''"""Run the FlowGuard Closure Contract template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    correct, broken = run_checks()
    print(correct.format_text())
    print()
    print(broken.format_text(max_findings=8))
    return 0 if correct.ok and not broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

FLOWGUARD_CLOSURE_CONTRACT_NOTES_TEMPLATE = """# FlowGuard Closure Contract Notes

Use this scaffold before a broad done, release, publish, or
production-confidence claim.

## What The Closure Review Consumes

- Runtime traces mapped back to named model obligations.
- Changed artifacts with dependent evidence and fresh revalidation evidence.
- Model-quality signals such as hidden state, missing side effects, owner
  ambiguity, helper-only proof, missing public boundary, and parent/child
  evidence gaps.
- Same-class model-miss closure evidence with both the observed failure and
  ContractExhaustionMesh case proof.
- Runtime gateway inventory closure for critical state writers.
- FieldLifecycleMesh evidence for behavior-bearing fields, old/replaced fields,
  and replacement disposition.
- Risk Evidence Ledger and route reports with current passing full-confidence
  evidence.
- One exact current closed-for-task Model Maturation identity, which must be
  the same identity recorded by the Risk Evidence Ledger report.

The closure review is a final coordinator. It does not replace the route that
owns each proof; it blocks or scopes the final claim when any required evidence
is stale, skipped, progress-only, missing, internally scoped, or unresolved.
"""

__all__ = [
    'FLOWGUARD_CLOSURE_CONTRACT_MODEL_TEMPLATE',
    'FLOWGUARD_CLOSURE_CONTRACT_RUN_CHECKS_TEMPLATE',
    'FLOWGUARD_CLOSURE_CONTRACT_NOTES_TEMPLATE',
]

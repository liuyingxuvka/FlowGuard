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

from flowguard import (
    CLOSURE_CONFIDENCE_FULL,
    CLOSURE_REPORT_FIELD_LIFECYCLE,
    CLOSURE_REPORT_RISK_LEDGER,
    CLOSURE_REPORT_RUNTIME_GATEWAY,
    CLOSURE_REPORT_UI_DONE_CLAIM,
    CLOSURE_REPORT_UI_FUNCTIONAL_CAPABILITY_COVERAGE,
    MODEL_QUALITY_HIDDEN_STATE,
    ArtifactInvalidation,
    ClosureEvidenceReport,
    FlowGuardClosureContractPlan,
    ModelQualitySignal,
    RuntimeGatewayInventoryClosure,
    RuntimeTraceMapping,
    SameClassMissClosure,
    review_flowguard_closure_contract,
)


def evidence_report(report_id, report_kind=CLOSURE_REPORT_RISK_LEDGER, **overrides):
    values = {
        "report_id": report_id,
        "report_kind": report_kind,
        "decision": f"{report_kind}:green",
        "ok": True,
        "current": True,
        "confidence": CLOSURE_CONFIDENCE_FULL,
        "result_status": "passed",
        "proof_artifact_ids": (f"artifact:{report_id}",),
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
  same-class proof.
- Runtime gateway inventory closure for critical state writers.
- FieldLifecycleMesh evidence for behavior-bearing fields, old/replaced fields,
  and replacement disposition.
- Risk Evidence Ledger and route reports with current passing full-confidence
  evidence.

The closure review is a final coordinator. It does not replace the route that
owns each proof; it blocks or scopes the final claim when any required evidence
is stale, skipped, progress-only, missing, internally scoped, or unresolved.
"""

__all__ = [
    'FLOWGUARD_CLOSURE_CONTRACT_MODEL_TEMPLATE',
    'FLOWGUARD_CLOSURE_CONTRACT_RUN_CHECKS_TEMPLATE',
    'FLOWGUARD_CLOSURE_CONTRACT_NOTES_TEMPLATE',
]

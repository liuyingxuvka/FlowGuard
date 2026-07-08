"""Template text for Behavior Commitment Ledger adoption."""

BEHAVIOR_COMMITMENT_LEDGER_MODEL_TEMPLATE = r'''"""FlowGuard Behavior Commitment Ledger template.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Register the full external behavior promise set before broad work claims.
Guards against: missing behavior, invented extra behavior, overlapping model ownership, stale evidence, and path-sensitive behavior without Primary Path Authority.
Use before editing: non-trivial project adoption, feature work, UI/API/CLI changes, release, archive, publish, or broad done confidence.
Run: python run_checks.py
"""

from flowguard import (
    BCL_COMMITMENT_WORKFLOW,
    BCL_EVIDENCE_CURRENT_PASS,
    BCL_SCOPE_FULL,
    BCL_SOURCE_DOC,
    BehaviorCommitment,
    BehaviorCommitmentLedger,
    BehaviorEvidenceBinding,
    BehaviorSourceSurface,
)


def build_behavior_commitment_ledger():
    return BehaviorCommitmentLedger(
        "project-behavior-ledger",
        project_boundary="example project external behavior",
        current_revision="template-initial",
        claim_scope=BCL_SCOPE_FULL,
        owner="project-maintainer",
        validation_boundary="template smoke plus project-specific FlowGuard evidence",
        rationale="baseline ledger records external behavior promises before implementation paths",
        expected_commitment_ids=("commitment:run-primary-workflow",),
        source_surfaces=(
            BehaviorSourceSurface(
                "surface:readme-workflow",
                surface_kind=BCL_SOURCE_DOC,
                label="README promises the primary workflow",
                source_ref="README.md#usage",
                commitment_ids=("commitment:run-primary-workflow",),
                owner="project-maintainer",
                validation_boundary="README and smoke test stay aligned",
                rationale="public docs are an external behavior source",
            ),
        ),
        commitments=(
            BehaviorCommitment(
                "commitment:run-primary-workflow",
                label="run the primary workflow",
                commitment_kind=BCL_COMMITMENT_WORKFLOW,
                actor="user or agent",
                trigger="invokes the documented primary command",
                expected_result="workflow reaches documented success or visible repairable error",
                failure_boundary="fail closed with visible repair information",
                source_surface_ids=("surface:readme-workflow",),
                primary_owner_model_id="model:primary-workflow",
                validation_boundary="model obligation, code contract, and smoke test cover the same behavior",
                rationale="this is the external behavior promise; helper functions are implementation details",
                evidence=BehaviorEvidenceBinding(
                    model_obligation_ids=("obligation:primary-workflow",),
                    code_contract_ids=("contract:primary-workflow",),
                    test_evidence_ids=("test:primary-workflow-smoke",),
                    risk_gate_ids=("risk_gate:behavior_commitment_coverage:project-behavior-ledger",),
                    coverage_case_ids=("bcl.full_inventory_mapping.workflow.doc.mapped",),
                    coverage_shard_ids=("contract_shard:behavior_commitment_ledger:full_inventory_mapping",),
                    coverage_receipt_ids=("contract_coverage:behavior_commitment_ledger",),
                    evidence_state=BCL_EVIDENCE_CURRENT_PASS,
                    current=True,
                ),
            ),
        ),
    )
'''


BEHAVIOR_COMMITMENT_LEDGER_RUN_CHECKS_TEMPLATE = r'''from model import build_behavior_commitment_ledger
from flowguard import review_behavior_commitment_ledger


def main():
    report = review_behavior_commitment_ledger(build_behavior_commitment_ledger())
    print("flowguard behavior commitment ledger")
    print(report.format_text())
    print("full_inventory_registered:", "yes" if report.ok else "no")
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


BEHAVIOR_COMMITMENT_LEDGER_NOTES_TEMPLATE = """# FlowGuard Behavior Commitment Ledger

Use this ledger as the upstream account book for external behavior promises.
Register UI, API, CLI, skill, workflow, release, process, and documentation
behavior that users or downstream agents can rely on. Do not register every
helper function or private implementation detail as a commitment.

For each commitment:

- record the source surface that promised or exposed it;
- name exactly one primary owner model;
- list supporting or child models only after the primary owner is clear;
- bind current model, code-contract, test, coverage, and risk evidence;
- if `path_sensitive=true`, attach Primary Path Authority evidence instead of
  creating another fallback checker.

Broad done, release, publish, archive, production, or full-confidence claims
need current ledger evidence.
"""

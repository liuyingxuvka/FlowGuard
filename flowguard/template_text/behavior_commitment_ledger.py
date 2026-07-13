"""Template text for canonical Behavior Commitment Ledger adoption."""

BEHAVIOR_COMMITMENT_LEDGER_LEDGER_TEMPLATE = r'''{
  "artifact_type": "flowguard_behavior_commitment_ledger",
  "format_version": "1",
  "ledger": {
    "change_mode": "bootstrap_ledger",
    "claim_scope": "full",
    "commitments": [
      {
        "actor": "end user",
        "actor_kind": "end_user",
        "behavior_plane": "product_runtime",
        "business_intent_id": "intent:run-primary-workflow",
        "commitment_id": "commitment:run-primary-workflow",
        "commitment_kind": "workflow",
        "evidence": {
          "code_contract_ids": ["contract:primary-workflow"],
          "coverage_case_ids": ["bcl.behavior_plane.product_runtime.workflow.end_user"],
          "coverage_receipt_ids": ["contract_coverage:behavior_commitment_ledger"],
          "coverage_shard_ids": ["contract_shard:behavior_commitment_ledger:plane-actor"],
          "current": true,
          "evidence_state": "current_pass",
          "model_obligation_ids": ["obligation:primary-workflow"],
          "risk_gate_ids": ["risk_gate:behavior_commitment_coverage:project-behavior-ledger"],
          "test_evidence_ids": ["test:primary-workflow-smoke"],
          "test_mesh_state": "shard_current"
        },
        "expected_result": "workflow reaches documented success or a visible repairable error",
        "expected_terminal": "documented success or visible repairable failure",
        "failure_boundary": "fail closed with visible repair information",
        "label": "run the primary workflow",
        "lookup_binding": {
          "path_patterns": ["README.md", "src/primary_workflow"],
          "task_terms": ["primary workflow", "documented command"],
          "tool_ids": ["project-primary-command"],
          "workflow_families": ["primary_workflow"]
        },
        "primary_owner_model_id": "model:primary-workflow",
        "rationale": "this is the external behavior promise; helper functions are implementation details",
        "source_surface_ids": ["surface:readme-workflow", "surface:workflow-api"],
        "trigger": "the documented primary command is invoked",
        "validation_boundary": "model obligation, code contract, and smoke test cover the same behavior"
      }
    ],
    "current_revision": "template-initial",
    "expected_business_intent_ids": ["intent:run-primary-workflow"],
    "expected_commitment_ids": ["commitment:run-primary-workflow"],
    "ledger_id": "project-behavior-ledger",
    "metadata": {
      "canonical_authority": ".flowguard/behavior_commitment_ledger/ledger.json",
      "python_adapter_role": "thin_loader_only"
    },
    "owner": "project-maintainer",
    "project_boundary": "example project external behavior",
    "rationale": "baseline ledger records external behavior promises before implementation paths",
    "require_current_evidence": true,
    "require_risk_gates_for_broad_claim": true,
    "source_surfaces": [
      {
        "business_intent_ids": ["intent:run-primary-workflow"],
        "commitment_ids": ["commitment:run-primary-workflow"],
        "freshness_state": "current",
        "label": "README promises the primary workflow",
        "owner": "project-maintainer",
        "primary_path_id": "path:primary-workflow",
        "rationale": "public docs are an external behavior source",
        "source_ref": "README.md#usage",
        "surface_id": "surface:readme-workflow",
        "surface_kind": "doc",
        "validation_boundary": "README and smoke test stay aligned"
      },
      {
        "business_intent_ids": ["intent:run-primary-workflow"],
        "commitment_ids": ["commitment:run-primary-workflow"],
        "delegates_to_primary_path": true,
        "freshness_state": "current",
        "label": "API exposes the same primary workflow",
        "owner": "project-maintainer",
        "primary_path_id": "path:primary-workflow",
        "rationale": "the API is another surface, not another commitment",
        "source_ref": "api/run-primary-workflow",
        "surface_id": "surface:workflow-api",
        "surface_kind": "api",
        "validation_boundary": "API delegation replay reaches the selected primary workflow"
      }
    ],
    "validation_boundary": "template smoke plus project-specific FlowGuard evidence"
  },
  "schema_version": "1.0"
}
'''


BEHAVIOR_COMMITMENT_LEDGER_MODEL_TEMPLATE = r'''"""Thin adapter for the canonical FlowGuard behavior commitment ledger.

FlowGuard Risk Purpose Header
Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Load the full external behavior promise set before broad work claims.
Guards against: duplicate authorities, mixed execution planes, stale evidence,
and Python-embedded inventory drifting from the machine-readable ledger.
Use before editing: non-trivial product behavior, UI/API/CLI changes, release,
archive, publish, or any broad external-behavior coverage claim.
Run: python run_checks.py
"""

from pathlib import Path

from flowguard import load_behavior_commitment_ledger


LEDGER_PATH = Path(__file__).with_name("ledger.json")


def build_behavior_commitment_ledger():
    return load_behavior_commitment_ledger(LEDGER_PATH)
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

Keep one BCL structure and one canonical `ledger.json`, but classify every
commitment into exactly one execution plane:

- `product_runtime`: behavior of the product or service seen by an end user or
  external system;
- `agent_operation`: steps the AI performs with tools, files, ports, browsers,
  publishing, or handoff operations;
- `development_process`: planning, validation, release, installation,
  synchronization, and completion gates.

`commitment_kind` remains orthogonal: UI, API, workflow, skill, or process does
not by itself decide the execution plane. Record a structured `actor_kind`,
and connect different planes only through typed relations such as `invokes`,
`validates`, `governs`, or `requires_evidence_from`. Related commitments are
context, not a second set of primary execution instructions.

At task time, perform a bounded lookup before path-only discovery. Match the
declared plane first, then exact commitment ids, tools, error signatures,
paths, workflow families, and task terms. If the plane is ambiguous, show
candidates and continue ordinary discovery; do not guess an owner or force
every action through a model.

For each commitment:

- assign one stable `business_intent_id` to one exact external purpose and keep
  exactly one active commitment for that identity;
- map repeated UI, API, CLI, alias, adapter, wrapper, and compatibility
  surfaces to the same commitment instead of creating delegate commitments;
- name exactly one primary owner model and bind current model, code-contract,
  TestMesh, coverage, and risk evidence;
- keep old or alternate success surfaces out of service through an explicit
  disposition;
- on Model Miss, query the same plane and reuse the existing commitment first;
  create a coverage-gap candidate only when no registered promise exists;
- if `path_sensitive=true`, attach one unambiguous Primary Path Authority
  identity. Legacy plural input is migration evidence only and never a second
  runtime authority.

The Python `model.py` is deliberately a thin loader. Do not rebuild an embedded
inventory beside `ledger.json`; that would create two authorities.
"""


__all__ = [
    "BEHAVIOR_COMMITMENT_LEDGER_LEDGER_TEMPLATE",
    "BEHAVIOR_COMMITMENT_LEDGER_MODEL_TEMPLATE",
    "BEHAVIOR_COMMITMENT_LEDGER_NOTES_TEMPLATE",
    "BEHAVIOR_COMMITMENT_LEDGER_RUN_CHECKS_TEMPLATE",
]

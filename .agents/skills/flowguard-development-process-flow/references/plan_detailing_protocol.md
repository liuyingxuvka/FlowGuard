# Internal Plan Detailing Protocol

Plan detailing is an internal `development_process_flow` route. It answers one
question before ordinary execution: is the plan detailed enough to check?

Requests for PlanDetailing, rough-plan expansion, or structured planning enter
`flowguard-development-process-flow`. The public owner records the
`plan_detailing` mode, builds the rows below, and consumes
`review_plan_detail(...)` evidence. There is no independent Codex skill,
forwarding entrypoint, alias, or fallback route for this mode.

## Required Rows

- `PlanDetailSource`: current source evidence for the plan.
- `PlanDetailSurface`: in-scope risks, scoped-out risks, and evidence/source
  mappings.
- `PlanDetailArtifact`: requirements, designs, models, code, tests, docs,
  adapters, reports, release assets, and other versioned inputs or outputs.
- `PlanDetailStateSurface`: durable state, facts, and side effects visible to
  the model.
- `PlanDetailStep`: ordered work with prerequisites, receipts, evidence gates,
  validation flags, rework targets, `agent_operation` ownership, and separate
  target commitment/plane/relation references.
- `PlanDetailValidation`, `PlanDetailEvidence`,
  `PlanDetailFailureBranch`, `PlanDetailHumanQuestion`, and
  `PlanDetailFreshnessRule`.
- UI/action rows for reachable controls and real click-through evidence.
- Artifact payload rows for real import, export, save, load, generation, or
  work-package surfaces with accepted and rejected cases.

When process optimization is active, keep only top-level
`process_optimization_reasons` and one current
`required_process_optimization_evidence_ids` reference. Ordinary plans leave
both fields empty.

## Projection Order

1. `plan_detail_to_plan_intake()` preserves sources and risk surfaces.
2. `plan_detail_to_step_contracts()` creates receipt gates.
3. `plan_detail_to_development_process()` preserves lifecycle ownership.
4. `plan_detail_to_agent_workflow_plan()` feeds the internal
   `agent_workflow` route when multiple capabilities or external actions apply.
5. UI and payload obligations go to their public native owners.

## Read-only WorkContext boundary

Each external planning source enters as one current read-only WorkContext row
with context/adapter/native-owner ids, context fingerprint, subject lane, and
exact generic artifact ids/roles/source refs/content fingerprints. Missing,
stale, mutable, unknown, unbounded, or role-incomplete context blocks the
route. The route never creates provider checks, sessions, caches, receipts,
owner mappings, or product-runtime authority.

## Completion Boundary

`pass` means the plan is detailed enough to continue. `scoped`,
`needs_revision`, and `blocked` remain distinct. This route does not execute
the plan or prove implementation, release, or publication.

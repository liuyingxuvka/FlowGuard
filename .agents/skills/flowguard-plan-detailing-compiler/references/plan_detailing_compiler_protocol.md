# Plan Detailing Compiler Protocol

Plan detailing answers one question before ordinary FlowGuard modeling starts:
is the plan detailed enough to check?

Use it when a request is non-trivial but the plan is still a rough idea, a few
steps, or an AI-written outline. The route converts that rough plan into
structured rows that downstream routes can consume. It does not execute the
plan and does not prove the implementation.

## Required Rows

- `PlanDetailSource`: current source evidence for the plan.
- `PlanDetailSurface`: in-scope risks, scoped-out risks, and evidence/source
  mappings.
- `PlanDetailArtifact`: requirements, designs, models, code, tests, docs,
  adapters, reports, release assets, and other versioned things the plan reads
  or writes.
- `PlanDetailStateSurface`: durable state, facts, or side effects that must be
  visible to the model.
- `PlanDetailStep`: ordered work with prerequisites, receipts, evidence gates,
  validation flags, and rework targets.
- `PlanDetailValidation`: validation obligations with evidence kinds, artifact
  ids, evidence ids, and commands.
- UI/action validation rows when a plan has visible controls: reachable
  enabled control ids, expected click-through method, pure-UI classifications,
  human-operability, and manual/native-dialog boundaries.
- Artifact payload rows when a plan imports, exports, saves, loads, generates,
  or consumes files/work packages: real payload surface ids, payload contract
  ids, synthetic accepted and rejected case ids, expected
  outputs/errors/state writes, fixture location, expected execution proof refs,
  and downstream owner route.
- `PlanDetailEvidence`: expected or current evidence rows.
- `PlanDetailFailureBranch`: failure, retry, blocked, or rework branch.
- `PlanDetailHumanQuestion`: unresolved decisions that block or scope claims.
- `PlanDetailFreshnessRule`: upstream changes that stale artifacts or evidence.

## Findings To Expect

- `missing_goal`
- `missing_source_evidence`
- `missing_risk_surfaces`
- `missing_artifacts`
- `missing_state_or_side_effect_surfaces`
- `missing_steps`
- `missing_validations`
- `missing_ui_action_coverage`
- `missing_artifact_payload_pack`
- `missing_failure_branches`
- `rework_gate_missing`
- `continue_gate_missing_evidence`
- `side_effect_missing_evidence_gate`
- `human_question_unresolved`
- `full_claim_missing_final_evidence`
- `full_claim_has_detail_gaps`

## Projection Order

After `review_plan_detail()`:

1. Use `plan_detail_to_plan_intake()` to preserve source evidence and risk
   surfaces.
2. Use `plan_detail_to_step_contracts()` to create receipt gates.
3. Use `plan_detail_to_development_process()` to review artifact freshness and
   completion claims.
4. Use `plan_detail_to_agent_workflow_plan()` when the work involves multiple
   installed skills or external actions.
5. Send UI controls to UI Flow Structure and real-surface payload case evidence
   to Model-Test Alignment or TestMesh before any broad implementation claim.

## Confidence Boundary

`pass` means the plan has enough structured detail to continue. `scoped` means
the plan may continue only with an explicit boundary. `needs_revision` means
the plan should be expanded before execution. `blocked` means a broad claim or
irreversible action is unsupported.

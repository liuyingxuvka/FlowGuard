## Context

FlowGuard currently has strong follow-up routing once a gap is visible:
ExistingModelPreflight prevents duplicate boundaries, SummaryReport and
MaintenanceScan route non-pass findings, FieldLifecycleMesh covers fields, and
ModelMaturation/ModelMesh handle coarse or parent-child models. The missing
piece is earlier and more open ended: an agent can still rely on one model
without explaining whether the feature needs another model angle.

This design keeps the thin FlowGuard entry path intact. It adds a small
structured deliberation object that captures the agent's reasoning about
possible additional model angles. Known FlowGuard routes remain handoff hints,
not a closed taxonomy of all allowed angles.

## Goals / Non-Goals

**Goals:**

- Let agents freely name candidate model angles without choosing from a fixed
  lens enum.
- Require enough rationale to review what the current model sees, what it may
  miss, and what failure would be missed if the angle is ignored.
- Make each candidate angle end in a concrete disposition: reuse, extend, create
  new model, add child model, scope out, defer, or human review.
- Integrate with ExistingModelPreflight, SummaryReport, MaintenanceScan,
  ClosureContract, and RiskEvidenceLedger without creating a new runner.
- Add compact AI guidance and examples that teach open-ended reflection rather
  than checklist completion.

**Non-Goals:**

- Do not add a fixed `lens_type` taxonomy for field, information-flow,
  authority-flow, or other known examples.
- Do not make FlowGuard infer domain semantics or automatically create models.
- Do not make MaintenanceScan run owner routes or validate owner-route evidence.
- Do not require trivial copy edits or formatting-only work to produce
  deliberation rows.
- Do not replace FieldLifecycleMesh, ModelMaturation, ModelMesh,
  Model-Test Alignment, DevelopmentProcessFlow, or ClosureContract.

## Decisions

1. **Use free-form model-angle rows, not a closed enum.**

   `ModelAngleDeliberation.angle_name` is plain text. Optional `owner_route_hint`
   maps to existing FlowGuard routes when the agent can identify an owner, but
   the route hint is not the angle itself.

   Alternative considered: `lens_type` enum. Rejected because it would recreate
   the failure mode where agents complete a checklist instead of thinking about
   the current feature.

2. **Add an additive helper module.**

   New `model_angle_deliberation.py` owns constants, dataclasses,
   `review_model_angle_deliberations(...)`, report formatting, and JSON export.
   It remains a helper/route group, not core Explorer semantics.

   Alternative considered: fold rows directly into ExistingModelPreflight.
   Rejected because the reflection object is useful in templates, risk ledger
   rows, and future project adapters without requiring preflight construction.

3. **Integrate through ExistingModelPreflight as the normal hot path.**

   ExistingModelPreflight gains `model_angle_review_required`,
   `model_angle_deliberations`, and `model_angle_gap_ids`. Full preflight blocks
   or scopes claims when required reflection is absent, unexplained, stale, or
   unresolved.

   Alternative considered: add a standalone mandatory route before preflight.
   Rejected because it would create another top-level gate and increase AI
   route-selection burden.

4. **Use existing reports and route handoffs.**

   SummaryReport and MaintenanceScan recognize model-angle findings and route
   them to existing owner routes such as ModelMaturation, ModelMesh,
   Code Structure, AgentWorkflowRehearsal, or DevelopmentProcessFlow. The
   unresolved angle remains visible until owner-route evidence is attached.

5. **Make broad claims consume evidence, not prose.**

   ClosureContract and RiskEvidenceLedger receive model-angle review evidence
   ids and confidence. Missing, stale, scoped, or blocked evidence downgrades or
   blocks full claims.

6. **Teach examples without making examples exhaustive.**

   Docs and skills may mention examples such as ACK settlement vs output
   completion, PromptStore as behavior input, observer vs scheduler state, or
   old packet disposition. They must explicitly state that these are examples
   and not the complete list of valid angles.

## Risks / Trade-offs

- [Risk] Agents may write vague angle names without actionable content.
  -> Mitigation: required fields include current-model view, missed view,
  ignored-failure risk, candidate action, and evidence/open-question handling.

- [Risk] The helper becomes another mandatory checklist.
  -> Mitigation: it is required only when the task is non-trivial or broad
  confidence is claimed; angle names remain free-form; known route hints are
  optional.

- [Risk] Agents may scope out difficult angles too easily.
  -> Mitigation: scope-out and defer dispositions require a reason; required
  broad claims with unresolved or unjustified rows are blocked or scoped.

- [Risk] New report fields could be treated as validation.
  -> Mitigation: docs and tests state that deliberation is reasoning evidence,
  not owner-route validation. Owner-route checks still need current proof.

## Migration Plan

1. Add OpenSpec delta specs and the new helper module with focused unit tests.
2. Add route-scoped API exports and public template command.
3. Integrate rows into ExistingModelPreflight review and tests.
4. Add summary/maintenance scan handoff handling.
5. Add closure/risk evidence consumption.
6. Update docs, skills, AGENTS snippet, changelog, and version records.
7. Add a FlowGuard self-model with correct and broken variants.
8. Run focused tests, self-model checks, OpenSpec validation, project audit,
   broader regression, editable install sync, shadow workspace verification, and
   local git sync.

Rollback is local and additive: remove the new helper module, fields, template,
docs, OpenSpec deltas, tests, and public exports. Existing FlowGuard routes
should continue to behave as before.

## Open Questions

None blocking implementation. If implementation exposes a conflict with a
recent parallel change, preserve the peer change and adapt this additive layer
around the current public API rather than reverting it.

## Context

FlowGuard already has model-mesh concepts for parent/child boundaries,
sibling-overlap review, budgeted model groups, long-check evidence, and
model-miss generalization. The missing contract is what happens after a child
model's boundary changes: parent partition maps and sibling overlap decisions
can remain green even though the child now owns, drops, widens, narrows, or
moves a risk boundary.

This change treats a child boundary change as a first-class diff that must be
propagated before parent freshness, sibling independence, and release-readiness
claims remain valid. It also makes the bug-class target explicit: the observed
bug instance is holdout evidence, while model precision is judged against the
generalized responsibility boundary for that bug class.

## Goals / Non-Goals

**Goals:**

- Capture boundary diffs for child models across functions, state fields, side
  effects, invariants, contracts, risk classes, and validation evidence.
- Propagate those diffs into parent partition maps and only the sibling models
  whose declared boundaries intersect the changed responsibility.
- Mark parent, sibling, and release-readiness evidence stale until affected
  boundaries are reconciled or explicitly escalated.
- Keep known bug instances as holdout or validation evidence, not as the model
  target.
- Measure model precision against the bug-class responsibility boundary that
  the model is meant to own.
- Route large or slow propagated checks through existing ModelMesh, Budgeted
  model-group, and LongCheck conventions without weakening required evidence.

**Non-Goals:**

- Do not automatically rewrite parent or sibling model code.
- Do not merge child graphs into parent graphs.
- Do not treat the known bug instance as sufficient model coverage.
- Do not add a new large-check runner beyond the existing budgeted and
  long-check governance paths.
- Do not add third-party dependencies.

## Decisions

1. Represent propagation input as a semantic boundary diff.

   A boundary diff records the old and new child boundary snapshots plus change
   kinds such as `added`, `removed`, `narrowed`, `widened`, and `moved`.
   Rationale: downstream review needs to know which ownership dimensions
   changed, not just that a model file changed. Alternative considered: mark the
   entire parent hierarchy stale on any child edit. That is simpler but causes
   broad reruns and still does not explain which sibling responsibilities are
   affected.

2. Keep propagation as a ModelMesh governance layer.

   Parent and sibling propagation should review partition maps, ownership
   intersections, freshness, and evidence authority. It should not change core
   `Explorer` semantics. Rationale: boundary propagation is architectural
   governance, while exploration remains model execution. Alternative
   considered: teach each model runner to discover and notify neighbors
   directly. That would couple executable models to repository topology and
   make local isolated model runs harder.

3. Reconcile parent partition maps before trusting parent claims.

   A parent stays stale when a child diff affects parent-owned coverage,
   child-owned coverage, shared-kernel coverage, or unmapped coverage. The
   parent must either update its partition map, declare an explicit escalation,
   or record why no parent claim is affected. Rationale: the parent is the
   source of hierarchy coverage authority. Alternative considered: allow child
   evidence to supersede parent maps automatically. That can hide coverage
   gaps and parent/child disagreement.

4. Recheck siblings by declared boundary intersection.

   Sibling review should target siblings whose function, state, side-effect,
   invariant, contract, or risk-class declarations intersect the propagated
   diff. Rationale: this catches duplicate ownership and handoff drift without
   rerunning unrelated siblings. Alternative considered: always review all
   siblings after every child diff. That is conservative but too expensive for
   large meshes.

5. Separate bug-class responsibility from bug-instance holdout evidence.

   The model target is the generalized same-class responsibility boundary. The
   observed bug instance is retained as holdout or validation evidence and can
   fail the model if the generalized class does not cover it, but it cannot be
   the only represented target. Rationale: this prevents point-fix-only models.
   Alternative considered: require the observed bug plus one extra scenario but
   leave ownership undefined. That still allows the model to cover examples
   without proving the responsible boundary.

6. Escalate slow or large propagation checks to existing heavy-check paths.

   If propagation invalidates a large parent, many siblings, or a budgeted run,
   the required evidence must be managed through ModelMesh split decisions,
   Budgeted model-group ledgers, and LongCheck log conventions. Incomplete
   shards or missing long-check exit evidence remain incomplete. Rationale:
   runtime cost should change execution strategy, not the proof standard.
   Alternative considered: allow a lightweight propagation note to replace a
   slow rerun. That would make large models less trustworthy precisely where
   propagation risk is highest.

## Risks / Trade-offs

- [Risk] Boundary diffs can be incomplete or hand-written inaccurately. ->
  Mitigation: require old/new ownership dimensions, evidence fingerprints
  where practical, and an explicit stale finding when a diff cannot be trusted.
- [Risk] Targeted sibling invalidation can miss an undeclared overlap. ->
  Mitigation: treat undeclared or unknown ownership as parent-stale and require
  parent reconciliation before green continuation.
- [Risk] Bug-class boundaries can be overbroad and make models expensive. ->
  Mitigation: allow the mesh to split responsibility into child models, shared
  kernels, or budgeted runs while keeping the class boundary explicit.
- [Risk] Heavy propagated checks can remain incomplete for a long time. ->
  Mitigation: report incomplete evidence as incomplete, include long-check log
  paths and exit codes, and avoid release-ready claims until the required
  evidence is complete or explicitly scoped out.

## Migration Plan

1. Add model boundary diff structures and examples for old/new boundary
   snapshots.
2. Add parent propagation review and stale-evidence reporting.
3. Add sibling intersection review for overlap, duplicate ownership, handoff,
   and shared-read cases.
4. Add bug-class responsibility and holdout evidence fields to model-miss
   guidance and examples.
5. Connect large or slow propagation checks to ModelMesh, Budgeted model-group,
   and LongCheck reporting conventions.
6. Add focused tests and docs, then prepare normal release notes and version
   metadata when implementation work is performed.

Rollback is documentation and helper-level only for the first implementation:
callers can stop using the new propagation review and keep existing model-mesh
and model-miss workflows.

## Open Questions

- None for this proposal. Implementation can choose exact helper API names
  while preserving the requirements in the spec.

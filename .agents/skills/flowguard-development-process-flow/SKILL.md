---
name: flowguard-development-process-flow
description: Use for any non-trivial staged development or modification task where step ordering, touched artifacts, validation evidence, evidence freshness, peer writes, or minimum revalidation affects whether the agent can safely continue or claim done; also use for release, archive, or publish confidence that depends on current evidence.
---

# FlowGuard Development Process Flow

This is a standalone FlowGuard satellite skill for staged development
lifecycle and validation freshness questions. Use it directly when non-trivial
work has multiple meaningful development or modification stages and validation,
or when the risk is "does the process order still support the
done/release/archive/publish claim?"

Return to `model-first-function-flow` when the basic FlowGuard route is
unclear or when the task needs broader modeling before lifecycle evidence can
be judged.

Skip only for truly single-step work with no meaningful validation or artifact
freshness risk, such as a tiny typo fix, pure explanation, or formatting-only
change.

## Hard Gates

- Verify the real package before claiming FlowGuard use:
  `python -c "import flowguard; print(flowguard.SCHEMA_VERSION)"`.
- Do not create a fake mini-framework or prose-only substitute.
- Model process blocks as `Input x State -> Set(Output x State)` when the
  lifecycle risk needs executable checking.
- Skipped, stale, progress-only, or not-run validation is not a pass.
- Failed validation must be triaged before further implementation or done
  claims. Do not push through a failure until it is classified as ordinary
  implementation defect, model too thick, test/check too thick, model-test
  mismatch, stale evidence, or parent/child evidence not reattached.
- If staged work accumulates repeated handlers, adapters, phases, branches, or
  validation layers around the same behavior, route to
  `flowguard-architecture-reduction` before adding more structure or claiming
  done/release.
- Preserve user and peer-agent changes; later writes can stale earlier
  evidence.
- Edits to model boundaries, code contracts, input gates, output mappers, error
  mappers, state writers, or side-effect wrappers stale code-boundary
  conformance evidence for the affected surface.
- Edits to model-miss classifications, same-class generalized cases, required
  closure evidence roles, recurring defect-family gates, or tests used as
  closure proof stale prior Model-Test Alignment, Risk Evidence Ledger, and
  release/done confidence for that repaired obligation.
- Edits to parent/child partitioning stale parent coverage and child
  disjointness evidence. Edits to child inputs, outputs, state ownership, side
  effects, contracts, or evidence ids stale child reattachment evidence. Edits
  to leaf input gates, output mappers, state writers, side effects, or errors
  stale the affected leaf boundary-matrix cells.
- Before broad done/release/archive/publish confidence, run automatic split
  diagnostics for direct model/test evidence that is oversized, incomplete,
  slow, broad, progress-only, or release-only. Required splits route to the
  existing ModelMesh or TestMesh gate; they are not a new skill route.

## Workflow

1. List planned lifecycle stages and artifacts: requirements, models, code,
   tests, prompts, docs, install surfaces, tags, release records, and generated
   assets.
2. Record which validations cover which artifact versions.
3. Identify later actions that can overwrite, stale, or narrow earlier
   evidence.
4. Use `review_development_process_flow(...)` or the template to derive the
   minimum revalidation plan.
5. After any failed, stale, skipped, oversized, or ambiguous validation result,
   record a failure triage before continuing:
   ordinary implementation defects may continue through the normal fix path;
   model-too-thick or oversized model evidence routes to ModelMesh;
   test-too-thick, slow/layered, skipped, stale, or release-only validation
   evidence routes to TestMesh; model/test obligation mismatch routes to
   Model-Test Alignment; disconnected parent/child evidence routes back to the
   owning parent evidence gate.
6. For direct model/test evidence with state counts, pending states, long
   durations, broad obligation coverage, background progress-only logs, or
   release-only scope, run `review_auto_mesh_splits(...)` and include the
   ModelMesh/TestMesh split gate in the minimum revalidation plan.
7. Treat sibling route evidence ids as inputs only; do not inspect or
   supervise sibling route internals.
8. Before implementation and again before done/release/archive/publish, check
   whether complexity-growth signals require Architecture Reduction: repeated
   adapters, duplicated branch handling, duplicate validation paths, or a
   smaller target architecture than the current code graph.
9. Include code-boundary conformance in the minimum revalidation plan when the
   touched artifact affects finite model-backed inputs or outputs.
10. Include Model-Test Alignment in the minimum revalidation plan when a
   model-miss repair changes the model obligation or the observed/same-class
   test evidence used for closure. Mark pre-repair evidence as stale or
   overclaimed when it only proved the observed bug.
11. Include TestMesh in the minimum revalidation plan when same-class
   validation is large, slow, layered, background, or release-only.
12. Include the recurring defect-family gate and Risk Evidence Ledger in the
   minimum revalidation plan when the same-class miss recurs or is high risk.
13. Include layered boundary proof in the minimum revalidation plan when the
   touched artifact affects parent coverage, child disjointness, child
   reattachment, or leaf boundary matrices.
14. Before done/release/archive/publish, verify the final evidence is current
   for the final artifact set.
15. Before final done/release/archive/publish, consume the Risk Evidence Ledger
   decision as an evidence boundary: full confidence may continue, scoped
   confidence must be reported as scoped, and blocked findings must route back
   to the owning evidence route.
16. For non-trivial lifecycle reviews, default to a user-facing Mermaid
   development process diagram showing artifact versions, action writes/invalidations,
   evidence ids, freshness gates, minimum revalidation, and unsupported claims.
   This diagram's edges mean order, invalidation, or required revalidation, not
   product behavior. Tiny single-step work may stay concise. The diagram
   explains the process model and does not count as validation.

## Owned Helpers

- `review_development_process_flow(...)`
- `derive_revalidation_plan(...)`
- `python -m flowguard development-process-flow-template --output .`

## Non-Goals

- Do not replace ModelMesh, TestMesh, StructureMesh, Architecture Reduction,
  Model-Test Alignment, LongCheck, or Conformance Adoption.
- Do not mark background progress as completion.
- Do not convert helper APIs or templates into Codex skills.

For detailed route rules, read
`references/development_process_flow_protocol.md`.

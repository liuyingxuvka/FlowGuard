## Context

The satellite skills already exist globally. The remaining issue is the
top-level routing contract: global AGENTS still says to use
`model-first-function-flow` before non-trivial software work, so the model often
selects the kernel even when a more specific satellite skill clearly matches.

## Goals / Non-Goals

**Goals:**

- Make global FlowGuard route selection a peer-skill table.
- Prefer direct satellite skills when the route is clear.
- Keep `model-first-function-flow` as a useful kernel for generic modeling,
  unclear routes, and cross-route coordination.
- Keep all hard gates: real FlowGuard package, executable evidence over prose,
  skipped/stale/not-run checks are not passes, and peer changes can stale
  evidence.
- Keep prompt and skill guidance synchronized across global, repository, and
  shadow workspace copies.

**Non-Goals:**

- Do not change public Python APIs.
- Do not remove `model-first-function-flow`.
- Do not force FlowGuard for trivial copy edits, formatting-only work, or pure
  explanations.
- Do not make one satellite skill a parent or supervisor of the others.

## Decisions

1. **Global AGENTS becomes the first router.**
   The global prompt will first decide whether FlowGuard applies, then select
   the most specific installed FlowGuard skill.

2. **Satellite routes are peers.**
   DevelopmentProcessFlow, UI Flow Structure, Code Structure Recommendation,
   Model-Test Alignment, TestMesh, StructureMesh, ModelMesh, and Model-Miss
   Review are all directly selectable global skills.

3. **The kernel handles uncertainty and ordinary modeling.**
   `model-first-function-flow` remains the route for ordinary behavior/state
   model-first work, route ambiguity, multiple applicable routes, and cases
   where a core model is needed before narrowing.

4. **Route priority is tested as prompt contract.**
   Tests will verify route-table text and sample route expectations so future
   edits cannot silently reintroduce model-first as the universal first stop.

## Risks / Trade-offs

- **Risk: prompt becomes too long.** Mitigation: keep the global table compact
  and point detailed route behavior to installed skills.
- **Risk: direct satellite over-triggering.** Mitigation: each satellite row
  still requires a clear match, while ambiguous or cross-route work falls back
  to the kernel.
- **Risk: installed prompt drifts from repository docs.** Mitigation: sync
  global AGENTS, installed skills, source checkout, and shadow workspace, then
  verify hashes and focused tests.

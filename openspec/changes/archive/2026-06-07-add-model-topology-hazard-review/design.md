# Design

## Route

OpenSpec owns the product behavior change. FlowGuard owns the executable
confidence boundary:

- Existing model preflight: reuse current FlowGuard model ownership before
  creating a parallel route.
- Model-first kernel: add topology-hazard review after automatic state closure
  in `run_model_first_checks(...)`.
- Model Topology Hazard Review: infer a topology digest from the model shape
  and usage intent, then review anchored hazard candidates.
- DevelopmentProcessFlow: treat code, docs, tests, install, shadow sync, skill
  sync, and git version as ordered evidence-bearing actions.

## Behavior

The review has three layers:

1. `UsageIntent` records how the project is expected to be used: local, CLI,
   library, plugin, service, release, migration, final claim scope, old history
   possibility, and compatibility policy.
2. `TopologyDigest` records model shape: states, inputs, blocks, workflow
   edges, state writes, side effects, external boundaries, compatibility paths,
   and landmarks.
3. `TopologyHazardCandidate` records a future-use hazard only if it can name a
   topology anchor and a required disposition.

Unanchored AI concerns are observations. They can be displayed, but they cannot
block confidence. Anchored unresolved hazards can scope or block confidence
depending on usage intent and required disposition.

## Default Integration

`run_model_first_checks(...)` always appends a `topology_hazard` section.

- If the caller provides a `TopologyHazardReviewPlan`, that explicit plan is
  reviewed.
- Otherwise FlowGuard infers a digest and candidates from the workflow,
  initial states, external inputs, and optional `UsageIntent`.
- Broad usage or broad final claims make repeatable side-effect and unknown
  compatibility hazards blocking until handled or scoped with evidence.
- Scoped gaps remain visible as `pass_with_gaps`; blockers make the section
  blocked.

## Prompt Integration

The Codex skill should ask the AI to read the model topology first, not recite
fixed categories such as concurrency or scale. The prompt should require each
hard candidate to explain:

- which topology anchor caused the concern;
- how that shape could fail in future real use;
- which state, edge, side effect, terminal, legacy path, or external boundary
  is affected;
- which route must own the resolution or evidence.

## Non-Goals

- Do not add an optional AI pack that agents can ignore.
- Do not run an LLM inside the `flowguard` Python package.
- Do not let generic risk warnings become hard gates without topology anchors.
- Do not replace Model-Test Alignment, Model Maturation, Architecture
  Reduction, DevelopmentProcessFlow, or Risk Evidence Ledger.

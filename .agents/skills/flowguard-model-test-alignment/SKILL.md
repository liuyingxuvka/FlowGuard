---
name: flowguard-model-test-alignment
description: Use when FlowGuard obligations, transition cells, tests, code contracts, source audits, or code-boundary observations need direct comparison without ModelMesh, TestMesh, or StructureMesh.
---

# FlowGuard Model-Test Alignment

Standalone FlowGuard satellite skill for comparing obligations, transition
cells, tests, owner code contracts, source audits, boundary observations, and
FieldLifecycleMesh projections. Consume Model Similarity handoffs for
shared/variant tests.

Return to `model-first-function-flow` when obligations are undefined. Do not invoke TestMesh, ModelMesh, or StructureMesh from this route.

## First Read

- Route id: `model_test_alignment`.
- Default entry: `ROUTE_STARTER_API["model_test_alignment"]` and
  `model-test-alignment-template`.
- Full entry: `model-test-alignment-full-template` for source audit, boundary
  conformance, state closure, transition matrices, or reused test evidence.
- Core helpers: `review_model_test_alignment()`, `TransitionCoverageMatrix`,
  `transition_coverage_to_model_obligations()`, and `CodeContract`.
- Similarity handoff: cite maintenance group ids plus shared/variant test
  obligation ids when claiming similar workflows are covered.
- Reference: `references/model_test_alignment_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- Keep the AGENTS.md managed block/version record current for real projects.
- Do not create a fake mini-framework.
- Tests must cover declared obligations, not just helper/internal paths.
- Full confidence requires each obligation to bind an owner `CodeContract` and
  current external-contract test evidence. Model+test-only evidence is scoped.
- Transition coverage claims need cells plus evidence targets, or a scoped-out boundary.
- Behavior-bearing fields need FieldLifecycleMesh projection or a scoped-out reason.
- Reused test results need `result_reused=True`, current `TestResultReuseTicket`, and current `ProofArtifactRef`.
- Source audit is conservative support, not semantic proof.
- Open external boundaries must expose representative unknown/other cases or a
  current state-closure report; unresolved cases route to model maturation.
- Missing evidence becomes a maintenance obligation.

## Minimum Workflow

1. List obligations, scenarios, invariants, hazards, transitions, and field projections.
2. Project transition matrices into obligations when transition-test coverage is claimed.
3. Add owner external code contracts, finite boundary observations, and
   test evidence that covers the same code contract ids.
4. Compare binding rows, classify gaps, and route split needs outward.

## Snapshot

Show coverage from model obligations to code contracts to tests, boundary
observations, missing inputs/outputs/state writes, and scoped gaps.

## Non-Goals

- Do not split tests, code, or models.
- Do not replace conformance replay for production-facing validation.

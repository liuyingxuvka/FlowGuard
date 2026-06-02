---
name: flowguard-model-test-alignment
description: Use when FlowGuard obligations, transition cells, tests, required code contracts, source audits, or code-boundary observations need direct comparison without ModelMesh, TestMesh, or StructureMesh.
---

# FlowGuard Model-Test Alignment

Standalone FlowGuard satellite skill for comparing model obligations, transition
cells, ordinary tests, required owner code contracts, source audits, and finite
code-boundary observations.
Consume Model Similarity handoffs when shared/variant tests matter.

Return to `model-first-function-flow` when the model obligations are not yet
defined. Do not invoke TestMesh, ModelMesh, or StructureMesh from this route.

## First Read

- Route id: `model_test_alignment`.
- Core helpers: `review_model_test_alignment()`, `TransitionCoverageMatrix`,
  `transition_coverage_to_model_obligations()`, `CodeContract`.
- Similarity handoff: cite maintenance group ids plus shared/variant test
  obligation ids when claiming similar workflows are covered.
- Reference: `references/model_test_alignment_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- Keep the AGENTS.md managed block/version record current for real projects.
- Do not create a fake mini-framework.
- Tests must cover declared obligations, not just helper/internal paths.
- Full confidence requires each required model obligation to bind an owner
  `CodeContract` and current external-contract test evidence for the same
  obligation. Model+test-only evidence is blocked or scoped, not green.
- Transition coverage claims need cells plus evidence targets, or a scoped-out boundary.
- Reused test results need `result_reused=True`, current `TestResultReuseTicket`, and current `ProofArtifactRef`.
- Source audit is conservative support, not semantic proof.
- Open external boundaries must expose representative unknown/other cases or a
  current state-closure report; unresolved cases route to model maturation.
- Missing evidence can become future maintenance obligations.

## Minimum Workflow

1. List obligations, scenarios, invariants, hazards, and transitions.
2. Project transition matrices into obligations when transition-test coverage is claimed.
3. Add owner external code contracts, finite boundary observations, and
   test evidence that covers the same code contract ids.
4. Compare binding rows, classify gaps, and route split needs outward.

## Snapshot

Show coverage from model obligations to code contracts to tests, boundary
observations, missing inputs/outputs/state writes, and scoped gaps.
When drawing the snapshot, edges mean covers, partially covers, observes, misses, or requires additional evidence.

## Non-Goals

- Do not split tests, code, or models.
- Do not replace conformance replay for production-facing validation.

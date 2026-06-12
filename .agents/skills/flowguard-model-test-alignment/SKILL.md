---
name: flowguard-model-test-alignment
description: Use when FlowGuard obligations, tests, code contracts, or source audits need direct comparison.
---

# FlowGuard Model-Test Alignment

Standalone FlowGuard satellite skill for obligations, tests, owner `CodeContract`s, source audits, boundary observations, payload evidence, and FieldLifecycleMesh projections.

Return to `model-first-function-flow` when obligations are undefined. Do not invoke TestMesh, ModelMesh, or StructureMesh from this route.

## First Read

- Route id: `model_test_alignment`.
- Starter: `ROUTE_STARTER_API["model_test_alignment"]` and `model-test-alignment-template`.
- Full: `model-test-alignment-full-template` for source audit, boundary conformance, state closure, matrices, or reused test evidence.
- Helpers: `review_model_test_alignment()`, `TransitionCoverageMatrix`, `CodeContract`, `ArtifactPayloadContract`.
- Similarity handoff: cite group ids plus shared/variant test obligations for similar workflow coverage claims.
- Reference: `references/model_test_alignment_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- Keep AGENTS.md managed records current for real projects.
- Do not create a fake mini-framework.
- Tests cover declared obligations, not just helper/internal paths.
- Full confidence requires each obligation to bind an owner `CodeContract` and current external-contract test evidence.
- Transition coverage claims need cells plus evidence targets, or a scoped-out boundary.
- Behavior-bearing fields need FieldLifecycleMesh projection or a scoped-out reason.
- Reused results need `result_reused=True`, current `TestResultReuseTicket`, and current `ProofArtifactRef`.
- File/import/export/artifact/work-package claims need `ArtifactPayloadContract` cases plus real-surface payload evidence with execution proof refs.
- Manual payload checks need structured case/result/evidence refs, not prose.
- Source audit is conservative support, not semantic proof.
- Open external boundaries need unknown/other cases or current state-closure; unresolved cases route to model maturation.
- Missing evidence becomes a maintenance obligation.
- For new/deepened obligations, record template harvest closure before broad claims.

## Minimum Workflow

1. List obligations, scenarios, invariants, hazards, transitions, and field projections.
2. Project transition matrices into obligations when transition-test coverage is claimed.
3. Add owner external code contracts, finite boundary observations, and same-contract test evidence.
4. Add synthetic payload cases that exercise the real file/work-package surface.
5. Compare binding rows, classify gaps, and route split needs outward.

## Snapshot

Show coverage from model obligations to code contracts to tests, boundary observations, missing I/O/state writes, and scoped gaps.

## Non-Goals

- Do not split tests, code, or models.
- Do not replace conformance replay for production-facing validation.

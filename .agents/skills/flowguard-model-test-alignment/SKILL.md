---
name: flowguard-model-test-alignment
description: Use when a FlowGuard model's obligations, optional externally visible code contracts, code-boundary runtime observations, and ordinary test evidence need direct comparison. Triggers include model-test alignment, missing test coverage for model scenarios or invariants, code contract evidence, code-boundary conformance evidence, Python source/test assertion audit, or checking whether tests actually cover FlowGuard obligations without invoking ModelMesh, TestMesh, or StructureMesh.
---

# FlowGuard Model-Test Alignment

Standalone FlowGuard satellite skill for comparing model obligations against
ordinary tests, optional code contracts, source/test assertion audits, and
finite code-boundary observations.

Return to `model-first-function-flow` when the model obligations are not yet
defined. Do not invoke TestMesh, ModelMesh, or StructureMesh from this route.

## First Read

- Route id: `model_test_alignment`.
- Core helpers: `review_model_test_alignment()`, `CodeContract`,
  `PythonCodeContractEvidence`, `PythonTestAssertionEvidence`.
- Reference: `references/model_test_alignment_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- For real target-project work, keep the AGENTS.md managed block/version record
  current or record why it was not updated.
- Do not create a fake mini-framework.
- Tests must cover declared obligations, not just helper/internal paths.
- Source audit is conservative support, not semantic proof.

## Minimum Workflow

1. List model obligations, scenarios, invariants, hazards, and transitions.
2. Add optional code contracts only for externally visible code surfaces.
3. Add boundary observations when finite inputs/outputs/errors/state/side
   effects must be proven.
4. Compare evidence, classify gaps, and route split needs outward.

## Snapshot

Show coverage from model obligations to tests, code contracts, boundary
observations, missing inputs/outputs/state writes, and scoped gaps.

## Non-Goals

- Do not split tests, code, or models.
- Do not replace conformance replay for production-facing validation.

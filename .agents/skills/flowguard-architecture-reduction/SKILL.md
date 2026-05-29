---
name: flowguard-architecture-reduction
description: Use when a FlowGuard model should drive behavior-preserving code architecture simplification, including shrinking overgrown flows, merging duplicate handlers/modules, collapsing pass-through adapters, removing dead branches or irrelevant state, and producing a StructureMesh-ready contraction plan before editing production code.
---

# FlowGuard Architecture Reduction

Standalone FlowGuard satellite skill for model-backed contraction. Use it when
existing code, prompt, or workflow structure appears reducible while observable
behavior must stay unchanged.

Return to `model-first-function-flow` when the model is unclear. Hand exact
production refactors to Code Structure Recommendation, StructureMesh, and
DevelopmentProcessFlow as needed.

## First Read

- Route id: `architecture_reduction`.
- Contract first: public entrypoints, outputs, observable state, side effects,
  validation boundaries, and rationale.
- Classify contraction candidates with proof status and required next route.
- Core helpers: `ObservableArchitectureContract`,
  `ArchitectureReductionCandidate`, `review_architecture_reduction()`.
- Reference: `references/architecture_reduction_protocol.md`.

## Hard Gates

- Verify the real package before claiming FlowGuard use.
- For real target-project work, keep the AGENTS.md managed block/version record
  current or record why it was not updated.
- Do not create a fake mini-framework.
- Every contraction candidate needs proof status and required next route.
- Public entrypoints require StructureMesh or equivalent parity evidence.

## Minimum Workflow

1. Ground existing model ownership and duplicate-boundary risks.
2. Declare the observable contract.
3. Map FunctionBlock, state, side effect, and public entrypoint ownership.
4. Classify candidates as merge, collapse, remove, keep facade, or review.
5. Separate ready, scoped, risky, and blocked candidates.

## Snapshot

Show current boundary, model boundary, observable contract, contraction
candidates, proof status, target action, and required next route.

## Non-Goals

- Do not rewrite production code directly.
- Do not delete compatibility facades from property-only evidence.
- Do not hide skipped or stale conformance evidence.

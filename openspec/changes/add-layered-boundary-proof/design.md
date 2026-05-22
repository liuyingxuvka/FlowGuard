## Context

FlowGuard already has separate routes for parent/child models (ModelMesh),
model-to-test alignment, TestMesh evidence hierarchy, and development-process
freshness. The missing contract is the proof chain between them: a parent can
consume child evidence, but there is no single structured review that proves
the children cover the parent, avoid illegal overlap, reattach current evidence,
and bottom out in leaf boundaries that are completely exercised.

This change introduces layered boundary proof as the connective route evidence.
It stays small and standard-library only. It does not execute tests or inspect
source; project adapters still collect model/test/code evidence and pass the
structured rows into FlowGuard.

## Goals / Non-Goals

**Goals:**
- Make the four proof tables first-class: parent coverage, child disjointness,
  child reattachment, and leaf boundary matrix coverage.
- Provide a helper API that can fail parent confidence when any table has an
  unknown, stale, skipped, overlapping, or too-large leaf boundary.
- Update skill and protocol guidance so agents know when to route to ModelMesh,
  Model-Test Alignment, TestMesh, StructureMesh, Architecture Reduction, and
  DevelopmentProcessFlow.
- Add tests, templates, docs, adoption records, and release notes for the new
  proof contract.

**Non-Goals:**
- Do not force every parent model to inline all child states.
- Do not run pytest, replay adapters, or source audits inside the proof helper.
- Do not make brute-force Cartesian tests mandatory for large/non-finite
  domains; such models must be split further or explicitly scoped.
- Do not remove existing ModelMesh, TestMesh, or Model-Test Alignment APIs.

## Decisions

1. **Add a new layered proof helper instead of overloading ModelMesh.**
   ModelMesh still owns model hierarchy and target splits. The layered helper
   consumes ModelMesh-like child facts plus leaf matrix evidence and produces a
   final proof-chain report. This avoids making ModelMesh responsible for real
   code boundary observations.

2. **Represent leaf coverage as matrix cells.**
   Each `LeafBoundaryMatrixCell` names `input_case`, `state_case`, expected
   outputs, next states, state writes, side effects, error paths, evidence ids,
   and evidence status. Missing or non-current cells block leaf confidence.

3. **Keep overlap strict by default.**
   A parent responsibility can have one child owner unless the overlap is
   explicitly marked as an allowed shared kernel/bridge. Illegal overlap blocks
   parent confidence and may route to Architecture Reduction.

4. **Use evidence ids, not raw test execution, for parent consumption.**
   Parent reattachment records which child evidence id it consumed. Changed or
   stale child evidence invalidates the parent until the consumed id is current.

5. **Expose both routine and release evidence boundaries in docs.**
   TestMesh continues to own routine/release split and background completion.
   Layered proof reports should not treat progress-only or release-only evidence
   as ordinary leaf coverage.

## Risks / Trade-offs

- **Risk:** The new helper duplicates some ModelMesh checks.  
  **Mitigation:** Keep it as a chain-level proof aggregator and update docs to
  say ModelMesh still owns split derivation and child model structure.

- **Risk:** Users may misread leaf full coverage as impossible for rich domains.  
  **Mitigation:** Require split-further or explicit scoped/exempted status
  rather than pretending large leaves are green.

- **Risk:** Public API grows.  
  **Mitigation:** Add narrow dataclasses and exports, plus API-surface tests and
  docs so the surface is discoverable.

- **Risk:** Release could publish local-only state.  
  **Mitigation:** Run existing tests, OpenSpec validation, install/shadow sync,
  adoption logging, git status/privacy checks, and publish through the release
  flow.

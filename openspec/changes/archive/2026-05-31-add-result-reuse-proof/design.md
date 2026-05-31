## Context

FlowGuard already has two relevant evidence concepts:

- `ModelReuseTicket` proves an unchanged model can reuse previous model output.
- `ProofArtifactRef` proves an evidence row is backed by a concrete validation
  result artifact rather than a declaration-only status.

Test evidence currently has freshness and result-status fields, and
Model-Test Alignment can require proof artifacts in strict mode. The missing
piece is a first-class way to say: this test result is old, and here is the
current proof that the old result is still valid for the current command,
source, tested artifacts, dependencies, environment, result artifact, and
coverage scope.

## Goals / Non-Goals

**Goals:**

- Add a public test-result reuse ticket API.
- Require reused test evidence to have a valid reuse ticket and concrete proof
  artifact before it supports TestMesh or Model-Test Alignment confidence.
- Keep model result reuse and test result reuse conceptually aligned without
  merging them into one overloaded data type.
- Update docs, templates, skills, and tests so agents can distinguish safe
  reuse from required reruns.

**Non-Goals:**

- Do not make FlowGuard execute tests or calculate repository fingerprints by
  itself. Project adapters and runners still produce evidence.
- Do not replace `ModelReuseTicket`; model evidence reuse keeps its existing
  model-specific semantics.
- Do not turn Model-Test Alignment into TestMesh. Large validation hierarchy
  remains owned by TestMesh.

## Decisions

1. Add `TestResultReuseTicket` as a separate public dataclass.

   Rationale: model reuse and test reuse share the same principle, but test
   reuse needs test-specific fields: test command fingerprint, test source
   fingerprint, tested artifact fingerprint, dependency/environment
   freshness, previous result id, result fingerprint, and coverage scope.

   Alternative considered: reuse `ModelReuseTicket`. That would blur model
   semantics with test-run semantics and force fields like FlowGuard semantic
   freshness onto tests where they are not the owning risk.

2. Validate reused evidence through both a reuse ticket and a proof artifact.

   Rationale: the reuse ticket explains why the old result still applies; the
   proof artifact points to the actual result and its fingerprint. Either one
   alone is incomplete.

   Alternative considered: put all fields on `ProofArtifactRef`. That would
   make every proof artifact carry optional test-reuse policy fields and weaken
   the clear distinction between "result exists" and "old result is reusable".

3. Reused evidence is opt-in and explicit.

   Rationale: FlowGuard cannot infer from a plain passed row whether the result
   was freshly produced or reused. Callers that reuse old results must mark the
   row as reused and attach the ticket.

4. TestMesh and Model-Test Alignment both validate reuse, but at different
   ownership levels.

   TestMesh decides whether a child suite can support parent confidence.
   Model-Test Alignment decides whether a test evidence row covers model
   obligations or code contracts. Both must reject invalid reused evidence.

## Risks / Trade-offs

- Reuse evidence requires more fields from runners. → Mitigate with clear docs,
  templates, and focused tests that show the minimum accepted ticket.
- Callers could forget to mark old results as reused. → Mitigate by documenting
  that unchanged old test evidence must be represented with `result_reused=True`
  before claiming current confidence from old results.
- This does not compute fingerprints automatically. → Keep FlowGuard as the
  reviewer; command runners and project adapters remain responsible for
  producing fingerprints.

## Migration Plan

1. Add the new dataclass and gap-code helper.
2. Wire it into Model-Test Alignment and TestMesh.
3. Update public exports, docs, route skills, and templates.
4. Add focused unit tests for valid reuse and stale/missing proof.
5. Run focused tests, full unit regression, model regressions, install sync,
   and project adoption audit.

## Open Questions

None for this change. The default is strict: reused test results are blocked
unless both reuse ticket and proof artifact are current.

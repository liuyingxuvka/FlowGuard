## Why

FlowGuard can already decide when unchanged model evidence may be reused, but
test evidence reuse is not equally explicit. This change makes reused test
results carry the same kind of checkable proof boundary so Model-Test Alignment
and TestMesh do not treat an old `passed` result as current without proving the
test, target, dependency, result artifact, and covered obligation scope still
match.

## What Changes

- Add a reusable test-result reuse ticket that records why a previous test
  result can still support current evidence.
- Require reused test evidence to carry both a current reuse ticket and a
  current proof artifact with matching result fingerprints and obligation
  coverage.
- Extend Model-Test Alignment so reused `TestEvidence` is rejected when its
  reuse ticket, proof artifact, or coverage scope is stale or missing.
- Extend TestMesh so reused `TestSuiteEvidence` is rejected before a child
  suite can support parent confidence.
- Update route guidance, templates, docs, and tests so agents know when old
  model and test results may be reused and when they must be rerun.
- Update local install, version surfaces, project adoption records, and git
  state after validation.

## Capabilities

### New Capabilities
- `test-result-reuse-proof`: Prove when a previous test result can be reused as
  current evidence by checking command, test source, tested artifacts,
  dependencies, environment, result fingerprint, and coverage scope.

### Modified Capabilities
- `model-test-alignment`: Reject reused test evidence that lacks a current reuse
  ticket or proof artifact before it counts toward model obligation coverage.
- `test-evidence-mesh`: Reject reused child-suite evidence that lacks a current
  reuse ticket or proof artifact before it supports parent TestMesh confidence.
- `proof-artifact-bound-evidence`: Use proof artifacts as the concrete result
  artifact for reused test evidence.
- `model-impact-freshness-gate`: Keep model evidence reuse and test evidence
  reuse aligned under the same current-evidence principle.
- `development-process-flow`: Treat model/test reuse tickets as evidence that
  can be invalidated by later writes and must be included in revalidation
  planning.
- `long-check-observability`: Clarify that background model/test regressions can
  reuse old completed results only when the reuse proof is current.

## Impact

- New public API for test-result reuse tickets and gap review.
- Updates to `flowguard.model_test_alignment`, `flowguard.testmesh`, public
  exports, docs, templates, OpenSpec artifacts, and regression tests.
- No new runtime dependencies.

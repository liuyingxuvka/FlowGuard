## 1. Proof Artifact Core

- [x] 1.1 Add `ProofArtifactRef`, status helpers, and serialization in a new core module.
- [x] 1.2 Export the proof artifact API from `flowguard.__init__`.
- [x] 1.3 Add focused proof artifact tests for pass, stale, non-zero exit, missing result, scope, and obligation matching.

## 2. Strict Evidence Consumers

- [x] 2.1 Add proof artifact fields and strict-mode blockers to layered boundary proof.
- [x] 2.2 Add proof artifact fields and strict-mode blockers to Risk Evidence Ledger.
- [x] 2.3 Add proof artifact fields and strict-mode blockers to recurring defect-family gates.
- [x] 2.4 Add proof artifact fields to model-test evidence and strict alignment reporting.
- [x] 2.5 Add proof artifact fields to DevelopmentProcessFlow validation evidence and strict freshness reporting.

## 3. Legacy Path Disposition

- [x] 3.1 Add legacy path disposition dataclasses, constants, and review helper.
- [x] 3.2 Integrate legacy path disposition into model-miss and defect-family closure tests.
- [x] 3.3 Document old-path deleted, blocked, delegated, same-contract repaired, out-of-scope, and unknown outcomes.

## 4. Docs, Skills, and Templates

- [x] 4.1 Update FlowGuard docs and API surface notes for proof-artifact-bound evidence.
- [x] 4.2 Update `.agents/skills` FlowGuard skill text and references to require strict proof artifacts for full confidence.
- [x] 4.3 Update templates so generated examples show strict proof artifact binding instead of declaration-only pass rows.
- [x] 4.4 Sync installed Codex FlowGuard skills after repository validation passes.

## 5. FlowPilot Integration

- [x] 5.1 Update FlowPilot known-friction/defect-family confidence code to distinguish obligation rows from proof artifact-backed evidence.
- [x] 5.2 Add FlowPilot tests proving declaration-only `passed/current` rows cannot support full confidence.
- [x] 5.3 Avoid and preserve unrelated peer-agent changes in the FlowPilot workspace.

## 6. Version, Install, and Verification

- [x] 6.1 Bump FlowGuard package version and changelog.
- [x] 6.2 Reinstall editable FlowGuard locally and verify import/version/schema.
- [x] 6.3 Run focused FlowGuard tests for proof artifacts, layered proof, risk ledger, recurring model miss, model-test alignment, development process, and templates.
- [x] 6.4 Run broader FlowGuard regression tests, using background artifacts for long checks where practical.
- [x] 6.5 Run FlowPilot focused integration checks and background model regressions for affected confidence gates.
- [x] 6.6 Record adoption evidence and KB postflight.

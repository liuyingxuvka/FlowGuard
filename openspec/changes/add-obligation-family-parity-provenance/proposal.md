## Why

FlowGuard can currently prove that individual model obligations and tests are green, but a repaired workflow family can still overclaim confidence when one sibling route is covered and another sibling route lacks the same mechanism. This change makes FlowGuard catch same-class parity, evidence-provenance, and claim-scope gaps before a downstream project treats a narrow green check as family-wide protection.

## What Changes

- Add a reusable obligation-family parity helper that declares sibling members, shared mechanisms, required evidence provenance, and member-level exceptions.
- Add a review report that blocks missing member coverage, wrong-provenance evidence, stale or non-passing family evidence, and family-wide claims that exceed evidence scope.
- Add same-class bad-case derivation so a miss observed in one family member can generate sibling cases for the remaining members.
- Add analogous defect radius scanning so model-miss review asks where the same failure shape may recur before broad closure is claimed.
- Integrate obligation-family parity with Model-Test Alignment and Risk Evidence Ledger so existing FlowGuard confidence routes can consume the new gate.
- Add docs, public API exports, tests, and release notes for the new FlowGuard capability.

## Capabilities

### New Capabilities
- `obligation-family-parity-provenance`: Declares same-class obligation families and checks that each required member has current, correctly sourced evidence for every shared mechanism before broad confidence is allowed.

### Modified Capabilities
- `model-test-alignment`: Model-Test Alignment can consume obligation-family parity plans so a model/test/code report is blocked when sibling mechanisms or required evidence provenance are missing.
- `risk-evidence-ledger`: Risk Evidence Ledger rows can require a current family parity gate before granting full confidence.
- `post-runtime-model-miss-review`: Model-miss closure can use same-class bad-case derivation and analogous defect scans to avoid closing on the observed bug alone.

## Impact

- Adds a new public helper module under `flowguard`.
- Extends public API exports with obligation-family parity dataclasses, constants, and review helpers.
- Extends `ModelTestAlignmentPlan` and `RiskEvidenceRow` with optional family-gate fields while preserving existing defaults.
- Adds optional analogous-scan confidence fields to `RiskEvidenceRow` for final closure claims after model misses.
- Updates README, API docs, and changelog.
- No runtime dependencies are added; schema remains compatible unless the implementation discovers a reason to bump it.

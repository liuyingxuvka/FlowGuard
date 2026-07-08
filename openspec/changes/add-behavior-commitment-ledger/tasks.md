## 1. OpenSpec And Model Boundary

- [x] 1.1 Create proposal, design, spec deltas, verification contract, and task list for Behavior Commitment Ledger.
- [x] 1.2 Validate the OpenSpec change shape before implementation.
- [x] 1.3 Confirm the ledger is upstream of Primary Path Authority and does not duplicate PPA fallback logic.

## 2. Core Ledger API

- [x] 2.1 Add `flowguard/behavior_commitment.py` with commitment, source surface, PPA binding, evidence binding, report, finding, review, formatting, and export helpers.
- [x] 2.2 Add bidirectional coverage checks for missing commitments, unmapped surfaces, extra commitments, owner gaps, owner overlap, unknown dependencies, and scoped-out disposition gaps.
- [x] 2.3 Add path-sensitive checks that require PPA evidence and block on PPA blocked decisions.
- [x] 2.4 Add ContractExhaustionMesh axes, interaction groups, coverage-universe helper, and plan helper for commitment coverage.

## 3. Public API, Templates, And Docs

- [x] 3.1 Export ledger APIs from `flowguard/__init__.py` and update public API surface tests.
- [x] 3.2 Add a public ledger template and wire it through the template registry.
- [x] 3.3 Add `docs/behavior_commitment_ledger.md`, README mention, AGENTS guidance, and agents snippet guidance.
- [x] 3.4 Add `.agents/skills/flowguard-behavior-commitment-ledger/SKILL.md` with baseline ledger and change-time review workflow.

## 4. Route Integrations

- [x] 4.1 Update DevelopmentProcessFlow artifacts/gaps so broad process confidence consumes current behavior ledger coverage.
- [x] 4.2 Update RiskEvidenceLedger with a behavior-commitment coverage gate.
- [x] 4.3 Update PPA handoff helpers so path-sensitive commitments preserve PPA decisions, report ids, receipt ids, and risk gate ids.
- [x] 4.4 Update existing FlowGuard skills for model-first, existing-model preflight, development-process, model-test alignment, contract exhaustion, test mesh, and UI flow routing.

## 5. Tests And Cartesian Coverage

- [x] 5.1 Add core ledger tests for complete, missing expected, unmapped surface, source-less commitment, missing owner, owner overlap, unknown dependency, and scoped-out disposition cases.
- [x] 5.2 Add PPA integration tests for path-sensitive missing PPA, passed PPA, and blocked PPA.
- [x] 5.3 Add ContractExhaustionMesh tests covering the ledger axes and interaction groups.
- [x] 5.4 Add RiskEvidenceLedger release-gate tests for passing and blocked ledger reports.
- [x] 5.5 Update public template and API surface tests.

## 6. Validation And Synchronization

- [x] 6.1 Run focused behavior-ledger test files.
- [x] 6.2 Run affected existing PPA, template, API, risk ledger, and project audit checks.
- [x] 6.3 Run OpenSpec validation/status for this change.
- [x] 6.4 Sync installed local package and installed FlowGuard skills.
- [x] 6.5 Sync shadow workspace without reverting parallel agent work.
- [x] 6.6 Run KB postflight and record any reusable lesson.

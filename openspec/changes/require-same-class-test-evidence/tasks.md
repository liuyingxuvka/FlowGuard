## 1. Contracts and Helper Behavior

- [x] 1.1 Extend Model-Test Alignment rows with model-miss closure roles and same-class evidence requirements.
- [x] 1.2 Block point-fix-only test evidence when a model-miss obligation requires same-class closure.
- [x] 1.3 Keep overclaimed pre-repair test evidence visible as a blocker.

## 2. FlowGuard Models, Templates, and Guidance

- [x] 2.1 Update the lightweight model-miss review example so closure requires test-side same-class evidence handoff.
- [x] 2.2 Update public model-miss and model-test-alignment templates/notes to teach observed regression plus same-class test evidence.
- [x] 2.3 Update skill docs and protocol docs for model-miss, model-test-alignment, development-process-flow, and TestMesh handoff.
- [x] 2.4 Update README/API/check-plan guidance to expose the new closure rule in user-facing docs.

## 3. Tests and Validation

- [x] 3.1 Add focused tests for same-class evidence success, observed-regression-only failure, wrong-target failure, and overclaimed evidence.
- [x] 3.2 Add focused tests for public template and skill documentation coverage.
- [x] 3.3 Run OpenSpec strict validation and focused FlowGuard/tests for the touched routes.
- [x] 3.4 Run full local validation, including pytest, model examples, install sync, and shadow workspace import checks.

## 4. Release

- [x] 4.1 Update version metadata and changelog for the local release candidate.
- [x] 4.2 Sync local editable install and the `FlowGuard_20260427` shadow workspace.
- [ ] 4.3 Commit and tag the local git release candidate after the recurring-defect gate follow-up is complete. GitHub push/publish remains out of scope unless explicitly requested.

## 5. Recurring Defect-Family Gate

- [ ] 5.1 Add a recurring model-miss defect-family gate helper with promotion, proof, and scoped-confidence decisions.
- [ ] 5.2 Feed required/current/scoped defect-family gate status into Risk Evidence Ledger rows.
- [ ] 5.3 Update lightweight model-miss example and generated templates so recurring families cannot be closed as ordinary point fixes.
- [ ] 5.4 Update docs, README, API notes, and FlowGuard skills so agents know the gate belongs in FlowGuard, not downstream apps.
- [ ] 5.5 Add focused recurring-gate and ledger tests, then rerun OpenSpec strict validation, model examples, and focused route tests.
- [ ] 5.6 Sync editable install, installed skills, shadow workspace, and local git state.

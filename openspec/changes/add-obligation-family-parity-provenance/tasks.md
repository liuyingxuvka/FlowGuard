## 1. OpenSpec and model contract

- [x] 1.1 Add OpenSpec proposal, design, specs, and task checklist.
- [x] 1.2 Keep the feature generic to FlowGuard; do not encode FlowPilot-specific names.

## 2. Core helper implementation

- [x] 2.1 Add `flowguard.obligation_family` dataclasses, constants, report formatting, and `review_obligation_family_parity`.
- [x] 2.2 Add same-class bad-case seed and derivation helpers.
- [x] 2.3 Add analogous defect scan dataclasses, dispositions, radius review, and report formatting.
- [x] 2.4 Export the helper through the public FlowGuard API.

## 3. Existing route integration

- [x] 3.1 Integrate family parity into `ModelTestAlignmentPlan` and `review_model_test_alignment`.
- [x] 3.2 Integrate family gate confidence into `RiskEvidenceRow` and `review_risk_evidence_ledger`.
- [x] 3.3 Integrate analogous defect scan confidence into `RiskEvidenceRow` and `review_risk_evidence_ledger`.

## 4. Tests and docs

- [x] 4.1 Add focused unit tests for full family coverage, missing sibling coverage, wrong provenance, same-class case derivation, analogous defect scan, MTA integration, and ledger integration.
- [x] 4.2 Update README and docs for the new FlowGuard capability.
- [x] 4.3 Update changelog and version for release.

## 5. Verification and release

- [x] 5.1 Run focused tests and full practical regression.
- [x] 5.2 Sync editable local install and verify imported version.
- [ ] 5.3 Commit, tag, push, and publish a GitHub release.

## 1. OpenSpec And FlowGuard Modeling

- [x] 1.1 Validate OpenSpec artifacts for `simplify-flowguard-field-schema`.
- [x] 1.2 Add a FlowGuard model for direct field-schema contraction, including
  risk-row gates, process evidence metrics, plan-intake evidence ids, duplicate
  helper classes, and no-legacy-fallback policy.
- [x] 1.3 Run the new FlowGuard model checks before production code edits.

## 2. Risk Evidence Ledger Cleanup

- [x] 2.1 Introduce `RiskEvidenceGate` and replace route-specific gate columns
  on `RiskEvidenceRow` with `gates`.
- [x] 2.2 Update `review_risk_evidence_ledger()` to validate compact gates.
- [x] 2.3 Update risk evidence ledger templates, docs, and tests.

## 3. Development Process Flow Cleanup

- [x] 3.1 Remove large-run metric and auto-split fields from `ProcessEvidence`.
- [x] 3.2 Route split review expectations to AutoSplit/TestMesh evidence.
- [x] 3.3 Update development-process templates, docs, and tests.

## 4. Plan Intake Cleanup

- [x] 4.1 Remove duplicate mapping/source evidence field shapes from Plan
  Intake.
- [x] 4.2 Remove strict adapter fixture flags from normal mapping rows.
- [x] 4.3 Update plan-intake docs, templates, and tests.

## 5. Duplicate Helper Cleanup

- [x] 5.1 Merge duplicate blindspot helper classes in UI Flow Structure.
- [x] 5.2 Merge duplicate artifact helper classes where one canonical class is
  sufficient.
- [x] 5.3 Update exports, API docs, and API-surface tests.

## 6. Verification And Sync

- [x] 6.1 Run focused tests for changed routes and public templates.
- [x] 6.2 Run OpenSpec strict validation and FlowGuard project audit.
- [x] 6.3 Run broader unit regression and aggregate FlowGuard model regression,
  using background execution where practical.
- [x] 6.4 Sync editable local install and verify import path/version/helper
  availability.
- [x] 6.5 Sync shadow/local repository copies without deleting peer-only files,
  or record why no copy is available.
- [x] 6.6 Update adoption logs and KB postflight evidence.

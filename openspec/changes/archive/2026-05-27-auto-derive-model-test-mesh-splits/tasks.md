## 1. Specification And Model Grounding

- [x] 1.1 Create the OpenSpec proposal, design, spec, and tasks for automatic model/test split derivation.
- [x] 1.2 Verify the real FlowGuard package import before production changes.
- [x] 1.3 Inspect existing ModelMesh, TestMesh, DevelopmentProcessFlow, Risk Evidence Ledger, and target split derivation APIs.

## 2. Auto Split Helper

- [x] 2.1 Add public auto split candidate, policy, finding, report, and review helper APIs.
- [x] 2.2 Generate ModelMesh/TestMesh target split derivation recommendations when structured child/partition inputs exist.
- [x] 2.3 Add focused helper tests for small evidence, oversized model, pending budgeted model, slow/broad test, progress-only evidence, and missing target derivation.

## 3. Existing Route Integration

- [x] 3.1 Feed auto split status into DevelopmentProcessFlow done/release confidence.
- [x] 3.2 Feed required model/test split gate status into Risk Evidence Ledger rows.
- [x] 3.3 Update public templates and docs so large direct evidence becomes compatibility evidence and child evidence controls parent confidence.
- [x] 3.4 Update FlowGuard skills and agents snippet so agents route large models/tests to ModelMesh/TestMesh automatically.

## 4. Validation And Sync

- [x] 4.1 Run OpenSpec strict validation for this change.
- [x] 4.2 Run focused auto split, DevelopmentProcessFlow, Risk Ledger, ModelMesh/TestMesh, API, template, and skill-doc tests.
- [x] 4.3 Run model examples and full/background regression, inspecting final exit artifacts before claiming completion.
- [x] 4.4 Sync editable install, installed FlowGuard skills, `FlowGuard_20260427` shadow workspace, and local git/tag state.
- [x] 4.5 Record FlowGuard adoption evidence and KB postflight.

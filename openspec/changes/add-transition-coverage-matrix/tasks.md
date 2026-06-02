## 1. OpenSpec Contract
- [x] 1.1 Add proposal, design, and spec deltas for transition coverage matrix.
- [x] 1.2 Validate the change with `openspec validate add-transition-coverage-matrix --strict`.

## 2. Core Helper API
- [x] 2.1 Add transition coverage data objects and projection helpers.
- [x] 2.2 Export the new helper API from the public package surface.
- [x] 2.3 Add focused unit tests for matrix projection, scoped-out cells, and TestMesh required ids.

## 3. Route Integration
- [x] 3.1 Add Model-Test Alignment tests proving transition-derived obligations block or pass with evidence.
- [x] 3.2 Add UI projection tests from `UIInteractionModel.transitions`.
- [x] 3.3 Add TestMesh tests for transition coverage leaf-cell requirements.

## 4. Guidance Surfaces
- [x] 4.1 Update docs and template text for Model-Test Alignment, UI Flow Structure, TestMesh, modeling protocol, and check plan.
- [x] 4.2 Update FlowGuard Codex skills so agents derive transition coverage before broad test-coverage claims.

## 5. Validation and Sync
- [x] 5.1 Run focused tests for the changed modules.
- [x] 5.2 Run OpenSpec strict validation.
- [x] 5.3 Run broad FlowGuard regression checks.
- [x] 5.4 Sync the editable/local install and verify package/schema versions.
- [x] 5.5 Sync the real local git repository without overwriting unrelated peer changes.

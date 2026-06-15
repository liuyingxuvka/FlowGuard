## 1. Core ModelMesh Closure Gates

- [x] 1.1 Extend `MeshClosureTransition` with structured repeated-input, progress, repair-feedback, blocker, code-contract, and runtime-node metadata.
- [x] 1.2 Harden `review_mesh_closure_model(...)` so repeated-input loop transitions require repair feedback plus a progress, blocker, or bound disposition.
- [x] 1.3 Harden `review_hierarchical_mesh(...)` so parent meshes with child outputs or reattachment contracts require a closure model before broad green confidence.
- [x] 1.4 Add focused hierarchical mesh tests for missing closure, missing feedback, missing no-delta blocker, and guarded retry/rejection loops.

## 2. Transition/Test Projections

- [x] 2.1 Add `model_mesh_closure_to_transition_coverage(...)` to project closure transitions into `TransitionCoverageMatrix` cells.
- [x] 2.2 Ensure retry/rejection-like closure transitions generate happy, failure, negative, and replay required test kinds.
- [x] 2.3 Add Model-Test Alignment and TestMesh regression tests for missing evidence and required leaf-cell ownership of generated cells.
- [x] 2.4 Export the new helper and constants through `flowguard.__init__` and public API registries.

## 3. Docs, Templates, And Specs

- [x] 3.1 Update public docs and modeling protocol to describe ModelMesh closure as the default parent/child green gate.
- [x] 3.2 Update route reference docs/templates for ModelMesh, Model-Test Alignment, TestMesh, and Model-Miss Review.
- [x] 3.3 Update field inventory/API docs so new fields and helper surfaces are discoverable.
- [x] 3.4 Update changelog, version metadata, AGENTS managed version block, and adoption logs for the local release.

## 4. Validation And Synchronization

- [x] 4.1 Run focused unit tests for hierarchical mesh, transition coverage, test mesh, model-test alignment, model miss, public templates, API surface, and skill docs.
- [x] 4.2 Run OpenSpec strict validation for the new change and all specs.
- [x] 4.3 Run the full practical regression suite, using background logs for long checks where appropriate and inspecting final artifacts before claiming pass.
- [x] 4.4 Refresh the editable local install and verify installed package/schema imports.
- [x] 4.5 Sync installed FlowGuard skill copies, shadow workspace, project audit, topology/adoption records, and local git state.

## 5. Peer OpenSpec Cleanup

- [x] 5.1 Inspect the pre-existing untracked OpenSpec changes without overwriting peer work.
- [x] 5.2 Complete, validate, or clearly document those changes if they are safe and related historical optimizations.

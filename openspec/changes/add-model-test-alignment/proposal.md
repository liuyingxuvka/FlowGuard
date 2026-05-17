## Why

FlowGuard can model behavior and FlowGuard can review large test hierarchies, but there is no small first-class way to compare model obligations with ordinary test evidence. This creates a gap where a model can pass, tests can pass, and neither artifact proves that the same scenarios, invariants, hazards, and edge paths are covered.

## What Changes

- Add a standalone Model-Test Alignment helper that compares declared model obligations with plain test evidence.
- Add a Skill Kernel sub-protocol route for `model_test_alignment`.
- Add public documentation and a starter template for project-local alignment reviews.
- Add CLI support for generating the alignment template.
- Keep the feature independent from TestMesh, StructureMesh, and ModelMesh. Those mesh routes remain separate parent/child partition tools.

## Capabilities

### New Capabilities
- `model-test-alignment`: Reviews direct alignment between FlowGuard model obligations and current test evidence.

### Modified Capabilities

## Impact

- New public helper module under `flowguard/`.
- New exported API names in `flowguard.__init__`.
- New template function and `python -m flowguard model-test-alignment-template` command.
- New Skill Kernel route and reference document.
- Updates to README and helper/API docs.
- Focused unit tests for the helper, template, API surface, and skill docs.

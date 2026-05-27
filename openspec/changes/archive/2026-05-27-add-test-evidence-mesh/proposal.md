## Why

FlowGuard already helps large projects split oversized models into parent and
child evidence boundaries. Slow test suites create the same class of risk:
teams split test entrypoints, but parent validation can still overclaim because
child results are stale, incomplete, skipped, overlapping, or only showing
background progress. FlowGuard needs a first-class TestMesh capability that
models test evidence as a hierarchy instead of treating slow tests as ad hoc
shell commands.

## What Changes

- Add TestMesh helper APIs for test partitions, child suite evidence, result
  freshness, background completion evidence, and routine-vs-release gates.
- Add a `test-mesh-template` starter so projects can model their own validation
  hierarchy without making FlowGuard a pytest/unittest runner.
- Update the model-first skill guidance to route slow test hierarchy, regression
  splitting, and background validation evidence into TestMesh.
- Add documentation, tests, and public release notes for the new capability.

## Capabilities

### New Capabilities

- `test-evidence-mesh`: Reviews hierarchical test suites, partition coverage,
  stale or incomplete evidence, hidden skips/timeouts, duplicate suite
  ownership, background-run completion, and routine/release evidence boundaries.

### Modified Capabilities

- `model-first-function-flow`: Adds a `test_mesh_maintenance` route for slow or
  layered validation workflows.

## Impact

- Affected code: optional helper/reporting APIs, CLI template surface, public
  exports, tests, and examples/templates.
- Affected docs: README, API surface, agents snippet, model-first skill, and
  changelog.
- Dependencies: none; keep the Python standard-library-only runtime.
- Release: minor version bump because this is a new public capability.

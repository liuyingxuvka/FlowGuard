## Why

ModelMesh can verify parent/child partition coverage, evidence freshness, and
child reattachment, but it does not yet prove that the model network itself is
closed from parent entry through child handoffs to normal, failure, or explicit
out-of-scope exits. This leaves room for a parent mesh to be green while a child
output, branch, or join obligation is not consumed anywhere.

## What Changes

- Add a FlowGuard-style mesh closure meta-model for model-to-model handoffs.
- Represent root entries, child calls, child outputs, consumers, terminal
  dispositions, join points, and out-of-scope branches as structured closure
  obligations.
- Add a closure review helper that runs the handoff model and reports
  unconsumed outputs, missing entries, unreachable exits, incomplete joins,
  terminal leaks, loop/progress gaps, and unexplained out-of-scope branches.
- Require a passing closure model before ModelMesh can return
  `mesh_green_can_continue` when a parent boundary declares closure
  requirements.
- Keep child internals out of the parent mesh; the closure model consumes child
  contracts and evidence summaries instead of expanding child state graphs.
- Add documentation, examples, tests, and public exports for the closure model.
- No external dependencies and no breaking changes to existing model execution.

## Capabilities

### New Capabilities

- `model-mesh-closure-model`: Executable FlowGuard-style closure modeling for
  parent/child ModelMesh handoffs, output consumption, join completion, and
  terminal dispositions.

### Modified Capabilities

- None.

## Impact

- Affected code: `flowguard/hierarchy.py`, public exports, hierarchical
  examples, and focused tests.
- Affected docs: ModelMesh protocol, hierarchical ModelMesh docs, API surface,
  modeling protocol, skill docs, changelog, and README as needed.
- Dependencies: none; keep the Python standard-library-only runtime.
- Sync: mirror the finished source/docs/tests into the local git checkout and
  refresh the editable install so both local workspaces import the same package
  version.

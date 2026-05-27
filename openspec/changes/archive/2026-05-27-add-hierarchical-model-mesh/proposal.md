## Why

FlowGuard can already run several independent models and use a model mesh to
review evidence freshness, but large workflows still risk either one oversized
state space or several sibling models with unclear boundaries. We need a
first-class way to review hierarchical model partitioning so large models can be
split safely without leaving parent coverage gaps or duplicating sibling
responsibilities.

## What Changes

- Add hierarchical model-mesh governance for parent/child model boundaries.
- Add partition-map checks that verify every parent coverage item has an owner.
- Add sibling-overlap checks that distinguish safe shared reads from unsafe
  duplicate ownership of functions, state writes, side effects, and risk areas.
- Add large-model split review so a single oversized new or legacy model can
  trigger mesh review even before the project has three local models.
- Add legacy-model classification and compatibility-contract concepts so old
  models can be registered, wrapped, reviewed, and gradually split without
  forced rewrites.
- Add documentation, examples, tests, and release notes for the new workflow.
- No breaking changes to `FunctionBlock`, `Workflow`, `Explorer`, or existing
  budgeted graph execution.

## Capabilities

### New Capabilities

- `hierarchical-model-mesh`: Reviews multi-level FlowGuard model hierarchies,
  parent coverage maps, sibling overlap, large-model split triggers, and legacy
  model compatibility.

### Modified Capabilities

- None.

## Impact

- Affected code: optional helper/reporting APIs, public exports, examples, and
  tests.
- Affected docs: modeling protocol, model mesh protocol, API surface, changelog,
  and README as needed.
- Dependencies: none; keep the Python standard-library-only runtime.
- Release: bump the package version, sync the editable install and shadow
  workspace, commit/tag/push, and create a new GitHub release.

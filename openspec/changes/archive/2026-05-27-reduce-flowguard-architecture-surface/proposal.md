## Why

FlowGuard's public package facade has grown through repeated release-driven additions. The current `flowguard.__init__` keeps both grouped API declarations and a large hand-maintained `__all__` list, which makes every new model/helper route more expensive to verify and easier to drift.

## What Changes

- Reduce the first low-risk architecture surface by deriving `flowguard.__all__` from existing `API_SURFACE` groups plus a small explicit metadata/export supplement.
- Preserve the broad `flowguard` facade, public import names, CLI behavior, package version, schema version, and template output contracts.
- Add model-backed Architecture Reduction / StructureMesh evidence for the public facade contraction before changing production code.
- Keep larger candidates, such as splitting `flowguard.templates`, as future work unless the first pass proves enough compatibility evidence.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `flowguard-structure-simplification`: Public facade export simplification must keep `API_SURFACE` and `flowguard.__all__` compatible while removing duplicate manual export declarations.

## Impact

- Affected code: `flowguard/__init__.py`, targeted API-surface tests, and FlowGuard/OpenSpec evidence artifacts for this change.
- Public API: no intended public import, CLI, JSON, schema, package version, or file-writing behavior changes.
- Validation: targeted API-surface tests, public template tests, OpenSpec validation, FlowGuard model checks, shadow workspace import checks, editable install checks, and broad background regressions.

## Why

FlowGuard's current release is green, but the maintenance surface is still too heavy for agents: many specs have placeholder purposes, deep local model checks are not a first-class command, shadow workspace sync is manual, the public API has no compact agent-first index, and field/module bloat is only visible after ad hoc inspection. This change finishes the maintenance hardening that must happen before another meaningful release.

## What Changes

- Add a tracked aggregate runner for local FlowGuard model regressions so ignored or tracked `.flowguard` model artifacts cannot silently drift from the public API.
- Add a shadow workspace sync helper that copies whole source sets, refreshes editable install metadata when requested, and verifies import path/version/helper availability in the target workspace.
- Split CI into fast push checks and deeper manual/scheduled checks, and opt JavaScript actions into Node 24 to remove the current runner warning.
- Replace OpenSpec `Purpose: TBD` placeholders with useful capability purposes so agents can choose routes without reading every requirement.
- Add a compact agent-default API surface that points agents to the smallest useful FlowGuard entry set before falling back to the full helper inventory.
- Add a field lifecycle inventory generator and generated inventory artifact so redundant, display-only, compatibility, and behavior-bearing fields are visible before deletion.
- Physically split a source-audit responsibility out of the oversized Model-Test Alignment module while keeping the original public imports stable.
- **BREAKING**: None. Public FlowGuard names remain exported.

## Capabilities

### New Capabilities
- `flowguard-maintenance-hardening`: Covers aggregate model regression, shadow sync, agent-default API discovery, field inventory, and behavior-preserving module split evidence.

### Modified Capabilities
- `long-check-observability`: Deep local model checks become a named tracked runner instead of ad hoc background commands.
- `project-adoption-version-gate`: Shadow workspace synchronization and editable-install verification become first-class release gates.
- `flowguard-api-registry`: Public API registry exposes a compact agent-default surface before the full helper index.
- `field-lifecycle-mesh`: Field-bearing maintenance includes a generated field inventory with ownership/lifecycle hints.
- `structure-refactor-mesh`: Large module reduction includes behavior-preserving extraction with facade compatibility evidence.

## Impact

- Affected code: `flowguard/__init__.py`, `flowguard/model_test_alignment.py`, new helper modules/scripts, tests, docs, OpenSpec specs, CI workflow, release/version files.
- Affected local processes: model regression, shadow workspace sync, release validation, field audit, structure maintenance.
- Dependencies: Python standard library only.

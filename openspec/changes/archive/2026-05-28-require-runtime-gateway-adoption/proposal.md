## Why

FlowGuard can already model workflow receipts, code boundaries, replay, proof
artifacts, and claim chains, but a target project can still claim FlowGuard use
while its production code writes critical state through scattered direct paths.
That creates the exact failure mode where models and tests look green, yet the
runtime control plane keeps reopening old blockers or accepting stale evidence.

## What Changes

- Add a public Runtime Gateway Adoption review capability that distinguishes
  design-only, test-aligned, and runtime-gateway FlowGuard adoption.
- Require projects that claim runtime-gateway adoption to inventory all critical
  state surfaces and all known write paths for those surfaces.
- Require critical state writes to pass through declared gateway contracts that
  bind to workflow step contracts, code-boundary contracts, replay observations,
  and proof artifacts.
- Treat direct critical-state writes, missing inventory evidence, stale writer
  observations, unmanaged surfaces, and declared legacy bypasses as blocked
  runtime-gateway adoption rather than harmless warnings.
- Preserve existing FlowGuard core APIs and existing helper behavior; this adds
  a new helper layer rather than changing `Workflow` or `Explorer`.

## Capabilities

### New Capabilities

- `runtime-gateway-adoption`: Reviews whether a project has connected
  FlowGuard to the real runtime write gateways for every declared critical
  state surface.

### Modified Capabilities

- `flowguard-closure-contract`: Complete FlowGuard use must clarify when a
  production-confidence claim requires runtime-gateway adoption rather than
  design-only or test-aligned evidence.
- `model-test-alignment`: Code-boundary evidence must remain explicit that it
  supports runtime gateway adoption only when the corresponding writer
  inventory and gateway observations are present.

## Impact

- New public module and exports for runtime gateway adoption reviews.
- New docs and OpenSpec specs describing adoption levels, complete state-write
  inventory, direct-write bypass blockers, and gateway evidence requirements.
- Focused tests for green adoption, missing inventory, direct bypasses,
  unmanaged surfaces, stale observations, and legacy bypass declarations.
- No new runtime dependencies; schema version remains compatible unless a later
  release policy decides otherwise.

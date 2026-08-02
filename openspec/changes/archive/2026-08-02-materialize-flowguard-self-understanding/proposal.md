## Why

FlowGuard models many parts of itself, but the topology is largely inventory-shaped and some source/test/runtime relationships are synthetic or incomplete. It needs an executable self-model that demonstrates the same depth, ownership, evidence, and admission discipline it asks target projects to use.

## What Changes

- Add first-class self models for TaskCoverageDemand and the complete ModelMaturation-to-admission path.
- Add explicit model-to-model, model-to-source, model-to-test, and model-to-runtime relationships for the affected FlowGuard control plane.
- Register maturation, receipt verification, admission, risk, and closure behavior commitments with one primary owner each.
- Align self-maintenance state names and transition obligations with the public runtime contract.
- Make source inventory independent of the behavior ledger and make missing/ambiguous ownership visible.
- Extend model/test alignment so every changed model obligation has an explicit evidence owner or a declared gap.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `flowguard-self-maintenance-mesh`: Represents the complete current self-understanding and implementation-admission flow with executable child gates.
- `authoritative-model-system`: Requires real affected source, test, runtime, and model relationships rather than inventory-only authority for the upgraded surface.
- `hierarchical-model-mesh`: Carries explicit parent/child and affected-sibling relationships for the self-model topology.
- `behavior-commitment-ledger`: Registers the upgraded public behaviors and enforces one primary implementation owner.
- `model-test-alignment`: Requires explicit evidence ownership or a visible gap for every changed obligation.

## Impact

This primarily affects `.flowguard` model packages, topology and source inventories, behavior commitments, alignment declarations, regression orchestration, and tests. It also updates documentation that currently describes stale field names or older release behavior.

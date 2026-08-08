## Why

The current FlowGuard self-blueprint audit exposed a topology model miss: structural hierarchy, cross-boundary feedback, child evidence consumption, delegated assertion helpers, and execution ownership can each look locally complete while the full self-model still lacks an exact current reattachment proof. The release path needs one direct-current contract that preserves these boundaries instead of letting parent aggregation or generated evidence stand in for child-owned results.

## What Changes

- Give every non-root topology node exactly one `structural_parent_id` and record non-structural consumers, feedback, and other cross-boundary owners separately in `cross_boundary_parent_ids`.
- Prohibit cross-boundary relations from becoming structural parent edges merely because they connect the same nodes or form a cycle.
- Require every reachable feedback strongly connected component to bind a current progress contract and independent evidence for its repair token, blocker, ranking rule, decreasing measure, or finite bound.
- Keep the current full model parent as an aggregation owner only: every declared child must contribute its own exact-current terminal receipt, and the parent must consume that receipt without manufacturing or relabeling it.
- Prohibit a blueprint producer, model parent, or evidence consumer from generating or registering the current evidence that it later uses to license its own result.
- Recursively resolve delegated assertion helpers to exact current leaf assertion/native-check members, using lexically qualified identities so nested or same-named helpers cannot collapse.
- Preserve the coverage-contract owner through helper delegation and keep accepted planned-checker design separate from actual execution; absent exact terminal evidence remains `not_run`.
- Make software-blueprint readiness retain exact topology, evidence, helper, and execution gaps instead of promoting a locally green parent.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `target-system-blueprint`: Require explicit structural-parent and cross-boundary-parent identities in target topology.
- `hierarchical-model-mesh`: Distinguish structural hierarchy from cross-boundary feedback and require current progress/evidence closure for real feedback components.
- `authoritative-model-system`: Keep the full model parent as an exact child-receipt aggregator and forbid self-generated or self-registered current evidence.
- `software-blueprint-readiness`: Block whole-blueprint readiness when topology, feedback progress, child receipt, or independent-evidence reattachment is incomplete.
- `model-test-alignment`: Require recursive lexically qualified assertion-helper resolution while preserving coverage ownership and planned-versus-executed status.

## Impact

The affected behavior spans target topology records and validation, self topology production, ModelMesh closure, model-authority evidence registration, full-model parent aggregation, blueprint readiness, model-test alignment, delegated helper discovery, focused regressions, and the next exact model-authority revision. This proposal changes no release identity by itself; all implementation, model renewal, tests, activation, installation, and publication remain explicit unfinished work.

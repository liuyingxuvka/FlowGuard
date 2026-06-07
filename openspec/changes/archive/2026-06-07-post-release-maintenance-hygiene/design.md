## Context

FlowGuard's release surface is green at v0.41.1, but the maintenance surface is
still heavier than necessary for agents:

- many completed OpenSpec changes were still active;
- release validation is local-only unless the maintainer remembers the gate;
- `review_flowguard_self_maintenance(...)` requires callers to manually provide
  all parent route graph fields even for the common default review path.

## Decisions

1. Archive completed OpenSpec changes before adding new work.

   This lowers future routing noise. If an old archive delta no longer applies
   because a later spec renamed the requirement, manually sync the durable
   requirement and archive the old change without replaying stale deltas.

2. Keep CI minimal and source-only.

   CI should run checks that are stable in GitHub-hosted Python and Node
   environments: editable install, FlowGuard project audit, OpenSpec strict
   validation, self-maintenance model checks, and a focused unit suite.

3. Fold self-maintenance defaults into one helper.

   The helper should build a full `SelfMaintenancePlan` from defaults while
   still exposing the full dataclass for explicit advanced use. This reduces
   field burden without deleting behavior-bearing fields.

## Risks

- CI may fail if OpenSpec CLI installation changes. Mitigation: install the
  npm `openspec` package inside the workflow rather than assuming a global
  runner tool.
- Default self-maintenance helper could hide missing route graph evidence.
  Mitigation: use package `FLOWGUARD_ROUTE_API` for API ids and keep
  `review_flowguard_self_maintenance(...)` as the validator.

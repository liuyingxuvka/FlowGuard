## Why

The current route registry contains unresolved next actions, cycles without an executable progress bound, and public-owner routes whose declared skill owner is absent or contradictory. A route graph cannot safely drive delegation or closure until every handoff is typed, resolvable, uniquely owned, and live.

## What Changes

- Add typed handoff targets that distinguish public skills, kernel-owned internal routes, helper APIs, and explicit external actions.
- Require every public-owner/direct route to resolve to exactly one canonical skill owner and every internal route to resolve to one kernel or satellite owner.
- Resolve the current dangling targets for the Codex skill suite and model-maturation flow.
- Define Primary Path Authority as an internal Behavior Commitment Ledger evidence gate unless a future independently invocable public route is explicitly specified.
- Assign Risk Evidence Ledger, FlowGuard self-maintenance, and Risk Template Library to the kernel-owned internal route surface rather than leaving ambiguous public owners.
- Require every strongly connected route component to declare a progress delta, terminal/blocking condition, and finite retry or review bound.
- Extend topology checks and known-bad cases for dangling targets, wrong target kinds, duplicate owners, and unbounded cycles.
- **BREAKING**: an untyped, unresolved, multiply owned, or unbounded cyclic handoff will no longer be accepted as a valid route profile.

## Capabilities

### New Capabilities

- `flowguard-route-topology-governance`: Defines typed route targets, owner resolution, cycle liveness, and machine-checkable topology diagnostics.

### Modified Capabilities

- `flowguard-global-routing`: Requires the global route registry, kernel route map, skill metadata, and next-action graph to agree on route role and canonical ownership.

## Impact

Affected surfaces include route profile models and registries, topology-hazard checks, kernel and satellite route metadata, Behavior Commitment Ledger/Primary Path Authority integration, risk-ledger ownership, route-map generation, tests, and known-bad fixtures. This change depends on `repair-flowguard-adoption-integrity` for the canonical skill inventory and does not own prompt-section rewrites, SkillGuard deep contracts, evidence receipts, or distribution tooling.

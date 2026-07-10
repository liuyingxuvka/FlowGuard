## 1. Confirm Prerequisite Inventory

- [x] 1.1 Verify `repair-flowguard-adoption-integrity` is implemented and its canonical seventeen-skill inventory check passes; record the inventory hash consumed by topology work.
- [x] 1.2 Snapshot all current route profiles, 81 edges, public owner declarations, kernel route projections, and skill metadata so every migrated handoff and owner has a disposition.

## 2. Implement Typed Handoffs

- [x] 2.1 Add discriminated handoff data for `skill`, `internal_route`, `helper_api`, and `external_action`, including target id, condition, claim scope, and stable serialization.
- [x] 2.2 Implement kind-specific resolvers against suite inventory, internal route registry, helper API registry, and explicit external-action declarations.
- [x] 2.3 Migrate every current next action to typed form and repair the four audited dangling targets, documenting the canonical disposition for each old string.
- [x] 2.4 Remove the bare-string successful route; retain only a deterministic migration error with the expected typed target.

## 3. Normalize Canonical Ownership

- [x] 3.1 Enforce exactly one canonical skill owner for each public-owner/direct route and exactly one skill plus internal id for each internal route.
- [x] 3.2 Reclassify Primary Path Authority as the Behavior Commitment Ledger-owned internal evidence gate and remove DevelopmentProcessFlow as its substitute owner.
- [x] 3.3 Reclassify Risk Evidence Ledger, FlowGuard self-maintenance, and Risk Template Library as kernel-owned internal routes.
- [x] 3.4 Preserve PlanDetailing and AgentWorkflow as DevelopmentProcessFlow delegated modes and verify they cannot appear as generic public fallbacks.

## 4. Make Cycles Live And Bounded

- [x] 4.1 Enumerate every strongly connected component in the route graph and attach progress measure, allowed delta, success/blocked terminals, and finite re-entry/review bound.
- [x] 4.2 Define route-specific liveness for the seven-node development/closure/test rework SCC and the existing-model-preflight/similarity SCC.
- [x] 4.3 Add executable loop probes proving changed evidence can progress and unchanged inputs terminate blocked before the bound.

## 5. Generate And Check Projections

- [x] 5.1 Make the canonical route registry the source for route role, entry policy, owner, and typed next actions.
- [x] 5.2 Generate or parity-check the kernel route index, skill metadata, and route documentation against the registry.
- [x] 5.3 Implement `scripts/check_flowguard_route_topology.py` and `scripts/check_flowguard_route_parity.py` with stable JSON findings and nonzero closure status for any hazard.

## 6. Add Test And Model Evidence

- [x] 6.1 Add `tests/test_route_topology_governance.py` and `tests/test_route_profiles.py` for positive resolution, all four target kinds, unique ownership, and projection parity.
- [x] 6.2 Add known-bad fixtures for dangling skill/internal/helper targets, kind mismatch, missing/duplicate owners, absent terminals, no progress delta, unbounded cycle, and unchanged loop.
- [x] 6.3 Update topology/self-maintenance model checks to consume typed edges and cycle metadata; do not mark a topology gap as `pass_with_gaps` for broad closure.

## 7. Close And Handoff

- [x] 7.1 Run every required check in `verification-contract.yaml`, strict OpenSpec validation, and affected route/model tests; bind the report to the inventory/registry hashes.
- [x] 7.2 Confirm all current route targets resolve, both SCCs meet liveness rules, and no public route has zero or multiple owners.
- [x] 7.3 Hand the stable route ids/roles/owners to `upgrade-flowguard-skill-contract-governance`; leave prompt rewrites and SkillGuard contract generation to that change.

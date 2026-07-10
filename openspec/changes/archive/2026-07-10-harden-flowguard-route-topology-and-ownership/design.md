## Context

The current default route profiles form a graph of 29 nodes and 81 edges. Four `next_actions` point to names that are not route ids, two strongly connected components have no machine-readable progress/termination contract, Primary Path Authority is labeled as a direct public route but points at the DevelopmentProcessFlow skill, and several public-owner routes have no skill owner. Existing checks validate portions of shape but not target existence, target kind, owner uniqueness, or cycle liveness.

This change consumes the canonical suite inventory from `repair-flowguard-adoption-integrity` and provides route ownership needed by skill contract generation.

## Goals / Non-Goals

**Goals:**

- Give every handoff a typed target and resolvable identifier.
- Assign exactly one canonical owner to every public and internal route.
- Encode progress, termination, and bounds for cycles.
- Make route registry, kernel route map, skill metadata, and generated indexes consistent.
- Produce precise topology diagnostics and negative fixtures.

**Non-Goals:**

- Add an eighteenth public PPA skill.
- Rewrite the detailed prompt or SkillGuard contract for each skill.
- Execute child routes or decide evidence freshness.
- Change user-facing behavior outside route selection and invalid-topology rejection.

## Decisions

### 1. Handoffs use a discriminated target type

Replace bare next-action strings with records containing `target_kind`, `target_id`, `condition`, and optional `claim_scope`. Allowed kinds are `skill`, `internal_route`, `helper_api`, and `external_action`. Each kind has its own resolver and owner rules. Serialization remains deterministic.

Inferring kind from naming conventions is rejected because the current dangling targets demonstrate that names alone are ambiguous.

### 2. Public route ownership is one-to-one

Every `public_owner`/`direct` route must name exactly one skill present in the canonical suite inventory. Internal routes name one owner skill plus an internal route id. A skill may own multiple internal routes, but a public route cannot be multiply owned.

Primary Path Authority becomes `internal_route` owned by `flowguard-behavior-commitment-ledger`. Risk Evidence Ledger, Risk Template Library, and FlowGuard self-maintenance become kernel-owned internal routes under `model-first-function-flow`. PlanDetailing and AgentWorkflow remain delegated modes owned by DevelopmentProcessFlow.

### 3. Dangling names are repaired at their semantic source

The Codex skill-suite target resolves to the actual public/kernel route id rather than a skill name. The three `model_maturation_loop` references resolve to an explicitly registered internal route owned by the kernel, or are replaced by the correct existing route if source review proves one. No compatibility alias remains as a second successful route.

### 4. Cycles require liveness metadata

Each strongly connected component must declare:

- a `progress_measure` that changes before re-entry;
- an `allowed_delta` or evidence improvement predicate;
- terminal success and terminal blocked conditions;
- `max_reentries` or an externally justified bounded review policy.

The topology checker explores each cycle with unchanged and changed inputs. Unchanged re-entry must block before the bound; changed evidence may continue.

### 5. One registry generates all projections

The route profile registry is authoritative. Kernel route tables, public route indexes, skill route-parity tests, and topology diagrams are generated or checked against it. Human prompt text remains curated but declares stable route ids that are checked against the registry.

## Risks / Trade-offs

- **[Risk] Existing callers pass plain strings.** → Provide a one-time parser at the data-loading boundary that emits a deterministic migration error; do not keep a successful legacy execution path.
- **[Risk] Cycle bounds are too small for legitimate iterative work.** → Bounds are route-specific and may yield a typed blocked/review result rather than silently terminating useful work.
- **[Risk] PPA later needs direct invocation.** → A future OpenSpec change can promote the internal route after independent activation evidence; this design does not preclude it.
- **[Risk] Generated projections drift.** → CI compares all projections to the canonical registry and fails on manual edits that change route ids or owners.

## Migration Plan

1. Land typed target data structures and resolvers behind failing known-bad tests.
2. Map all existing edges and owners; reject unresolved or duplicate mappings.
3. Fix PPA and kernel-owned internal route classifications.
4. Add cycle metadata and liveness checks for both current SCCs.
5. Generate/check the kernel route index and run all topology/model tests.
6. Remove the successful bare-string path after all callers are migrated.

Rollback reverts the typed topology and its consumers together; it must not leave both typed and untyped success routes.

## Open Questions

- During implementation, source review must choose the exact canonical id for the current `model_maturation_loop` references. The acceptance rule is fixed: the chosen id must be registered, owned, and covered by the same liveness checks.

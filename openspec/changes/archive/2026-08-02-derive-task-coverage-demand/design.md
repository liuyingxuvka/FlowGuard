## Context

`ModelMaturationIntake.required_contribution_ids` currently makes the caller the effective author of the minimum denominator. Existing route-specific models already know when they are relevant, but there is no independent object that compiles those triggers into one task-specific contract.

## Goals / Non-Goals

**Goals:**

- Represent the task as immutable facts and derive the minimum required owner rows deterministically.
- Keep each specialist model as the owner of its own trigger and evidence semantics.
- Make depth measurable without forcing every route on every task.

**Non-Goals:**

- Defining roles internal to the target product.
- Making users select a correctness mode.
- Replacing specialist FlowGuard routes with one universal model.

## Decisions

### Introduce a frozen TaskFacts and TaskCoverageDemand boundary

`TaskFacts` carries exact task identity, requested outcomes, affected surfaces, change kinds, risk signals, topology signals, execution intent, and release intent. A registry of `CoverageRule` values maps those facts to `CoverageDemandRow` values. The compiled `TaskCoverageDemand` is content-fingerprinted and contains all owner rows plus the derived cost tier.

This is preferred over adding more fields to ModelMaturation because demand derivation and sufficiency judgment have different responsibilities. It is also preferred over hard-coding product roles because target roles belong in the target model.

### Use monotonic demand union

Built-in rule results are the minimum. Caller additions are unioned by stable row identity; a caller cannot delete, downgrade, or mark a built-in row satisfied. Duplicate owners with conflicting requirements fail compilation.

### Record four terminal dispositions

Rows use `satisfied`, `not_triggered`, `unresolved`, or `blocked`. `not_triggered` is retained in the compiled record so a light run is explainable rather than silently incomplete.

### Derive presentation tier after demand compilation

Tier is computed from triggered owner families, risk, topology, persistence, and release facts. It governs grouping and default check breadth, not the denominator. This avoids both all-routes overhead and a user-selected weak path.

## Risks / Trade-offs

- [Rule registry misses a new change kind] → Unknown or unmapped affected facts compile to an unresolved `coverage-demand-owner` row and block broad closure.
- [Too many conservative triggers] → Preserve not-triggered explanations and test ordinary bounded tasks against the minimal expected owner set.
- [Caller additions collide with built-ins] → Require exact semantic equality for duplicate identities; otherwise fail visibly.

## Migration Plan

1. Add and validate the new model before changing runtime consumers.
2. Introduce task-demand types and compiler with focused unit tests.
3. Change ModelMaturation intake to require the compiled demand and remove caller-authored minimum authority.
4. Update public exports, examples, API registry, prompts, and self models.
5. Use direct-current replacement; do not add a legacy coercion or fallback.

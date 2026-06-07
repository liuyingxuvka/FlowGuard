# Design

## Route

OpenSpec owns the product behavior change. FlowGuard owns the executable
confidence boundary:

- Existing model preflight: reuse `run_model_first_checks(...)` as the default
  integration point.
- Model-first kernel: add a finite closure gate without making `Explorer`
  infinite-state.
- DevelopmentProcessFlow: treat docs, tests, install, shadow sync, and local git
  version as ordered evidence-bearing actions.

## Behavior

The state closure gate classifies each modeled dimension:

- `closed_enumeration`: the model claims the listed values are complete.
- `open_boundary`: values outside the list may occur and need representative
  unknown cases plus safe handling.
- `unbounded_boundary`: the model cannot enumerate the surface and broad
  confidence must be scoped or blocked.
- `unknown_policy`: FlowGuard inferred the dimension, but the model has not yet
  declared whether it is closed or open.

Safe handling means reject, block, isolate, or route to model maturation before
side effects. Accepting unknown values as normal flow or causing side effects
before resolution blocks confidence.

## Default Integration

`run_model_first_checks(...)` always appends a `state_closure` section.

- If the caller provides a `StateClosurePlan`, that explicit plan is reviewed.
- Otherwise FlowGuard infers dimensions from external inputs and dataclass
  fields such as `status`, `phase`, `kind`, `type`, `mode`, `version`, and
  `schema_version`.
- Inferred `unknown_policy` gaps produce scoped confidence, not silent pass and
  not default human review.
- Explicit unsafe handling produces `blocked`.

## Maintenance Handoff

A state closure gap is not a new giant route. The maintenance scan emits a
required `model_maturation_loop` action for
`MAINTENANCE_SIGNAL_STATE_CLOSURE_GAP`, so agents know the next owner route is
to deepen the model and rerun the owning checks.

## Non-Goals

- Do not add an optional pack that agents can ignore.
- Do not weaken hard invariants to make unknown cases pass.
- Do not make core `Explorer` enumerate infinite values.
- Do not treat generated representative cases as domain proof without a model,
  replay, test, or explicit safe handling policy.

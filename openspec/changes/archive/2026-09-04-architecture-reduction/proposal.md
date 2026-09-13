## Why

The architecture-reduction route needs a bounded ordinary read path and a
proof-backed contraction rule. Similar code, low apparent usage, or high cost
is not enough to remove a route because dynamic callers, model bindings, tests,
and public behavior may still depend on it.

## What Changes

- Add compact, candidate-detail, and explicit full projections over one
  complete reduction denominator.
- Require current caller, consumer, behavior, state, error, side-effect,
  public-surface, model, and test/oracle proof before contraction.
- Keep one current runtime path and reject aliases, fallbacks, and unbound
  wrappers after a proven replacement.

## Capabilities

### Modified Capabilities

- `architecture-reduction`: proof-backed compact reads and single-path cleanup.

## Impact

This is a specification-only companion to the current FlowGuard cleanup. It
does not authorize independent reconstruction, a second model authority, or
behavior removal without current proof.

## Why

Large FlowGuard graph-style models can reach millions of possible states. The
current ten-step progress output makes long checks visible, but it does not
reduce the amount of model state held or revisited, so agents can still time out
or run out of memory on models such as FlowPilot meta and capability checks.

## What Changes

- Add a budgeted model-group runner for reachable graph models.
- Split one large model run into persisted shards, with a default shard budget
  of 10,000 processed states.
- Keep a durable ledger of seen, pending, processed, and failed states so later
  shards continue from previous work instead of starting over.
- Report progress at two levels: the current shard's ten-step progress and the
  whole model group's completed/pending state.
- Treat incomplete model groups as incomplete evidence, not as passing checks.
- Keep existing `Explorer` progress behavior compatible and unchanged for
  sequence-based workflows.

## Capabilities

### New Capabilities

- `budgeted-model-groups`: Defines how FlowGuard runs large reachable graph
  models in bounded shards with durable progress, resume, and whole-group
  reporting.

### Modified Capabilities

- None.

## Impact

- New public helper API for budgeted graph/model-group checks.
- New tests, documentation, and example model for large-check behavior.
- No new runtime dependencies; the implementation should use the Python
  standard library.
- Version and changelog update for a new GitHub release.

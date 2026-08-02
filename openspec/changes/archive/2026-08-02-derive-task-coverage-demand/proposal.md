## Why

FlowGuard can currently judge the evidence that a caller asks it to inspect, but the caller can also understate what must be understood. A task-derived coverage denominator is needed so the system can say what it has understood, what was deliberately not triggered, and what remains unresolved before judging model maturity.

## What Changes

- Add a canonical TaskCoverageDemand plan derived from task facts, affected behavior, risk, external surfaces, lifecycle changes, and the existing model topology.
- Require every demanded owner row to end as `satisfied`, `not_triggered`, `unresolved`, or `blocked`, with evidence or a reason.
- Derive ordinary, standard, deep, and release cost tiers from task facts; callers may request more work but may not use a tier to remove required coverage.
- Bind ModelMaturation intake to the compiled demand so the coverage denominator is not caller-authored.
- Keep target-software roles inside the target model; FlowGuard models ownership and interfaces without inventing product roles.

## Capabilities

### New Capabilities

- `task-coverage-demand`: Derives the minimum model/owner/evidence coverage required by the current task and records the disposition of every demanded row.

### Modified Capabilities

- `model-maturation-loop`: Consumes an independently compiled TaskCoverageDemand instead of trusting caller-supplied required contribution identifiers.
- `flowguard-ai-entry-simplification`: Makes task fact freezing and demand compilation the stable entry sequence while preserving lightweight use for genuinely small tasks.

## Impact

This affects the public Python API, CLI/API registry, ModelMaturation compilation, model-first guidance, self models, documentation, and the tests that establish coverage and depth. It is a direct-current contract change: permissive caller-authored minimum coverage is removed rather than retained as a fallback.

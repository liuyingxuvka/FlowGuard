# State Write Inventory

A state write inventory is a small checklist for model fidelity. It helps avoid
building an invariant around one obvious writer while missing another production
path that mutates the same state.

This is a modeling practice, not a new FlowGuard runtime gate. The direct core
path remains:

```text
State + FunctionBlock + Invariant + Explorer
```

## When To Make One

Make a write inventory before adding or trusting an invariant over a state field
such as:

- `recommendation_status`
- `output_status`
- `analysis_json`
- cache fields or materialized views
- queue status fields
- retry counters or side-effect records
- ownership or permission fields

The higher the risk, the more important the inventory. It is especially useful
when the production code has cleanup paths, finalizers, runtime repair jobs, or
multiple functions that can write the same field.

## What To Record

Use a compact table:

| State field | Invariant or risk | Production write locations searched | Modeled block or skipped reason |
| --- | --- | --- | --- |
| `output_status` | cannot regress to `reject` after recommendation | `mark_recommended_output_set`, cleanup jobs, finalizer | modeled as `MarkRecommendedOutput` |

The inventory should answer:

1. Which field does the invariant depend on?
2. Which production functions, methods, queries, or scripts can write it?
3. Which writers are represented in the FlowGuard model?
4. Which writers are intentionally skipped, and why?

Skipped writers are not automatic failures, but they are confidence gaps. Keep
them visible in the adoption log or summary report.

## Search Heuristics

Use repository search before finalizing the model. For a field named
`output_status`, search for patterns such as:

```text
output_status
.output_status
["output_status"]
UPDATE ... output_status
set_output_status
mark_*output*
cleanup
finalize
```

Also search for wrapper names, ORM fields, migration columns, and task names
that can write the field indirectly.

## How It Affects Conformance

If a state field has multiple production writers, or if one writer is a cleanup,
runtime, or finalizer path, conformance replay should be the default next check
after the model passes. If replay is skipped, record why this round is still
model-level confidence only.

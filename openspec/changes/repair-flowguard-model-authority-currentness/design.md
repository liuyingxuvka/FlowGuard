## Context

The repository already has a model-authority section and snapshots, but recent audit history says authority was invalid. Repair must preserve immutable history and use the native revision activation path.

## Goals / Non-Goals

**Goals**

- Establish one current sole observed head and passing audit.
- Separate authority repair evidence from later feature evidence.

**Non-Goals**

- No model-miss diagnostic behavior.
- No deletion or mutation of historical snapshots.

## Decisions

1. Inspect the live snapshot, head, activation receipt, and current source inventory.
2. If stale, create a new revision set and activate it through native commands; never hand-edit an old snapshot.
3. Run project/model-system audits and focused authority-store tests.
4. Fold the behavior-neutral authority repair into the next feature release,
   v0.66.0, while keeping its evidence separate from feature evidence.

## Risks / Trade-offs

A source-inventory change can require reattachment of multiple owners; incomplete reattachment remains visible.

## Migration Plan

Audit, create/activate only if needed, verify the sole head, and include the
repair in v0.66.0.

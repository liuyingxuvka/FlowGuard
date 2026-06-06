# FieldLifecycleMesh Protocol

FieldLifecycleMesh is the FlowGuard route for field-level coverage. It exists
because field-heavy changes can be too detailed for the main behavior model,
but still too important to leave as informal notes.

## Trigger

Use FieldLifecycleMesh when a task touches:

- payload, schema, API, config, prompt/config, persisted, UI state, or runtime
  state fields;
- field additions, removals, renames, migrations, aliases, defaults, fallback
  fields, wrappers, or compatibility fields;
- bug repairs whose root cause is a missing, stale, mis-projected, or
  old-field behavior branch;
- replacement work where the user did not explicitly request compatibility.

Skip only when no field, schema key, config flag, prompt/config field, persisted
attribute, payload column, or public field-like surface is in scope.

## Inputs

Collect:

- the field boundary and discovered field ids;
- parent groups such as entity, payload, schema, config, public entrypoint, or
  prompt/config surface;
- leaf rows for every discovered field;
- role, lifecycle, behavior impacts, readers, writers, and owner routes;
- projection rows for behavior-bearing fields;
- old-field disposition and evidence refs for old, replaced, deprecated,
  alias, fallback, or compatibility-like fields.

## Parent And Leaf Shape

The parent field model keeps the high-level view small. Leaf rows carry the full
inventory. A behavior model should include only fields that affect routing,
state, permissions, side effects, schema, replay, migration, or external
contracts. Presentation-only or metadata fields can stay out of the high-level
model if the leaf row records why.

## Default Replacement Policy

If compatibility is not explicitly requested, old fields should not survive by
default. Valid closing dispositions are deleted, blocked, migrated, delegated to
the replacement field, same-contract repaired, explicitly preserved, or
out-of-scope with reason. Unknown disposition blocks full confidence.

Explicit preservation requires compatibility intent plus current evidence, such
as public API compatibility, old data migration, or externally promised schema
support.

## Handoffs

FieldLifecycleMesh does not prove behavior alone. Send:

- projections to Model-Test Alignment as model obligations and owner code
  contracts;
- reader/writer/owner maps to Code Structure Recommendation;
- old field disposition to Legacy Path Disposition and Architecture Reduction;
- field root cause ids and same-class field ids to Model-Miss Review;
- field lifecycle, projection, replacement, and bug-repair closure artifacts to
  DevelopmentProcessFlow;
- current field lifecycle evidence to Closure Contract for broad claims.

## Completion Standard

A field lifecycle review is complete when:

- every discovered field has a leaf row or the discovery boundary is narrowed;
- every behavior-bearing field has a projection or a scoped-out reason;
- old/replaced/deprecated/compatibility-like fields have a closing disposition;
- downstream handoffs are named;
- stale field rows are blocked or rerun;
- full confidence is not claimed from inventory alone.

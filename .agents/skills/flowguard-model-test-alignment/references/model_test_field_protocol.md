# Model-Test Field Protocol

Load this file when a field is added, removed, renamed, migrated, replaced,
externalized, preserved, or projected across a boundary.

## Required Field Chain

Bind each field through:

`source declaration -> input/loader -> internal state -> transition/write -> output/serialization -> consumer -> retirement or preservation rule`

Record presence, absence, null/default behavior, type/domain, transform,
round-trip behavior, unknown-field policy, and error semantics. A model row,
code owner, and test must describe the same field lifecycle.

## Negative Coverage

Include missing field, malformed value, boundary value, stale name, mixed old
and current payload, duplicate source, and prohibited resurrection. For a
retired field, prove zero current writers/readers unless an explicit bounded
historical reader is part of the requirement.

## Handoff

Use FieldLifecycleMesh for lifecycle ownership and replacement/retirement
evidence. Model-Test Alignment consumes that result and reports row coverage;
it does not invent compatibility or migration authority.

## Context

Architecture Reduction is the right FlowGuard route for asking whether existing
code can be smaller while preserving declared observable behavior. It already
tracks candidate type, target action, proof status, public entrypoint impact,
and required next route.

The missing concept is why a candidate exists. A pass-through adapter or branch
may be valid current behavior, a public compatibility facade, a rejection test
for retired input, archived historical evidence, or obsolete runtime authority.
Those cases need different recommendations even when the target action looks
similar.

FlowGuard already has `LegacyPathDisposition` for model-miss closure. That
object answers the later question: after a repair, what happened to an old or
alternate executable path? Compatibility-surface classification answers the
earlier Architecture Reduction question: before contraction, what kind of
surface is this?

## Design

Add `CompatibilitySurfaceClassification` to
`flowguard.architecture_reduction`.

The object records:

- `surface_id`: stable id for the old, alternate, or compatibility-like
  surface.
- `classification`: one of:
  - `current_contract`
  - `boundary_adapter`
  - `negative_legacy_test`
  - `archive_only`
  - `prune_candidate`
  - `evidence_needed`
- `code_node_ids`: code nodes or modules that expose the surface.
- `public_entrypoints`: public commands, imports, routes, APIs, or file formats
  affected by the surface.
- `runtime_authority`: whether the surface can still write or authorize
  current runtime state.
- `owner_model_elements`: model elements that currently own the behavior.
- `candidate_ids`: Architecture Reduction candidates informed by this surface.
- `recommended_action`: one of keep, adapt, reject, archive, prune, or
  collect-evidence.
- `evidence_refs`, `missing_evidence`, and `rationale`.

Extend `ArchitectureReductionPlan` with:

```python
compatibility_surfaces: tuple[CompatibilitySurfaceClassification, ...] = ()
```

Review rules:

1. Missing compatibility-surface rationale is a warning for recorded surfaces.
2. `current_contract` blocks remove/collapse target actions for linked active
   candidates.
3. Any linked surface with public entrypoints requires StructureMesh when its
   candidate is active.
4. `negative_legacy_test` blocks removal unless the candidate keeps rejection
   evidence visible or is completed with current replacement evidence.
5. `archive_only` must not retain runtime authority; runtime-authority
   archive-only surfaces block.
6. `prune_candidate` can support ready contraction only when the linked
   candidate already has a ready proof status.
7. `evidence_needed` blocks ready contraction for linked candidates.

`ArchitectureReductionReport` should expose the reviewed classifications in
`compatibility_surfaces` so downstream tooling and users can see why a
candidate was kept, blocked, or made ready.

## Compatibility With Existing APIs

Existing `ArchitectureReductionPlan(...)` calls continue to work because
`compatibility_surfaces` defaults to an empty tuple.

Existing candidate proof semantics are preserved. The new classification never
replaces proof status; it adds a reasoned precondition for old or alternate
surfaces.

## Relationship To LegacyPathDisposition

`CompatibilitySurfaceClassification` does not close repaired old paths. When a
bug repair or closure claim still has old executable paths, use
`LegacyPathDisposition` and proof artifacts as before.

The expected handoff is:

```text
Architecture Reduction:
  "This surface is a boundary adapter / prune candidate / evidence-needed."

Model Miss or Risk Evidence closure:
  "The old path was deleted, blocked, delegated, repaired, or scoped out with
   proof."
```

## Validation

- Unit tests for all classification outcomes in Architecture Reduction.
- API surface tests for exported helper objects and constants.
- OpenSpec strict validation for the new change and modified specs.
- Full pytest after focused tests pass.
- Project audit and editable install sync after implementation.

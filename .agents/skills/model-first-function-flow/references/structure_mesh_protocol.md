# StructureMesh Protocol

Use StructureMesh when a large script, package, module, command surface, or API
surface is being split into smaller owned children and the risk is structural:
lost public entrypoints, duplicated state, duplicated side effects, dependency
cycles, config drift, or overclaimed behavior parity.

StructureMesh is a parent/child ownership model. It does not refactor code,
parse files, or run tests. Project adapters or agents collect source inventory,
dependency, facade, and parity evidence, then pass that evidence into
`review_structure_mesh(...)`.

## Trigger

Create or update a StructureMesh when any of these are true:

- a large script or module is split into two or more child modules;
- a public import path, CLI command, API route, JSON/data shape, or plugin entry
  point is moved;
- state, config, cache, side effects, or external writes are divided across
  children;
- a child module depends on another child and cycles may appear;
- routine refactor confidence and release confidence require different
  evidence.

## Partition Checklist

Inventory the parent boundary as `StructurePartitionItem` rows:

- functions and classes;
- state fields, caches, registries, and durable records;
- config keys, defaults, environment variables, and path conventions;
- side effects such as writes, publishes, external calls, logs, migrations, or
  generated artifacts;
- public entrypoints and behavior contracts.

Every partition should have one clear owner:

- `child` for normal extracted child ownership;
- `parent` for retained orchestration or facade responsibilities;
- `read_only` for inspected data that must not be written;
- `shared_kernel` only when duplication is intentional and documented.

## Evidence Checklist

For each `ModuleStructureEvidence`, record:

- child module id, path, layer, and source parent;
- owned functions, state, config, side effects, and behavior contracts;
- dependency list and any dependency cycles;
- whether the compatibility facade remains;
- whether behavior parity evidence is current and which evidence tier supports
  it;
- whether config/default behavior changed;
- whether the module is routine evidence or release-required evidence.

For each `PublicEntrypointEvidence`, record:

- old path and new path;
- entrypoint type such as import, CLI, API route, command, data shape, or plugin;
- whether compatibility is preserved;
- whether a facade or compatibility layer is available;
- whether parity evidence is current;
- whether release scope must block until this entrypoint is green.

## Routine And Release Scope

Use `decision_scope="routine"` for ordinary refactor confidence. Routine scope
may defer release-only modules or entrypoints when
`release_deferred_allowed=True`, but the report must keep the release
obligation visible.

Use `decision_scope="release"` before publishing, tagging, deployment, broad
completion claims, or compatibility claims. Release scope should block when
release-required parity evidence is missing or stale.

## Required Hazards

Before trusting parent refactor confidence, the StructureMesh model must make
these known-bad variants fail:

- missing partition owner;
- unregistered partition owner;
- duplicate partition owner;
- duplicate state owner;
- duplicate side-effect owner;
- duplicate config owner;
- public entrypoint removed;
- compatibility facade missing;
- unsafe dependency cycle;
- config/default drift;
- missing behavior parity;
- stale behavior parity;
- insufficient evidence tier;
- missing release-required parity under release scope.

## Prompt Template

Use this compact prompt when asking an agent to build or review a
StructureMesh:

```text
Build a FlowGuard StructureMesh for this refactor. Treat the original module as
the parent and the extracted files as child modules. Inventory functions,
state, config, side effects, public entrypoints, behavior contracts, dependency
edges, facades, and parity evidence. Do not inline each child implementation.
Review routine scope and release scope separately. The mesh must catch missing
owners, unregistered owners, duplicate ownership, removed entrypoints, missing
facades, dependency cycles, config drift, stale parity, and release-only parity
gaps before parent refactor confidence is claimed.
```

## Completion Standard

A StructureMesh is complete when:

- the parent partition map covers the moved or retained structure;
- every owner is registered or explicitly parent/read-only/shared-kernel;
- duplicate state, side-effect, and config ownership is absent or documented as
  allowed shared ownership;
- public entrypoints remain compatibility-preserved through facades;
- dependency cycles are absent or explicitly allowed with evidence;
- config/default changes are either absent or treated as behavior changes;
- routine/release obligations are visible;
- known-bad hazards fail in executable evidence.

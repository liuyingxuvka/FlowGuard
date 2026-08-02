## Context

This change follows `close-flowguard-self-understanding-loop`. The required observable contracts are already defined there and in the main FlowGuard specs. The remaining work is implementation contraction with explicit public-facade and field-lifecycle proof.

## Goals / Non-Goals

**Goals:**

- Establish one direct-current source for public-owner identity and one direct-current source for each owner result.
- Make Closure a thin terminal consumer rather than a competing decision owner.
- Remove count-driven mesh behavior and obsolete entry fields without changing licensed outcomes.

**Non-Goals:**

- New behavior, route IDs, commands, skills, status values, or compatibility paths.
- Reinterpreting existing evidence to make an unresolved case pass.

## Decisions

### Derive rather than synchronize

All secondary route maps and evidence views are generated from their canonical typed owner. Runtime comparison-and-repair was rejected because it would preserve multiple authorities and hide drift.

### Contract only after parity proof

StructureMesh first inventories public imports, constructor fields, serialized keys, CLI inputs, tests, docs, and downstream consumers. ArchitectureReduction marks each candidate as proven, conditional, or rejected. Removal occurs only for proven candidates with a current facade/parity result and a FieldLifecycle disposition.

### Preserve upstream decisions at Closure

Closure receives the exact maturation receipt verification, implementation admission, and RiskLedger decision. It checks identity/material/terminal consistency and returns their licensed boundary. It does not maintain a second route-specific scoring table.

### Direct-current removal

Removed fields and entry paths receive no aliases, converters, deprecated dual paths, or fallbacks. Unsupported legacy input fails visibly. Historical immutable evidence remains historical and is not rewritten.

## Risks / Trade-offs

- **[Risk] A seemingly internal field is externally imported** → Inventory exports and fixtures, then keep the candidate conditional until facade evidence proves safe removal.
- **[Risk] Thin Closure changes error ordering** → Capture current externally supported terminal outcomes and compare before/after traces.
- **[Risk] Partial contraction leaves two writers** → Add exact-one-owner checks and block completion while duplicate construction remains reachable.

## Migration Plan

1. Freeze observable contracts and compile StructureMesh, ArchitectureReduction, and FieldLifecycle evidence.
2. Redirect consumers to canonical descriptors/resolutions and prove parity.
3. Delete duplicate construction and count activation, then run focused and affected tests.
4. Verify the parent self-understanding change still passes without scoped widening.

Rollback is a source revert before release. No migration reader or compatibility layer is introduced.

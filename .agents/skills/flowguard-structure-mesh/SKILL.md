---
name: flowguard-structure-mesh
description: Use when an existing large script, module, package, command, public API, facade, config surface, or plugin entrypoint split needs model-derived ownership, dependency, compatibility, parity, and release gates.
---

# FlowGuard Structure Mesh

## Purpose
Govern an existing-code split while preserving public entrypoints, facades, configuration, side effects, dependency cycles, and observable parity.

## Entrypoint Scope
This standalone FlowGuard satellite skill owns `structure_mesh_maintenance` (`public_owner`) refactor evidence, not behavior invention or code edits.

## Local Material Routing
After admission, read `references/structure_mesh_protocol.md` for target derivation, partitions, evidence scopes, and handoffs.

## Entrypoint Acceptance Map
Accept a named model and existing surface; derive child ownership; block facade/owner/cycle/config/parity gaps; hand evidence to typed owners.

## Use When
- Use for splitting large code surfaces, moving public imports/CLI/API/data/plugin entrypoints, dividing state/config/side effects, or checking dependency cycles and parity.

## Do Not Use When
- Do not derive behavior requirements from scratch, recommend greenfield modules, refactor code directly, or claim parity from internal/formatting checks; return unclear models to `flowguard`.

## Required Workflow
1. Derive target modules from a named model and its FunctionBlock/state/effect/facade/validation maps.
2. Partition functions, state, config, effects, contracts, dependencies, public entrypoints, and facades to single owners.
3. For blueprint scope, consume the independent inventory fingerprint and exact required ids; require one owner or terminal disposition per surface.
4. Attach current routine/release parity and hand gaps/obligations downstream.

## Hard Gates
- Model-purpose gate: freeze task-specific failure(s); bind native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose: no mode/fallback; only FlowGuard-declared checks may support completion claims. Require the real FlowGuard check engine and AGENTS.md managed record; forbid a fake mini-framework.
- Missing target structure, facade, owner, compatibility, or current parity blocks its scope. StructureMesh does not discover source; stale inventory, omitted surfaces, or fingerprint mismatch blocks blueprint closure.
- Route ArchitectureReduction only when a concrete candidate already names its observable contract, proof, target action, and required next route.
- Dependency/config drift and release-only gaps stay visible; new/deepened models require template harvest closure.

## Output Requirements
- Return `evidence`, `failures`, `blockers`, `skipped_checks`, `residual_risk`, `claim_boundary`, `typed_next_actions`, parity, and a structure mesh diagram. Blueprint output adds inventory fingerprint, exact required/partitioned/dispositioned/missing ids, and closure.


<!--VTP:target adapter/catalog;native validation;stale|ambiguous=block;preview!=proof;harvest-->

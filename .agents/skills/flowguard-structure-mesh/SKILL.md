---
name: flowguard-structure-mesh
description: Use when an existing large script, module, package, command, public API, facade, config surface, or plugin entrypoint split needs model-derived ownership, dependency, compatibility, parity, and release gates.
---

# FlowGuard Structure Mesh

## Purpose
Govern an existing-code split while preserving public entrypoints, facades, config, effects, cycles, and parity.

## Entrypoint Scope
A standalone FlowGuard satellite skill; owns `structure_mesh_maintenance` (`public_owner`) evidence, not behavior invention or edits.

## Local Material Routing
After admission, read `references/structure_mesh_protocol.md` for target derivation, partitions, evidence scopes, and handoffs.

## Entrypoint Acceptance Map
Accept a named model/surface; derive child ownership; block facade/owner/cycle/config/parity gaps; hand evidence onward.

## Use When
- Use for splitting large code surfaces, moving public imports/CLI/API/data/plugin entrypoints, dividing state/config/side effects, or checking dependency cycles and parity.

## Do Not Use When
- Do not derive behavior requirements from scratch, recommend greenfield modules, refactor code directly, or claim parity from internal/formatting checks; return unclear models to `flowguard`.

## Required Workflow
1. Accept ArchitectureReduction only with universe member, observable contract, current equivalence/facade proof, consumers/tests, action, and next route; otherwise unresolved. Derive modules from named model maps.
2. Partition functions, state, config, effects, contracts, dependencies, public entrypoints, and facades to single owners.
3. For blueprint scope, consume the independent inventory fingerprint and exact required ids; require one owner or terminal disposition per surface.
4. Attach current routine/release parity and hand gaps/obligations downstream.

## Hard Gates
- Model-purpose gate: freeze task-specific failure(s)/claim_boundary; bind native good/bad-per-failure/oracle/current evidence. Reusable types are not fixed-purpose: no mode/fallback; only FlowGuard-declared checks may support completion claims. Require real FlowGuard check engine and AGENTS.md managed record; forbid a fake mini-framework.
- Missing target structure, facade, owner, compatibility, or current parity blocks its scope. StructureMesh does not discover source; stale inventory, omitted surfaces, or fingerprint mismatch blocks blueprint closure.
- ArchitectureReduction requires a concrete universe member, contract, current proof, target action, and next route; similarity, size, or origin is not proof.
- Dependency/config and release-only gaps stay visible.
- Only explicit reuse/publication or proven cross-project use triggers strict `risk_template_library` closure.
- Blueprint depth/first gap, explicit whole scope, affected-only default, exact ownership, and separate decision axes follow the protocol.

## Output Requirements
- Return evidence, failures, blockers, skipped_checks, residual_risk, claim_boundary, typed_next_actions, parity, and a structure mesh diagram. Blueprint adds depth/first gap, inventory fingerprint, ids, and closure. Keep one facade/adapter owner; caller, dependency, model, test, and release evidence are required before contraction.

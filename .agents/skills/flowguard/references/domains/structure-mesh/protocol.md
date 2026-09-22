# FlowGuard Structure Mesh

## Purpose
Govern an existing-code split while preserving public entrypoints, facades, config, effects, cycles, and parity.

## Entrypoint Scope
Owner `structure_mesh_maintenance` (`public_owner`) evidence; not behavior invention or edits.

## Local Material Routing
After selecting the subject, read `references/structure_mesh_protocol.md` for target derivation, partitions, evidence scopes, and handoffs.


## Operation routing
- `read`: load this protocol only when the selected subject is requested; use accepted current model and evidence, with zero producers and zero writes.
- `change`: load this protocol when the selected subject's model, relation, field, contract, or obligation changes; execute only its affected owner closure.
- `release`: reuse accepted subject evidence and load this protocol only for a missing release obligation in the declared scope.

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

- Missing target structure, facade, owner, compatibility, or current parity blocks its scope. StructureMesh does not discover source; stale inventory, omitted surfaces, or fingerprint mismatch blocks blueprint closure.
- ArchitectureReduction requires a concrete universe member, contract, current proof, target action, and next route; similarity, size, or origin is not proof.
- Only explicit reuse/publication or proven cross-project use triggers strict `risk_template_library` closure.
- Blueprint depth/first gap, explicit whole scope, affected-only default, exact ownership, and separate decision axes follow the protocol.

## Output Requirements
- Return parity, and a structure mesh diagram. Blueprint adds depth/first gap, inventory fingerprint, ids, and closure. Keep one facade/adapter owner; caller, dependency, model, test, and release evidence are required before contraction.

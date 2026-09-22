# FlowGuard Code Structure Recommendation

## Purpose
Derive recommendation-only FunctionBlock-to-module ownership, facades, adapters, fields, effects, and validation boundaries from a named model.

## Entrypoint Scope
Owner `code_structure_recommendation` (`public_owner`); recommendation only, not refactoring.

## Local Material Routing
After selecting the subject, read `references/code_structure_recommendation_protocol.md` for the complete schema and handoffs.


## Operation routing
- `read`: load this protocol only when the selected subject is requested; use accepted current model and evidence, with zero producers and zero writes.
- `change`: load this protocol when the selected subject's model, relation, field, contract, or obligation changes; execute only its affected owner closure.
- `release`: reuse accepted subject evidence and load this protocol only for a missing release obligation in the declared scope.

## Use When
- Use before code when module, function, facade, adapter, field/effect owner, or validation boundary is unclear.

## Do Not Use When
- Do not refactor existing code, invent behavior, or replace parity evidence; return missing models to `flowguard`.

## Required Workflow
1. Freeze the model, maturation/admission identities, blocks, state, fields, effects, and public entrypoints.
2. Recommend cohesive modules, single owners, facades/adapters, and observable leaves; record StructureMesh, Model-Test Alignment, or FieldLifecycleMesh handoffs.
3. For an explicit blueprint claim, fingerprint the exact model-element universe, disposition every required element, and emit reverse implementation-coverage obligations for the independent source audit.
4. Without exact current admission for the same task/model/scope, remain recommendation-only.

## Hard Gates

- Do not invent modules before responsibilities. Every write needs one owner; public facades and validation boundaries stay explicit; oversized leaves split or remain scoped.
- A diagram or nonempty map is not readiness. Omitted elements, missing reverse obligations, fingerprint drift, or scope beyond admission block blueprint use. This route neither scans source nor proves static closure.
- Route ArchitectureReduction only for a concrete evidence-backed contraction candidate. Any model/maturation/admission identity drift makes this recommendation stale.

## Output Requirements
- Return ownership map, and structure diagram; edges mean owns, calls, adapts, exposes, or validates. Blueprint adds depth/first gap, fingerprint, unresolved ids, and reverse obligations.

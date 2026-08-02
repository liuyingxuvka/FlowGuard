# FlowGuard Route Index

This is the only pre-selection route material. It projects the current `RouteProfile` registry; it selects an owner but does not execute a route or prove evidence.

## Decision rule

Extract task facts with request spans. Match those facts to positive and forbidden condition ids in the current route profiles. Select only an exact single public owner. Zero candidates means `no_match`; multiple candidates mean `conflict`; neither may be resolved by keyword score, declaration order, or a caller saying a route applies.

## Public owners

| Route | Use when | Exclude when | First action |
| --- | --- | --- | --- |
| `model_first_function_flow` / `flowguard` | ordinary behavior/state modeling, unclear owner, or cross-route coordination | trivial work or a clear satellite owner | extract facts and build the smallest faithful executable model |
| `existing_model_preflight` / `flowguard-existing-model-preflight` | an existing modeled system needs current ownership lookup | greenfield work without model context | audit observed authority and select a bounded owner closure |
| `behavior_commitment_ledger` / `flowguard-behavior-commitment-ledger` | broad external promises or commitment coverage must be inventoried | helper-only inventories | declare ledger mode and inventory admitted promises independently |
| `architecture_reduction` / `flowguard-architecture-reduction` | existing modeled implementation may shrink without behavior change | greenfield structure or intended behavior change | freeze the observable contract and reduction candidates |
| `code_structure_recommendation` / `flowguard-code-structure-recommendation` | target module/function ownership is needed before code | an existing large refactor already needs StructureMesh | map FunctionBlocks and state owners to target boundaries |
| `contract_exhaustion_mesh` / `flowguard-contract-exhaustion-mesh` | a declared finite universe needs canonical bad cases or Cartesian coverage | open-ended unbounded discovery | declare the finite universe, axes, and oracles |
| `development_process_flow` / `flowguard-development-process-flow` | staged work, multi-skill order, evidence freshness, sync, or release claims | one specialist semantic check with no lifecycle concern | register artifacts, peers, order, freshness, and execution owners |
| `field_lifecycle_mesh` / `flowguard-field-lifecycle-mesh` | fields or schemas are added, removed, renamed, migrated, or replaced | no field lifecycle change | inventory fields, readers/writers, projections, and old-field disposition |
| `model_mesh_maintenance` / `flowguard-model-mesh` | affected topology crosses model boundaries, a parent/child boundary changes, child evidence is stale, a model is oversized, or a whole-flow mesh claim is requested | several unrelated models whose boundaries do not interact | freeze the affected topology, parent/children, partition, and current child evidence |
| `model_miss_review` / `flowguard-model-miss-review` | runtime/test/replay evidence fails after a model was green | no observed failure | bind the miss to its current model and commitment owner |
| `model_test_alignment` / `flowguard-model-test-alignment` | model obligations, owner code contracts, and tests need comparison | test hierarchy only | list obligations, contracts, and current evidence |
| `model_topology_hazard_review` / `flowguard-model-topology-hazard-review` | locally green topology needs anchored future-use hazard review | an observed runtime failure, which belongs to Model Miss | bind usage intent to topology digest and hazard candidates |
| `structure_mesh_maintenance` / `flowguard-structure-mesh` | an existing large module/package/API must split with facade parity | pre-code structure planning only | freeze the public facade and partition inventory |
| `test_mesh_maintenance` / `flowguard-test-mesh` | validation is large, slow, stale, layered, background, or release-only | semantic alignment only | freeze parent claims, child checks, owners, and freshness |
| `ui_flow_structure` / `flowguard-ui-flow-structure` | UI states, journeys, controls, hierarchy, or operability are in scope | non-UI work | inventory UI states, controls, journeys, and recovery branches |

## After selection

Load only the selected skill. Its `Local Material Routing` names the first protocol. Further references require a named trigger: broad claim, prediction, Model Miss, ambiguity, high-impact gap, or still-addressable native gap. Once triggered, continue the route's model-predict-validate-revise loop until native closure or an explicit external, scoped, stalled, or bounded terminal reason.

Internal helpers and modes are reached only through their canonical public owner. They are not public aliases or fallback routes.

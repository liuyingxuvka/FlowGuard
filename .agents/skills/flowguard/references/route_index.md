# FlowGuard Route Index

This is the only pre-selection route material. It projects the current `RouteProfile` registry; it selects an owner but does not execute a route or prove evidence.

For a machine-readable capsule after a route id or skill name is known, run
`python -m flowguard route-reference <route-or-skill-name> --json`. That query
returns one current route and its lazy reference edges; it never returns the
complete route registry or loads the selected fragment.

## Decision rule

Extract task facts with request spans. Match those facts to positive and forbidden condition ids in the current route profiles. Select only an exact single public owner. Zero candidates means `no_match`; multiple candidates mean `conflict`; neither may be resolved by keyword score, declaration order, or a caller saying a route applies.

## Public owners

| Route | Use when | Exclude when |
| --- | --- | --- |
| `model_first_function_flow` / `flowguard` | ordinary behavior/state modeling, unclear owner, or cross-route work | trivial work or a clear satellite |
| `existing_model_preflight` / `flowguard-existing-model-preflight` | an existing model needs current ownership lookup | greenfield work without model context |
| `behavior_commitment_ledger` / `flowguard-behavior-commitment-ledger` | external promises or commitment coverage need inventory | helper-only inventories |
| `architecture_reduction` / `flowguard-architecture-reduction` | modeled implementation may shrink without behavior change | greenfield structure or intended behavior change |
| `code_structure_recommendation` / `flowguard-code-structure-recommendation` | module/function ownership is needed before code | existing large refactor needing StructureMesh |
| `contract_exhaustion_mesh` / `flowguard-contract-exhaustion-mesh` | a declared finite universe needs bad cases or Cartesian coverage | open-ended discovery |
| `development_process_flow` / `flowguard-development-process-flow` | staged order, freshness, sync, or release claims matter | one specialist semantic check |
| `field_lifecycle_mesh` / `flowguard-field-lifecycle-mesh` | fields/schemas are added, removed, renamed, migrated, or replaced | no field lifecycle change |
| `model_mesh_maintenance` / `flowguard-model-mesh` | topology crosses models, parent/child boundaries change, child evidence is stale, or mesh closure is requested | unrelated non-interacting models |
| `model_miss_review` / `flowguard-model-miss-review` | runtime/test/replay evidence fails after a model was green | no observed failure |
| `model_test_alignment` / `flowguard-model-test-alignment` | model obligations, code contracts, and tests need comparison | test hierarchy only |
| `model_topology_hazard_review` / `flowguard-model-topology-hazard-review` | green topology needs anchored future-use hazard review | observed runtime failure (Model Miss) |
| `structure_mesh_maintenance` / `flowguard-structure-mesh` | an existing large module/package/API must split with facade parity | pre-code structure planning |
| `test_mesh_maintenance` / `flowguard-test-mesh` | validation is large, slow, stale, layered, background, or release-only | semantic alignment only |
| `ui_flow_structure` / `flowguard-ui-flow-structure` | UI states, journeys, controls, hierarchy, or operability are in scope | non-UI work |

## After selection

Load only the selected skill and its first routed protocol. Load further references only for a named trigger. Helpers/modes remain behind their canonical public owner; the selected route profile remains the sole trigger/owner source.

The internal `agent_workflow_rehearsal` mode is a conditional exception, not a
second selection result: `flowguard-development-process-flow` may admit it
only for explicit rehearsal, cross-owner/shared-write,
post-validation-invalidating-write, agent/route-workflow-change, or
multiple-independent-owner-irreversible-side-effect facts. A normal task,
even one that mentions several skills/tools, must leave this mode
`not_triggered` and must not load its protocol.

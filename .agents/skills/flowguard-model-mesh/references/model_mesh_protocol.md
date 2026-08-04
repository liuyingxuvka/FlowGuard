# Local ModelMesh Routing Protocol

Use ModelMesh for affected topology, not model count. Several unrelated models
may remain independent; one changed child can require ModelMesh when a parent or
sibling consumes its boundary.

## Admission

Enter only when at least one current task fact shows:

- an affected relationship crosses model boundaries;
- a model is oversized, broad, incomplete, or classified model_too_thick;
- a parent/child partition or ownership boundary changed;
- child evidence is stale or a parent consumes a changed child;
- an affected sibling shares ownership, reads, effects, invariants, failures, or contracts;
- a parent whole-flow, hierarchical closure, or multi-model revision claim is requested.

Do not enter merely because the repository contains three or more models. Do
not split tests or code here, execute a portable joint graph, or treat
child-local green as parent proof.

An explicit whole-software blueprint claim is a whole-flow trigger only when
the model-system owner supplies the current observed snapshot plus the
independent implementation-inventory and binding identities. Ordinary tasks
continue selecting only affected models, ancestors, consumers, and siblings;
the existence of a blueprint never widens them to the whole model universe.

## Conditional references

Load only what the admitted signal needs:

- model_mesh_partition_protocol.md for inventory, target split, partitions,
  ownership, oversized models, and affected siblings.
- model_mesh_reattachment_protocol.md when a changed child or child receipt
  must plug back into parent/sibling contracts.
- model_mesh_closure_protocol.md for whole-flow closure, joins, loops, layered
  proof, portable handoff, or atomic model-system revision.
- templates/model_mesh_prompt_template.md only when delegating or scaffolding
  a fresh mesh.

## Shared shape

Keep the mesh finite. Record model ids, risk boundaries, inputs/outputs,
state/effect ownership, evidence tier/freshness, typed relations, affected
siblings, and explicit gaps. Useful blocks are:

Group compact prompts as `model`, `interface`, `ownership`, `evidence`, and
`deep_handoff`; these are presentation groups, not new authorities.

    InventoryAffectedTopology x State -> Set(ModelInventory x State)
    DeriveTargetPartition x State -> Set(PartitionDecision x State)
    CheckChildReattachment x State -> Set(ReattachmentReport x State)
    ReviewAffectedSiblings x State -> Set(SiblingReport x State)
    ReviewMeshClosure x State -> Set(ClosureReport x State)
    DecideMeshAuthority x State -> Set(ContinueOrBlock x State)

## Shared gates

- Start from the sole observed authority snapshot. Targets and experiments are candidates.
- One logical model has one snapshot instance; every governed path has one exact owner.
- Freeze task-specific protected failures and bind native good, bad-per-failure,
  oracle, candidate, and current evidence.
- Preserve stale, skipped, not-run, scoped, blocked, and progress-only states.
- Parent confidence requires complete partition ownership, current
  parent-consumed child receipts, affected-sibling review, and closure when
  whole-flow confidence is claimed.
- Consume the canonical `flowguard.portable_refinement.v1` result; do not build a second mesh-owned interpreter.
  Portable checker semantics remain owned by the portable refinement route.
- Feed reattachment, boundary, oversized-model, and duplicate-edge findings to
  Model Maturation under the exact TaskCoverageDemand; permission cannot close them.
- RiskLedger owns broad/scoped/blocked confidence. ModelMesh proves only the
  declared relationship boundary.
- For blueprint topology, every model has a reasoned `connected`,
  `intentional_leaf`, `delegated_or_supporting`, or `scoped_out` disposition
  plus meaningful purpose, producer/consumer, and realization references.
  Inventory and binding fingerprints are references only; source semantics,
  implementation disposition, and blueprint qualification remain with their
  native owners.
- ModelMesh never scans the repository or exports blueprint shards.

## Output

Return route trigger, loaded conditional references, affected topology,
partition/reattachment/closure decisions, evidence, failures, blockers,
skipped checks, residual risk, claim boundary, and typed next actions. Diagram
edges must say delegates, reattaches, consumes, affects, or blocks.

For blueprint topology, also return consumed inventory/binding fingerprints
and the exact missing purpose, consumer, or realization relation ids; do not
describe this relationship report as implementation proof.

## Blueprint Layer Contribution

ModelMesh contributes relationship/topology evidence to `traceability`: each
model has a current purpose, producer, consumer, relation, and realization
reference. It may consume exact `inventory`, `independent_semantics`,
`model_code_test`, and `resource_oracle` fingerprints, but it never copies or
reinterprets those owners' semantics and cannot qualify `static_blueprint`.

Whole-software topology is explicit-only. Ordinary work stays on affected
models, ancestors, consumers, and siblings. Report any supplied canonical
`deepest_proven_layer` unchanged plus the first unresolved native
owner/relation/evidence gap. Missing or ambiguous owners block; do not assign
the FlowGuard self-model or authoritative root as a target-software fallback.

User choice, model maturation, and implementation admission remain separate.
Portable exchange, combination, or language translation is a typed relation
use case selected only when that outcome is requested.

Blueprint topology references canonical normalized shared objects for owners,
contracts, semantics, oracles, tests, resources, and intent; it never duplicates
or rewrites them. Ordinary work starts from a verified
`AffectedBlueprintNeighborhood` and follows only declared behavior, support,
producer/consumer, ancestor, and sibling edges. A different shard layout with
the same logical content is not a model change.

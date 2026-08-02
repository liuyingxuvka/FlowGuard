# Understanding Plumbing Reduction

This record explains the behavior-preserving contraction used by the
FlowGuard self-understanding upgrade. It is deliberately separate from the
semantic completeness claim: fewer objects or branches do not prove deeper
understanding.

## Observable Contract

The preserved public behavior is:

- every public FlowGuard route keeps its current route and skill identity;
- task facts compile to explicit owner obligations and unresolved facts stay
  visible;
- one owner result binds the exact task, demand, obligations, and evidence;
- understanding sufficiency, user execution choice, and FlowGuard admission
  remain independent;
- the status API and CLI are read-only projections;
- Closure checks identity and material integrity, then preserves the one
  upstream RiskLedger terminal decision.

## Candidate Dispositions

| Candidate | Before | Current owner and action | Proof status |
| --- | --- | --- | --- |
| Route and skill lookup tables | route, skill, coverage, and admission identities could drift between independently maintained maps | `PublicOwnerDescriptor` in `flowguard/route_topology.py` is the one declaration; the existing maps are derived read-only projections | proven by route topology, API registry, self-maintenance, and retired-route known-bad tests |
| Coverage versus maturation owner results | task coverage and maturation could be populated through separate caller-authored evidence shapes | `OwnerCoverageResolution` in `flowguard/task_coverage_demand.py` is the single immutable result consumed by demand, maturation, receipts, and readiness | proven by exact task/demand/owner/fingerprint tests and forged-evidence failures |
| Closure decision logic | Closure could appear to make another route-specific confidence judgment | `flowguard/closure_contract.py` owns only identity/material blockers and projects the canonical RiskLedger full/scoped pair | proven by closure good/bad scenarios and upstream terminal-pair tests |
| Hierarchy activation count | a raw number of models could activate ModelMesh without explaining a semantic relation | semantic topology or a genuinely oversized individual model activates the mesh; the public `model_count` input is removed | proven by hierarchy scenarios and the raw-count non-activation regression |

No compatibility alias or fallback reader was added. The retired public route
ids `model_mesh`, `structure_mesh`, and `test_mesh` are rejected; their current
identities are `model_mesh_maintenance`, `structure_mesh_maintenance`, and
`test_mesh_maintenance`.

## Model-Derived Code Structure

The executable CodeStructureRecommendation review in
`tests/test_understanding_plumbing_reduction.py` assigns exactly one owner to
each function block:

```text
ResolvePublicOwner           -> route_topology
CompileTaskCoverageDemand    -> task_coverage_demand
ResolveOwnerCoverage         -> task_coverage_demand
ReviewModelMaturation        -> model_maturation
ComposeUnderstandingStatus   -> understanding_readiness
ReviewClosureIntegrity       -> closure_contract
```

The only new public entrypoints are `compose_understanding_status` and the
read-only `model-understanding-status` command, both owned by the readiness
facade. That facade has no execution, resume, publication, receipt-writing, or
filesystem-writing path.

## Field And Surface Lifecycle

| Surface | Disposition | Reason |
| --- | --- | --- |
| `review_hierarchical_mesh(..., model_count=...)` | removed | raw quantity did not express semantic topology; no compatibility alias is retained |
| retired public route ids | rejected | direct-current route identity prevents dual authority |
| `PublicOwnerDescriptor` | added, canonical | route, skill, coverage, and admission identity now have one source |
| `OwnerCoverageResolution` plus fingerprint | added, canonical | prevents the same owner result from being re-entered differently downstream |
| proof command/result path/timestamps/subject/fingerprint | required for current-pass use | caller-set `passed` or `current` is not execution evidence |
| understanding/user-choice/admission status keys | added, independent | a direct user choice cannot promote understanding or FlowGuard readiness |
| existing imports and route groups | preserved through direct projection | no second route or new skill was created |

The validation boundary is the affected import, serialization, route/API,
status CLI, maturation receipt, hierarchy, Closure, model regression, and full
release suite. A passing design review is pre-code structure evidence; only
the later executed checks count as implementation evidence.

## Pre-release Self-Blueprint Contraction Audit

The v0.68.5 release also runs ArchitectureReduction and StructureMesh against
the current FlowGuard self blueprint before the source freeze. The audit found
two byte-equivalent private helper families with current behavior-preserving
proof:

- eleven local string-to-tuple helpers now delegate to
  `flowguard._normalization.string_tuple`;
- eight local order-preserving string deduplicators now delegate to
  `flowguard._normalization.unique_strings`.

The contraction changed no public entrypoint, serialized field, output order,
state transition, side effect, or validation owner. Its affected parity set
passed 244 tests plus 41 subtests.

Eight remaining similarity families were reviewed and deliberately retained:
authority JSON loaders have separate trust boundaries; similar dataclasses are
different schemas; invariant and progress checks sit in different dependency
layers; risk vocabularies may diverge; process and plan freshness have
different evidence contracts; TestMesh and Model-Test Alignment own different
planes; and the final sequence helpers do not share one type contract. These
are typed `retain` dispositions, not forgotten cleanup. A future contraction
must bring new observable-equivalence evidence before changing them.

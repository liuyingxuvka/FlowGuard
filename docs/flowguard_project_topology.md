# FlowGuard Project Topology

This topology records the maintained route shape for FlowGuard itself. It is a
human-readable map; executable confidence still comes from models, tests,
OpenSpec validation, project audit, and route reports.

## Canonical Bad-Case Route

```text
Owning route declaration
-> ContractExhaustionMesh coverage universe
-> ContractExhaustionMesh case ids, shards, receipts, oracles, and fault profiles
-> Observed-problem backfeed for real misses
-> Composite handoff acceptance ids for multi-route closure
-> Model-Test Alignment / TestMesh / ModelMesh / Risk Evidence Ledger
-> DevelopmentProcessFlow freshness and final claim boundary
```

ContractExhaustionMesh is now the only canonical route for generated finite
bad-case ids. A matrix-ready report does not prove whole-chain readiness by
itself; broad confidence also needs the composite handoff acceptance ids to be
closed by the relevant route owners. Model-local Cartesian coverage also emits
coverage receipts; those receipts become parent ModelMesh and Risk Evidence
Ledger inputs rather than replacing parent closure. Broad/full claims must name
the coverage universe first, and observed misses must map back to generated and
same-class case ids or remain visible as model gaps. Existing routes remain
owners of their own declarations and evidence:

- StateClosure and ScenarioMatrix declare state/input and deterministic
  challenge cases.
- FieldLifecycleMesh declares fields, owners, projections, and old-field
  disposition.
- ObligationFamily and ModelMissReview declare family seeds and observed miss
  responsibility.
- ArtifactPayload declares file/work-package payload cases.
- TransitionCoverage and ModelMesh declare transition cells and parent/child
  closure hazards.
- Model-Test Alignment, TestMesh, ModelMesh, LayeredBoundaryProof, and Risk
  Evidence Ledger consume canonical case ids as proof requirements.

Old hand-written analogous-bug prompts, fallback same-class generators, and
compatibility-like generator paths are cleanup candidates unless they are the
current declaration owner, current evidence consumer, explicit public facade,
negative legacy test, or archive-only record.

## Public Route Control Plane

```text
User or agent request
-> public owner route
-> delegated mode or internal feeder evidence when needed
-> owner route report and obligations
-> Risk Evidence Ledger / DevelopmentProcessFlow final claim gates
```

Public route discovery is intentionally smaller than the full helper inventory.
`FLOWGUARD_ROUTE_API` and `ROUTE_STARTER_API` expose public owner routes only.
Helpers that still add useful structure stay available through advanced/helper
inventories, but they do not compete as first-stop routes.
The AI-facing route checklist lives in `default_flowguard_route_profiles()`:
when a route adds a new required output, downstream handoff, gate, shard, or
receipt, that route profile must be updated in the same change.

Current role shape:

- Public owner routes: self-maintenance, existing-model preflight,
  architecture reduction, code structure recommendation, model-test alignment,
  field lifecycle, ContractExhaustionMesh, risk template library, UI flow
  structure, ModelMesh, TestMesh, StructureMesh, DevelopmentProcessFlow,
  model-miss review, RiskEvidenceLedger, and topology hazard review.
- Delegated DevelopmentProcessFlow modes: PlanDetailing and
  AgentWorkflowRehearsal. They can be invoked explicitly, but ordinary rough
  plan and multi-skill workflow routing enters DevelopmentProcessFlow first.
- ExistingModelPreflight feeders: model-angle deliberation and model-similarity
  consolidation. They preserve candidate viewpoint and sibling-workflow
  evidence, then hand ownership back to ExistingModelPreflight or the selected
  public owner route.
- DevelopmentProcessFlow feeders: development-process simulator,
  maintenance-obligation memory, and maintenance-scan output. They decide or
  preserve process/freshness signals; they do not validate implementation,
  model/test alignment, or release confidence by themselves.
- ContractExhaustionMesh feeders: StateClosure, ScenarioMatrix, transition
  coverage, parent/child mesh closure, payload contracts, and model-miss family
  seeds. They declare finite boundaries; canonical bad-case ids are generated
  by ContractExhaustionMesh.

The maintenance rule is one current authority. A helper-first public route,
obsolete alias, fallback prompt, wrapper, or compatibility-like skill surface
must be deleted, absorbed into the owner route, or blocked. Ordinary software
history requires an explicit bounded compatibility contract.

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

Current guidance has no free lookalike search or fallback case generator. The
owner declares finite affected relations from commitment, blueprint, and
topology evidence; ContractExhaustionMesh alone materializes canonical bad
cases. Retired identities may remain only in negative tests or historical
records, never as a current route or completion authority.

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
- DevelopmentProcessFlow modes: delegated PlanDetailing, conditionally active
  DPF-owned process optimization (with the stable internal id
  `strategy_selection`), delegated AgentWorkflowRehearsal, and DPF-owned
  execution freshness. The internal order is plan detailing -> conditional
  optimization -> agent workflow -> execution freshness. Ordinary one-route
  work keeps optimization inactive; rough-plan and multi-skill routing still
  enters DevelopmentProcessFlow first, and no competing public route is added.
- ExistingModelPreflight consumes current commitment, blueprint, code-map, and
  topology evidence directly. When another owner has already declared an exact
  relation, the internal `CanonicalRelationHandoff` transports that edge
  without becoming a discovery or decision route.
- DevelopmentProcessFlow consumes development-process simulation,
  maintenance-obligation memory, changed-artifact identity, and freshness
  evidence directly. It reopens the exact affected owner route; no separate
  post-change scanner owns completion.
- ContractExhaustionMesh feeders: StateClosure, ScenarioMatrix, transition
  coverage, parent/child mesh closure, payload contracts, and model-miss family
  seeds. They declare finite boundaries; canonical bad-case ids are generated
  by ContractExhaustionMesh.

The maintenance rule is latest-schema-first. A helper-first public route,
obsolete alias, fallback prompt, wrapper, or compatibility-like surface must be
deleted, absorbed into the owner route, converted to an internal helper, or
kept only as an explicitly proven public facade.

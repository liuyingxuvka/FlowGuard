## Context

FlowGuard has strong but distributed mechanisms for finding bad cases:
StateClosure covers missing/unknown/malformed state and input boundaries;
ScenarioMatrix covers repeated, delayed, and reordered input routes;
ObligationFamily and model-miss helpers cover same-class sibling risks;
ArtifactPayload validation covers import/export and work-package surfaces;
TransitionCoverage projects finite transition cells; ModelMesh and layered
proof cover parent/child closure, stale child evidence, and retry/no-delta
handoffs.

The weakness is not that these tools cannot find bad cases. The weakness is
that they can each become a separate source of case ids, evidence language, and
same-class coverage claims. Agents can patch the observed bug, hand-write a
few sibling cases, and accidentally bypass the stronger finite boundary
coverage that FlowGuard should produce from declared contracts.

The current project rules also require latest-schema-first behavior and no
long-lived fallback or compatibility branches unless explicitly preserved with
current evidence. This design therefore consolidates case generation without
creating a compatibility wrapper around older routes.

## Goals / Non-Goals

**Goals:**

- Add one canonical bad-case generation layer for declared finite contract
  boundaries.
- Make every generated bad case stable, traceable, and evidence-bindable through
  `ContractMutationCase` ids.
- Require every generated case to have an explicit `ContractOracle` before it
  can support full confidence.
- Convert existing state, scenario, same-class, payload, transition, and mesh
  case sources into feeders or consumers instead of parallel canonical
  generators.
- Preserve existing route ownership for classification, validation, mesh
  closure, test evidence, architecture reduction, and risk closure.
- Make model gaps visible when similarity or boundary dimensions have not been
  declared.
- Remove old prompt and helper wording that allows hand-written same-class
  cases to stand in for canonical finite expansion.
- Keep installed skill copies synchronized after repository updates.

**Non-Goals:**

- Do not promise infinite-world bug discovery. The route only exhausts declared
  finite boundaries or explicit finite equivalence classes.
- Do not replace BugFamily, ModelMissReview, Model-Test Alignment, TestMesh,
  ModelMesh, LayeredBoundaryProof, ArchitectureReduction, or RiskEvidenceLedger.
- Do not introduce a fallback path from the new mesh back to old hand-written
  same-class case generation.
- Do not preserve old aliases, wrappers, or compatibility prompt paths unless
  ArchitectureReduction/StructureMesh classifies them as current public
  contracts or required safety classifiers.

## Decisions

### Decision: Add a thin `contract_exhaustion` module

Add `flowguard/contract_exhaustion.py` with dataclasses and a review helper:

- `ContractDimension`: a declared finite or scoped contract boundary.
- `ContractMutationCase`: one generated bad case from a dimension.
- `ContractOracle`: expected response for a mutation case.
- `ContractExhaustionPlan`: inputs, dimensions, seed cases, source bug refs,
  and generation policy.
- `ContractExhaustionReport`: generated cases, missing oracles, unbounded
  dimensions, model gaps, route handoffs, findings, and decision.

Rationale: this creates one canonical case language without moving route
internals into a new mega-flow.

Alternative considered: update each existing route in place. Rejected because
it would keep multiple case id surfaces and make future maintenance harder.

### Decision: Treat existing generators as feeders

StateClosure, ScenarioMatrix, ObligationFamily, ArtifactPayload,
TransitionCoverage, and ModelMesh closure helpers should expose adapter
functions into `ContractMutationCase`. They retain their domain-specific
review logic but no longer own canonical same-class or finite-boundary coverage
claims when contract exhaustion is required.

Rationale: this keeps proven helpers stable while removing duplicate
case-generation authority.

Alternative considered: delete the older helpers. Rejected because they still
own useful domain decomposition, candidate synthesis, and review behaviors.

### Decision: Keep closure routes as consumers

Model-Test Alignment, TestMesh, ModelMesh, LayeredBoundaryProof, and
RiskEvidenceLedger consume canonical case ids and report current evidence.
They do not generate canonical cases.

Rationale: proof responsibility remains where existing FlowGuard models already
place it.

Alternative considered: let ContractExhaustionMesh perform validation. Rejected
because it would become another large orchestrator and duplicate mature routes.

### Decision: Make missing declarations explicit gaps

If a route receives a bug-family seed but no sibling relation, evidence
currentness rule, payload surface, parent/child contract, or oracle is declared,
the report records a model gap or missing-oracle blocker. It does not infer a
passing result from prose or fallback rules.

Rationale: users need to know whether FlowGuard truly exhausted a declared
boundary or merely lacked the model to do so.

Alternative considered: generate best-effort cases with `needs_human_review`
and allow scoped pass. Rejected for required cases because it can overclaim
same-class coverage. Optional candidate cases may remain scoped.

### Decision: New skill is a route satellite, not a process front door

Add `.agents/skills/flowguard-contract-exhaustion-mesh`. It instructs agents to
use ExistingModelPreflight first, produce canonical cases/oracles, and hand off
to existing proof routes. DevelopmentProcessFlow remains the lifecycle front
door for staged implementation and final confidence.

Rationale: users asked for a clean path, not a new mega-workflow. A thin skill
makes routing discoverable while keeping orchestration in existing owners.

### Decision: No fallback or compatibility surface

Old same-class prompts, fallback generators, old aliases, wrappers, and
compatibility-like case paths are cleanup candidates. If one is public, route
it through ArchitectureReduction/StructureMesh as a facade decision. Otherwise
remove, replace, or rewrite it to call the canonical path.

Rationale: parallel compatibility paths would recreate the maintenance problem
this change is meant to solve.

## Risks / Trade-offs

- **Risk: ContractExhaustionMesh becomes too broad.** Mitigation: keep it to
  dimensions, cases, oracles, and handoff ids; no test execution, family
  promotion, or final risk closure.
- **Risk: Existing tests depend on old same-class case outputs.** Mitigation:
  preserve old helpers as feeders and update tests to verify projection into
  canonical cases.
- **Risk: Missing oracles block more work at first.** Mitigation: this is the
  intended safety boundary. Required cases without oracles should block or
  scope confidence rather than pass.
- **Risk: Documentation and installed skills drift.** Mitigation: update repo
  docs, `.agents/skills`, installed local Codex skills, and run
  project audit plus focused tests before final confidence.
- **Risk: Other agents are editing nearby files.** Mitigation: use scoped
  patches, inspect current state before editing, and do not revert unrelated
  changes.

## Migration Plan

1. Add the OpenSpec capability and implementation types.
2. Add adapter functions from stable existing feeders.
3. Update proof routes to accept and display canonical case ids where needed.
4. Update skills and docs to route same-class and finite boundary case
   generation through ContractExhaustionMesh.
5. Add tests for required generation, missing-oracle blockers, model gaps, and
   old-route projection.
6. Remove or rewrite old prompt wording that presents hand-written same-class
   cases as canonical coverage.
7. Sync installed skills and run project audit plus focused/full validation.

Rollback strategy is not a compatibility branch. If this change must be backed
out during development, revert the OpenSpec change and code edits as one
unfinished implementation. Do not leave both canonical and old same-class
generation routes active as alternatives.

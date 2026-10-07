# development-process-strategy-selection Specification

## Purpose
Define how DevelopmentProcessFlow selects and revises a bounded execution strategy only after proving equivalent outcomes and obligations, while preserving diagnostics, repair grouping, affected revalidation, and honest optimality boundaries.
## Requirements
### Requirement: Hard outcome equivalence precedes process optimization
The system SHALL compare process effort, rework, coordination, information value, or measured cost only among current candidates that satisfy the same declared terminal outcome, validation obligations, evidence boundary, safety constraints, protected side effects, dependency authority, and execution-owner boundary. A candidate SHALL cite current equivalence evidence rather than copying those owner structures into an optimizer-owned outcome contract.

#### Scenario: Shorter candidate lacks required evidence
- **WHEN** a candidate appears lower effort but omits a required validation or evidence obligation
- **THEN** the system excludes it before comparison and does not recommend it

#### Scenario: Candidate copies another owner's authority
- **WHEN** a candidate invents provider tasks, model obligations, or code owners instead of citing their current owner evidence
- **THEN** hard equivalence is unproven and optimization is blocked

### Requirement: Strategy selection is multi-objective and bounded
The system SHALL compare process effort, rework, coordination, information value, or measured cost only among current candidates that satisfy the same declared terminal outcome, validation obligations, evidence boundary, safety constraints, protected side effects, dependency authority, and execution-owner boundary. A candidate SHALL cite current equivalence evidence rather than copying those owner structures into an optimizer-owned outcome contract. When the complete declared candidate set contains exactly one candidate, the system SHALL still enforce every hard admissibility check but MAY select that sole eligible route without requiring cost vectors or Pareto comparison; it SHALL describe the route as un-compared and SHALL NOT claim a minimum, Pareto result, or cost superiority. Any malformed cost value or stale/missing reference that the caller did provide SHALL remain a finding. When more than one candidate is declared, the existing complete comparison requirements SHALL apply even if hard filtering leaves only one eligible candidate.

#### Scenario: Interleaved derived artifacts cause repeat work
- **WHEN** one eligible sequence writes documentation, inventories, installation projections, or release evidence before a later step invalidates their source identity while another equivalent sequence freezes source first and writes those artifacts once
- **THEN** the system assigns the interleaved sequence invalidated-output and repeated-write cost and selects the freeze-first sequence when its complete derived score is uniquely lower

#### Scenario: Caller preselects a higher-cost candidate
- **WHEN** the caller names an eligible candidate whose derived score is higher than another current hard-equivalent candidate
- **THEN** the system rejects that preference and returns the model-derived lower-cost candidate or a visible inconsistency rather than endorsing the supplied id

#### Scenario: Eligible candidates tie
- **WHEN** two current hard-equivalent candidates have the same complete derived score
- **THEN** the system exposes the tied candidate ids and does not silently claim that declaration order, lexical order, or an unsupported caller preference is optimal

#### Scenario: Measured cost input is incomplete
- **WHEN** a candidate in a declared multi-candidate set claims `comparison_basis=measured` but one declared step lacks comparable effort input or required cost evidence is not current
- **THEN** measured selection is blocked instead of treating missing cost as zero

#### Scenario: One declared candidate passes hard admissibility without ranking
- **WHEN** the complete declared candidate set contains exactly one candidate and all required hard outcome, evidence, safety, dependency, isolation, currentness, and owner checks pass
- **THEN** the system selects that candidate as the only admissible declared route without requiring a cost vector or running Pareto comparison
- **AND** the result makes clear that no cost comparison or minimum claim was produced

#### Scenario: Invalid supplied cost data remains rejected for one candidate
- **WHEN** the complete declared candidate set contains exactly one candidate and the candidate supplies a malformed cost, stale cost evidence, or an invalid reference
- **THEN** hard or reference validation reports the exact finding instead of ignoring the supplied invalid data

#### Scenario: A multi-candidate declaration does not use the single-candidate path
- **WHEN** the declared set contains more than one candidate but hard admissibility leaves only one eligible candidate
- **THEN** the system retains the declared multi-candidate comparison requirements and SHALL NOT use the single-candidate fast path

#### Scenario: Multiple-route reason has only one declaration
- **WHEN** the activation reason claims multiple equivalent routes but the complete declared set contains only one candidate
- **THEN** the system reports the contradiction and does not treat the incomplete declaration as a complete one-route universe

### Requirement: Diagnostic campaign completeness is explicit
The system SHALL delegate diagnostic execution accounting to TestMesh, where every planned item is executed or visibly not run, the selected diagnostic boundary is recorded, count relationships are consistent, and every not-run item has a reason. The optimizer SHALL reference current TestMesh and Finding Ledger identities without owning a duplicate campaign or observation structure.

#### Scenario: Campaign stops at a declared budget
- **WHEN** a `budgeted` campaign reaches its declared stop condition with planned work remaining
- **THEN** the campaign may be valid while every not-run item and reason remains visible

#### Scenario: Campaign falsely claims declared completeness
- **WHEN** `diagnostic_boundary=declared_complete` has an unexecuted or unaccounted planned item
- **THEN** TestMesh and the dependent optimizer claim are blocked

### Requirement: Failure clustering and repair batching preserve traceability
The system SHALL preserve every raw Finding Ledger id, SHALL create a compact repair group only when current relation evidence supports grouping, SHALL record a root-cause claim and disproof checks, and SHALL bind the group to repair actions, `affected_obligation_ids`, current ordinary Model-Test Alignment `owner_evidence_ids`, required revalidation ids, and current revalidation evidence ids. A repair group SHALL NOT replace, rewrite, or hide its source findings.

#### Scenario: Related failures share one repair
- **WHEN** several raw findings have current evidence for one shared root-cause claim
- **THEN** one repair group may cover them while retaining every original finding id, relation evidence id, and disproof check

#### Scenario: Grouping evidence is absent
- **WHEN** two failures share wording but have no current causal or structural relation evidence
- **THEN** the system keeps them separate instead of manufacturing one root cause

#### Scenario: Repair group has no affected revalidation
- **WHEN** a repair group claims completion without current evidence for all affected revalidation requirements
- **THEN** the group and every dependent completion claim are blocked

### Requirement: Material new evidence triggers strategy re-evaluation
The system SHALL bind an optimization decision to one input revision and current decision evidence. A new finding, changed assumption, dependency or owner change, peer write, verifier change, completed repair group, or other material evidence SHALL stale the old decision through DPF freshness and require a new or reaffirmed current decision before execution continues under an enforced optimization claim.

#### Scenario: Second failure changes the root-cause claim
- **WHEN** a new finding materially changes candidate eligibility or the repair grouping
- **THEN** the old decision becomes stale and execution is blocked until current decision evidence selects or reaffirms a candidate

### Requirement: Optimization composes diagnostic boundary and execution mode
The internal `strategy_selection` mode SHALL represent process choice through composable `diagnostic_boundary` values `targeted`, `declared_complete`, or `budgeted`, plus `execution_mode` values `sequential` or `safe_parallel`. Each candidate SHALL declare an acyclic dependency graph and an ordered step list that is a valid linearization of that graph. Hard invalidation, safety, dependency, or declared-order failures SHALL be universal stop conditions rather than selectable strategies; material new evidence SHALL stale every active decision rather than requiring an `adaptive` candidate. The six former policy names SHALL NOT remain a current successful vocabulary.

#### Scenario: Declared order violates a dependency
- **WHEN** a candidate lists a derived projection or release step before the source-freeze, self-audit, or validation step that its dependency graph requires
- **THEN** that candidate is ineligible even if its graph is acyclic and its terminal outcome label matches

#### Scenario: Independent work is proposed in parallel
- **WHEN** two steps have no dependency edge or shared mutable state but current dependency, state, side-effect, and execution-owner isolation evidence is incomplete
- **THEN** `safe_parallel` remains ineligible and sequential execution is retained

### Requirement: Process optimization is conditional and has an inactive path
The system SHALL create optimization candidates and details only for an explicit optimization request, multiple outcome-equivalent viable routes, material repeated-work risk, or a real diagnostic-boundary choice. An ordinary single-route task SHALL remain valid with an empty reason set, no optimization decision, and a `not_needed` status.

#### Scenario: Ordinary staged task has one clear route
- **WHEN** a task has one valid execution sequence and no material repeated-work or diagnostic-boundary choice
- **THEN** DPF proceeds without candidate tables, cost vectors, frontiers, clusters, or repair groups

### Requirement: Optimizer complexity remains bounded
The current implementation SHALL add no public skill, route, commitment, or model owner; SHALL use at most five optimizer dataclasses in total and at most six public optimizer symbols; SHALL keep every hard-equivalence, derived-order, cost, tie, freshness, and closure gate; and SHALL leave zero current-runtime residuals for retired policy, rollout, Pareto, duplicate projection, alias, wrapper, or dual-reader surfaces. Source layout SHALL remain normally readable and SHALL NOT satisfy a mechanical line budget by placing independent field declarations, statements, or report arguments on the same physical line. A private formatting or source-line count is not a behavior authority.

#### Scenario: New ordering behavior reaches the former line ceiling
- **WHEN** complete dependency, artifact, cost, rationale, and tie behavior no longer fits the former 500-nonblank-line formatting limit without code compression
- **THEN** the implementation keeps one public route and the six-symbol surface while retaining ordinary readable formatting instead of code-golfing or adding a second owner

#### Scenario: Simplification adds another public optimizer path
- **WHEN** implementation introduces a new public route, review function, compatibility wrapper, or successful old vocabulary
- **THEN** architecture-reduction closure is blocked even if focused tests are green

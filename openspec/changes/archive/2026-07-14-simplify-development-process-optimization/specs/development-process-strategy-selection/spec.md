## MODIFIED Requirements

### Requirement: Hard outcome equivalence precedes process optimization
The system SHALL compare process effort, rework, coordination, information value, or measured cost only among current candidates that satisfy the same declared terminal outcome, validation obligations, evidence boundary, safety constraints, protected side effects, dependency authority, and execution-owner boundary. A candidate SHALL cite current equivalence evidence rather than copying those owner structures into an optimizer-owned outcome contract.

#### Scenario: Shorter candidate lacks required evidence
- **WHEN** a candidate appears lower effort but omits a required validation or evidence obligation
- **THEN** the system excludes it before comparison and does not recommend it

#### Scenario: Candidate copies another owner's authority
- **WHEN** a candidate invents provider tasks, model obligations, or code owners instead of citing their current owner evidence
- **THEN** hard equivalence is unproven and optimization is blocked

### Requirement: Strategy selection is multi-objective and bounded
The system SHALL expose the eligible candidates, selected candidate, comparison basis, current comparison evidence, and selection rationale. `comparison_basis` SHALL be `qualitative` or `measured`; qualitative evidence, including bounded estimates or structural rules, MUST NOT be described as a measured minimum, and no result may claim an unrestricted global optimum. DPF MAY retain a bounded minimum claim only for a complete declared finite revalidation set with current measured inputs.

#### Scenario: Comparison uses estimates
- **WHEN** eligible routes are compared from estimated effort or rework evidence
- **THEN** the system describes one route as preferred under current declared evidence and does not emit a numeric optimum or Pareto-frontier claim

#### Scenario: Measured finite revalidation set is exhausted
- **WHEN** every candidate in a declared finite revalidation set is current, equivalent, and has comparable measured cost
- **THEN** DPF may claim a minimum only within that named finite set

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

## ADDED Requirements

### Requirement: Optimization composes diagnostic boundary and execution mode
The internal `strategy_selection` mode SHALL represent process choice through composable `diagnostic_boundary` values `targeted`, `declared_complete`, or `budgeted`, plus `execution_mode` values `sequential` or `safe_parallel`. Hard invalidation, safety, or dependency failures SHALL be universal stop conditions rather than a `fail_fast` candidate; material new evidence SHALL stale every active decision rather than requiring an `adaptive` candidate. The six former policy names SHALL NOT remain a current successful vocabulary.

#### Scenario: Correlated cheap diagnostics
- **WHEN** remaining diagnostics are bounded, valid, inexpensive, and likely to expose a shared cause
- **THEN** an eligible candidate may use `declared_complete` or `budgeted` with sequential or safely parallel execution before repair

#### Scenario: Destructive prerequisite failure
- **WHEN** continuing diagnostics would be invalid, unsafe, or meaningless after a hard prerequisite failure
- **THEN** the system stops, exposes every not-run descendant, and does not pretend that diagnostic completeness was reached

#### Scenario: Parallel execution lacks isolation evidence
- **WHEN** a candidate selects `safe_parallel` without current dependency, mutable-state, side-effect, and execution-owner isolation evidence
- **THEN** that candidate is ineligible

### Requirement: Process optimization is conditional and has an inactive path
The system SHALL create optimization candidates and details only for an explicit optimization request, multiple outcome-equivalent viable routes, material repeated-work risk, or a real diagnostic-boundary choice. An ordinary single-route task SHALL remain valid with an empty reason set, no optimization decision, and a `not_needed` status.

#### Scenario: Ordinary staged task has one clear route
- **WHEN** a task has one valid execution sequence and no material repeated-work or diagnostic-boundary choice
- **THEN** DPF proceeds without candidate tables, cost vectors, frontiers, clusters, or repair groups

### Requirement: Optimizer complexity remains bounded
The current implementation SHALL add no public skill, route, commitment, or model owner; SHALL use at most five optimizer dataclasses in total and at most six public optimizer symbols; SHALL keep every hard-equivalence and closure gate instead of shrinking the contract to meet an arbitrary field count; and SHALL leave zero current-runtime residuals for retired policy, rollout, Pareto, duplicate projection, alias, wrapper, or dual-reader surfaces.

#### Scenario: A simplification adds another public optimizer path
- **WHEN** implementation introduces a new public route, review function, compatibility wrapper, or successful old vocabulary
- **THEN** architecture-reduction closure is blocked even if focused tests are green

## REMOVED Requirements

### Requirement: Strategy vocabulary remains adaptive
**Reason**: The six labels mix diagnostic scope, execution topology, stop behavior, and replanning into mutually exclusive policies, making ordinary decisions harder to express and validate.

**Migration**: Replace them directly with `diagnostic_boundary` plus `execution_mode`; treat hard blockers and material-change replanning as universal rules. No former strategy label remains a successful current value.

### Requirement: Rollout is staged without parallel success paths
**Reason**: The shadow/advisory/opt-in/conditional-default rollout state adds a second policy dimension and permits ordinary tasks to carry optimizer ceremony. The optimizer is now conditionally admitted from stable reason codes and has one current implementation.

**Migration**: Delete rollout fields and constants. Empty activation reasons mean `not_needed`; active reasons require one current decision. No old rollout value, alias, or fallback success path remains in normal runtime.

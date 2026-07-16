## ADDED Requirements

### Requirement: Hard outcome equivalence precedes process optimization
The system SHALL compare process cost only among current candidates that satisfy the same declared terminal outcome, evidence obligations, safety constraints, protected side effects, and authority-owner boundary.

#### Scenario: Shorter candidate lacks required evidence
- **WHEN** a candidate has lower estimated effort but omits a required evidence obligation
- **THEN** the system excludes it from cost comparison and does not recommend it

### Requirement: Strategy selection is multi-objective and bounded
The system SHALL expose the eligible candidates, component cost vectors, Pareto frontier, deterministic recommendation, and one of `valid`, `non_dominated_within_candidates`, or `minimum_within_declared_finite_boundary`; it MUST NOT claim an unrestricted global minimum.

#### Scenario: Candidate inventory is partial
- **WHEN** two eligible candidates are non-dominated and the candidate inventory is not declared complete
- **THEN** the system returns the deterministic recommendation with a `non_dominated_within_candidates` boundary and preserves the other frontier candidate

#### Scenario: Finite boundary is exhausted
- **WHEN** every candidate in a named finite boundary is current, eligible or explicitly excluded, and has comparable cost
- **THEN** the system may claim `minimum_within_declared_finite_boundary` for the selected candidate

### Requirement: Strategy vocabulary remains adaptive
The system SHALL support `fail_fast`, `collect_all`, `focused_first`, `bounded_collect`, `parallel_shards`, and `adaptive` candidates and SHALL decide eligibility from declared urgency, safety, independence, correlation, rework, and evidence constraints rather than a universal preferred strategy.

#### Scenario: Destructive urgent failure
- **WHEN** continuing diagnostics would violate a safety constraint
- **THEN** collection candidates are ineligible and a valid fail-fast candidate can be recommended

#### Scenario: Correlated cheap diagnostics
- **WHEN** remaining diagnostics are bounded, safe, inexpensive, and likely to expose a shared cause
- **THEN** a collect-all or bounded-collect candidate can dominate repeated fail-fix cycles

### Requirement: Diagnostic campaign completeness is explicit
The system SHALL account every planned diagnostic item as executed or visibly not run, SHALL distinguish complete enumeration from early stop, and SHALL require a reason for every not-run item.

#### Scenario: Campaign stops after first failure
- **WHEN** a campaign has unexecuted planned items and records an early-stop reason
- **THEN** the campaign can be valid but enumeration completeness remains false

#### Scenario: Campaign falsely claims completeness
- **WHEN** a planned item is neither executed nor recorded as not run
- **THEN** the strategy review is blocked

### Requirement: Failure clustering and repair batching preserve traceability
The system SHALL preserve raw observation identities, require evidence for cluster membership, link root-cause hypotheses and disproof checks, and bind repair batches to clusters, owned artifacts, and required revalidation.

#### Scenario: Related failures share one repair
- **WHEN** several observations have current evidence for one shared root-cause hypothesis
- **THEN** one repair batch may cover them while retaining every observation and cluster identity

#### Scenario: Repair batch has no revalidation
- **WHEN** a batch claims completion without current evidence for its required revalidation ids
- **THEN** the batch and any dependent completion claim are blocked

### Requirement: Material new evidence triggers strategy re-evaluation
The system SHALL require a re-evaluation record when new observations, changed assumptions, or repair completion can change candidate eligibility, cost, or minimum revalidation.

#### Scenario: Second failure changes the root-cause hypothesis
- **WHEN** a new observation materially changes the selected candidate assumptions
- **THEN** execution under the old recommendation is blocked until a current re-evaluation selects or reaffirms a candidate

### Requirement: Rollout is staged without parallel success paths
The system SHALL support `shadow`, `advisory`, `opt_in`, and `conditional_default` policy stages through one implementation and SHALL block only when the active stage and scope require a current strategy decision.

#### Scenario: Advisory rollout
- **WHEN** the stage is advisory and a strategy report has gaps
- **THEN** the gaps remain visible but do not independently block an otherwise valid DPF plan

#### Scenario: Opt-in enforcement
- **WHEN** the caller opts in to strategy enforcement
- **THEN** missing or stale strategy evidence blocks the process claim

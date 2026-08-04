## Purpose

Defines how FlowGuard determines whether a supported software blueprint is behaviorally detailed, independently grounded, compactly consumable, and ready to guide reimplementation without automatically rebuilding the software.

## ADDED Requirements

### Requirement: Blueprint depth distinguishes four claims
FlowGuard SHALL distinguish owner-level structural closure, behavior-block closure, reconstruction readiness, and empirical reconstruction as separate claims with separate evidence identities.

#### Scenario: Owner map is complete but behavior contracts are coarse
- **WHEN** every implementation surface has one model owner but one or more behavior-bearing surfaces lack independent behavior contracts
- **THEN** owner-level structural closure SHALL be complete
- **AND** behavior-block closure and reconstruction readiness SHALL remain incomplete

#### Scenario: Reconstruction has not been requested
- **WHEN** static behavior and resource requirements are satisfied and no empirical reconstruction request exists
- **THEN** reconstruction readiness MAY be `ready`
- **AND** empirical reconstruction SHALL remain `not_run`

### Requirement: Behavior-bearing surfaces have reimplementable contracts
Every behavior-bearing implementation surface SHALL bind a source-independent contract expressed as `Input x State -> Set(Output x State)` with explicit input, output, state/effect, error, decision, completion, and applicable order, retry, and timeout meanings. Pure helpers MAY close through one unique supporting owner relation.

#### Scenario: Generic owner text is copied across unrelated behavior blocks
- **WHEN** several behavior-bearing surfaces share only one generic owner-level semantic statement without surface-specific applicability
- **THEN** behavior-block closure SHALL report the exact uncovered surfaces
- **AND** the generic text SHALL NOT satisfy those contracts

#### Scenario: A dimension is not applicable
- **WHEN** retry, timeout, ordering, state, effect, or another contract dimension does not apply to a behavior-bearing surface
- **THEN** that surface SHALL contain a typed not-applicable disposition with a reviewable reason

### Requirement: Reconstruction readiness is read-only and gap-complete
FlowGuard SHALL provide a read-only reconstruction-readiness decision with status `ready`, `incomplete`, `stale`, or `blocked`, bound to the exact blueprint fingerprint and the complete unresolved-gap set. The decision SHALL NOT launch reconstruction or modify the target project.

#### Scenario: Several readiness gaps exist
- **WHEN** behavior, resource, test, or intent gaps coexist
- **THEN** the decision SHALL report every known gap in the declared denominator rather than stopping at the first gap

#### Scenario: Ordinary work requests status
- **WHEN** an AI asks whether understanding is deep enough before implementation
- **THEN** FlowGuard SHALL return compact depth, readiness, first gap, and gap-count information without materializing the full blueprint

### Requirement: Resource completeness uses an independent denominator
Blueprint qualification SHALL use an independently derived project resource inventory covering build, runtime, dependency, configuration, schema, data, asset, migration, external-service, and behavioral-oracle categories. Every required member SHALL be `current`, `external`, `scoped_out`, or `blocked`.

#### Scenario: A caller omits an entire resource category
- **WHEN** project evidence indicates a required database, service, configuration, migration, or build input that is absent from the supplied resource rows
- **THEN** resource closure and reconstruction readiness SHALL be incomplete

### Requirement: Intent lineage participates in readiness
Blueprint readiness SHALL bind the current intent inventory fingerprint and terminal disposition of every admitted intent contribution. A non-trivial revision with an empty contribution set SHALL require a typed, evidence-bound no-declared-intent rationale.

#### Scenario: A change claims historical intent with no contributions
- **WHEN** a non-trivial blueprint revision describes intent lineage but its current intent inventory is empty and has no accepted no-intent rationale
- **THEN** intent closure and reconstruction readiness SHALL be incomplete

### Requirement: Candidate blueprints are honest by construction
For a supported project, FlowGuard SHALL be able to discover candidate files, surfaces, tests, resources, and possible owners without treating inferred semantics or ownership as accepted. Candidate generation SHALL be read-only by default and SHALL expose unresolved rows for independent completion.

#### Scenario: Candidate semantics come only from source inspection
- **WHEN** candidate semantics are inferred from implementation source without an independent accepted intent, contract, or oracle
- **THEN** the candidate SHALL remain unresolved and SHALL NOT qualify behavior-block closure

#### Scenario: Unsupported language is encountered
- **WHEN** no registered deep discovery adapter exists for the project language
- **THEN** candidate generation SHALL return a visible missing-adapter blocker rather than shallow success

### Requirement: Blueprint projections are normalized and affected-loadable
FlowGuard SHALL store shared owner, semantic, oracle, test, and receipt identities once and SHALL use content-addressed references from behavior-surface rows. Ordinary work SHALL load only the affected owner/behavior neighborhood, while full qualification SHALL prove canonical equivalence to the complete logical blueprint.

#### Scenario: Shared test evidence covers several surfaces
- **WHEN** one exact test member legitimately covers several behavior surfaces
- **THEN** the shared evidence object SHALL be stored once
- **AND** every covered surface SHALL have its own explicit coverage edge

#### Scenario: Projection layout changes without semantic change
- **WHEN** normalized sharding changes physical layout but preserves canonical logical content
- **THEN** the logical blueprint fingerprint and qualification result SHALL remain stable

### Requirement: Independent semantics and oracles cannot self-license
Reconstruction readiness SHALL report circular support when a behavior contract and its sole oracle are both derived only from the same implementation source without an independent intent, requirement, domain rule, counterexample, or witnessed behavior boundary.

#### Scenario: Code explains and validates itself
- **WHEN** source-derived semantics and a source-derived oracle are the only evidence for a behavior block
- **THEN** the block SHALL remain incomplete for reconstruction readiness
- **AND** the report SHALL name the missing independent source role


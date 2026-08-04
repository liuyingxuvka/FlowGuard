# target-system-blueprint Specification

## Purpose
Define one provider-neutral blueprint contract that can describe software, workflows, services, agents, data pipelines, and mixed systems without making a source language the core authority.

## Requirements

### Requirement: Target-system blueprints are provider-neutral
FlowGuard SHALL identify a target by target-system id, target kind, subject revision, declared boundary, and required provider capabilities. The core blueprint contract SHALL NOT require a programming language, repository layout, or executable software target.

#### Scenario: Declared workflow has no source language
- **WHEN** a bounded workflow supplies current observation and authority providers without a programming-language identity
- **THEN** FlowGuard SHALL evaluate it through the same target-system blueprint contract
- **AND** it SHALL NOT classify the target kind as unsupported solely because no source language exists

#### Scenario: Mixed target uses several provider kinds
- **WHEN** a target combines source code, workflow declarations, documentation, traces, and external contracts
- **THEN** the blueprint SHALL compose the exact provider results under one target and subject revision
- **AND** each result SHALL retain its own claim boundary

### Requirement: Providers report evidence rather than readiness
Every provider result SHALL identify its provider role, provider id and version, target id, subject revision, consumed-input fingerprint, result fingerprint, status, findings, and claim boundary. Providers SHALL contribute observations or independent authority but SHALL NOT directly declare the canonical blueprint ready.

#### Scenario: Required provider is missing
- **WHEN** the descriptor requires a discovery or authority capability for which no current provider result exists
- **THEN** FlowGuard SHALL report the exact missing capability as a blueprint gap
- **AND** it SHALL NOT replace the missing provider with inferred shallow success

#### Scenario: Provider result targets another revision
- **WHEN** a supplied provider result names a different target or subject revision
- **THEN** FlowGuard SHALL reject it as stale or mismatched for the current blueprint

### Requirement: Blueprint readiness follows one ordered chain
FlowGuard SHALL calculate evidence qualification, static blueprint readiness, and task admission as distinct ordered results.

#### Scenario: Evidence qualifies but static blueprint has gaps
- **WHEN** inventories and identities qualify but a required semantic, portable, helper, resource, intent, or test binding is incomplete
- **THEN** evidence qualification MAY be complete
- **AND** static blueprint readiness SHALL remain incomplete or blocked
- **AND** a whole-target DNA claim SHALL remain unavailable

#### Scenario: Scoped task does not require whole-target readiness
- **WHEN** an affected-only task has current evidence for its complete affected neighborhood while unrelated whole-target gaps remain
- **THEN** task admission MAY allow only that declared scope
- **AND** the result SHALL continue to report the broader blueprint gaps

### Requirement: Every behavior has an implementation-independent contract
Every behavior block required by the declared boundary SHALL bind exact implementation surfaces, source-independent semantic rules, portable model and transition identities, field mappings, assumptions, guarantees, invariants, protected failure boundaries, and applicable or typed-not-applicable behavior dimensions.

#### Scenario: Owner text is copied to several behaviors
- **WHEN** multiple behavior blocks reuse generic owner text without an explicit shared rule, exact applicability rows, and independent provenance
- **THEN** those behavior blocks SHALL remain incomplete

#### Scenario: Portable binding is stale
- **WHEN** a behavior block cites a portable model, transition, property, or field mapping whose fingerprint no longer matches current authority
- **THEN** the exact behavior block and binding SHALL be reported stale

### Requirement: Supporting surfaces require evidence-bound ownership
A supporting surface SHALL close only through one or more explicit ownership edges whose kinds and current evidence establish how it calls, delegates, reads for, or writes for exact behavior blocks. Sorting order, lexical similarity, or shared owner identity SHALL NOT select a behavior owner.

#### Scenario: Helper has two possible owners
- **WHEN** a helper can be associated with multiple behavior blocks but no current evidence distinguishes the relation
- **THEN** FlowGuard SHALL report ambiguous supporting ownership
- **AND** it SHALL NOT choose the first behavior block

### Requirement: Test coverage binds real members and cases
Static blueprint readiness SHALL require every formal coverage edge to reference an existing behavior block, implementation surface, test node or native check, concrete case, oracle member, oracle identity, and covered dimensions. Test design and execution evidence SHALL be stored and reported separately.

#### Scenario: Synthetic identifiers imitate a real test
- **WHEN** a coverage row names a generated placeholder test, assertion, or universal case that is absent from the current test inventory
- **THEN** the row SHALL NOT satisfy static blueprint coverage

#### Scenario: Current test has not run in this cycle
- **WHEN** a real current test, case, and oracle edge exists but no current execution receipt exists
- **THEN** static test design MAY be complete
- **AND** execution status SHALL remain `not_run`

### Requirement: Compact understanding is an affected projection
FlowGuard SHALL expose a read-only compact summary containing the exact blueprint identity, layer statuses, deepest proven layer, first gap, gap count, and affected surface ids. Ordinary affected-only queries SHALL NOT require loading the whole blueprint.

#### Scenario: AI asks whether it understands enough
- **WHEN** an AI requests task admission for an affected scope
- **THEN** FlowGuard SHALL return the compact affected summary and exact unresolved boundary
- **AND** it SHALL NOT replace the result with a self-authored confidence statement

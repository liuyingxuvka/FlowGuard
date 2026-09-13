## Purpose

Provide a finite, usable model map for a small consumer project so first adoption, local navigation, affected updates, and one pointer-last authority commit form a complete observable lifecycle without requiring unrelated whole-system proof.

## ADDED Requirements

### Requirement: First adoption yields a current-readable observed authority

A consumer with a finite manifest of one or more active models SHALL be able to complete first adoption by accepting the current intent and publishing exactly one observed implementation head that the normal current-authority reader can load. A bootstrap candidate, incomplete intent, or unaccepted generation SHALL not be reported as current.

#### Scenario: Two-model consumer completes first adoption
- **WHEN** a consumer supplies its two model definitions, runners, exact inputs, intent sources, owner bindings, and finite coverage evidence
- **THEN** the system accepts one current revision and publishes one observed head
- **AND** a normal current-model read succeeds without reading FlowGuard's author-suite models

#### Scenario: Initial intent or owner evidence is missing
- **WHEN** any model's initial intent, exact owner binding, required leaf receipt, or required connection evidence is absent
- **THEN** adoption returns the exact missing obligation and does not publish a current head

### Requirement: Basic navigation is independent from deep projection

A consumer SHALL be able to ask for a basic map of an exact model/input owner without requesting deep projection, author maintenance, installation, or release evidence. The result SHALL distinguish authority integrity, selected-source currentness, and execution evidence.

#### Scenario: Basic navigation without deep projection
- **WHEN** a valid current head contains an exact model/input binding and the caller requests basic navigation only
- **THEN** the system returns the selected model, declared dependencies, and as-of status with zero producers and zero writes
- **AND** missing deep projection does not turn the basic navigation result into an overall failure

#### Scenario: Selected input is stale
- **WHEN** one selected model/input changed after the accepted head
- **THEN** the system returns the last accepted map and the exact stale obligation
- **AND** it does not claim current execution or automatically activate a replacement

### Requirement: Affected updates preserve unrelated map entries

For an ordinary change, the system SHALL select the changed model and every typed parent, connection, and consumer that actually depends on it. Unrelated model entries SHALL remain navigable and eligible for exact evidence reuse.

#### Scenario: Alpha changes while beta is independent
- **WHEN** alpha's implementation and declared behavior change while beta and its dependencies remain identical
- **THEN** alpha and its typed connections are stale or revalidated
- **AND** beta remains available for navigation and is not treated as changed solely by global discovery

#### Scenario: A cross-model connection really depends on alpha
- **WHEN** a declared beta consumer uses alpha's changed interface
- **THEN** the connection and beta consumer obligation are included in the affected closure
- **AND** omitting that connection is a coverage failure rather than a successful optimization

### Requirement: Pointer-last commit does not re-run validated functional producers

After the selected model content, code, contracts, or necessary tests are validated, the system SHALL commit the accepted candidate and activation binding exactly once. A change only to generation, head, activation receipt, reverse binding, report, or task status SHALL trigger finite binding/integrity checks and SHALL NOT invalidate or re-run the already validated functional producers.

#### Scenario: Same candidate receives a new authority binding
- **WHEN** an accepted candidate is bound to a new generation and activation receipt without changing selected model content or its dependencies
- **THEN** the pointer binding is checked once and the functional owner identities remain current
- **AND** no leaf, native model runner, or full functional suite is started

#### Scenario: Selected model content changes
- **WHEN** the model payload, contract, oracle, or resolved functional input selected by the new pointer differs
- **THEN** only that model's affected closure is invalidated and revalidated
- **AND** the system does not classify the content change as a pointer-only update

### Requirement: Terminal completion is finite and non-reopening

A consumer completion claim SHALL use one stable work identity with a bounded initial attempt and at most one typed repair attempt. Reading a terminal result, writing a report, or changing a task checkbox SHALL not create a new functional attempt.

#### Scenario: Terminal result is read after a report update
- **WHEN** a completed local claim receives a report or task-checkbox update
- **THEN** the same terminal result remains readable with zero new producers, epochs, or leases

#### Scenario: Attempt budget is exhausted
- **WHEN** the initial attempt and its one typed repair both fail
- **THEN** the system returns a finite terminal failure with the unresolved check and evidence path
- **AND** it does not change the work identity or silently launch a third attempt

## ADDED Requirements

### Requirement: Project-neutral blueprint APIs extend the existing kernel cohort
The public API registry SHALL expose project-neutral construction, audit, test-inventory, binding, qualification, affected-neighborhood, and deterministic projection APIs through the existing FlowGuard kernel API cohort. These APIs SHALL operate on explicit project definitions and native owner evidence without introducing a new public route, `DNA` skill, or alternate authority cohort.

#### Scenario: A consumer builds another Python project's blueprint
- **WHEN** a consumer supplies a project root, bounded project definition, supported Python discovery adapter, and current owner inputs
- **THEN** the kernel cohort exposes the project-neutral builder and qualification result
- **AND** the consumer does not import FlowGuard's self-blueprint preset

#### Scenario: FlowGuard builds its own blueprint
- **WHEN** FlowGuard invokes self-blueprint qualification
- **THEN** its preset delegates to the same public project-neutral APIs
- **AND** no duplicate FlowGuard-only builder owns the generic semantics

#### Scenario: A generic API name is missing or duplicated
- **WHEN** registry compilation finds an expected blueprint API absent, duplicated, or assigned to a conflicting route group
- **THEN** the API-registry check fails with the exact name and owner conflict
- **AND** package export cannot claim the project-neutral cohort current

### Requirement: API results expose layered understanding without executing reconstruction
Project-neutral API results SHALL expose the deepest proven understanding layer, per-layer statuses, exact findings and owners, implementation admission status when supplied by its native owner, and empirical reconstruction status. Calling construction, inventory, audit, qualification, affected-neighborhood, or projection preparation APIs SHALL NOT launch reconstruction.

#### Scenario: Static blueprint is complete without reconstruction
- **WHEN** all static layers pass and no reconstruction receipt is supplied
- **THEN** the API reports static blueprint complete and reconstruction `not_run`
- **AND** the result remains successful for a static-only claim

#### Scenario: Reconstruction is explicitly required for a claim
- **WHEN** the caller requests a reconstruction-qualified claim but supplies no matching current receipt
- **THEN** the API reports the empirical layer `not_run` and the requested claim blocked
- **AND** it does not schedule or execute reconstruction

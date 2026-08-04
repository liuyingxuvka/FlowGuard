## MODIFIED Requirements

### Requirement: Project-neutral blueprint APIs extend the existing kernel cohort
The public API registry SHALL expose provider-neutral target-system descriptor, provider declaration/registry/result, frozen snapshot, compiler, understanding projection, and project-specialized inventory/binding/qualification APIs through the existing FlowGuard kernel API cohort. These APIs SHALL operate on explicit target definitions and native provider evidence without introducing a new public route, `DNA` skill, or alternate authority cohort.

#### Scenario: A consumer builds a non-Python target blueprint
- **WHEN** a consumer supplies a target descriptor, frozen provider registry and snapshot, current observation and authority results, and downstream layer results
- **THEN** the kernel cohort exposes the provider-neutral compiler and qualification result
- **AND** the consumer does not import FlowGuard's Python self-blueprint preset

#### Scenario: FlowGuard builds its own blueprint
- **WHEN** FlowGuard invokes self-blueprint qualification
- **THEN** its software preset delegates to the same public target-system and project-neutral APIs
- **AND** no duplicate FlowGuard-only builder owns the generic semantics

#### Scenario: A generic API name is missing or duplicated
- **WHEN** registry compilation finds an expected target-system or blueprint API absent, duplicated, or assigned to a conflicting route group
- **THEN** the API-registry check fails with the exact name and owner conflict
- **AND** package export cannot claim the provider-neutral cohort current

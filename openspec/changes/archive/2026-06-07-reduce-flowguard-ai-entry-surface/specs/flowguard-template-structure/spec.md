## MODIFIED Requirements

### Requirement: Route-scoped template ownership
FlowGuard SHALL store route template bodies in route-scoped internal modules
while preserving `flowguard.templates` as the public compatibility facade.

#### Scenario: Existing compact facade remains compatible
- **WHEN** a caller imports the default model-miss, model-test-alignment, or
  UI-flow template factory from `flowguard.templates`
- **THEN** the factory emits a compact runnable template for that route

#### Scenario: Full template facade is explicit
- **WHEN** a caller needs the deep scaffold for model-miss,
  model-test-alignment, or UI-flow structure
- **THEN** a corresponding full-template factory and CLI command emits the full
  route template files

### Requirement: Template split has parity evidence
The system SHALL validate compact and full template facade behavior with public
template tests and CLI smoke coverage.

#### Scenario: Compact template text is validated
- **WHEN** route template text is loaded
- **THEN** public template tests verify runnable templates, risk-purpose
  headers, private-marker scans, line budgets, and required safety gate text

#### Scenario: Full template remains discoverable
- **WHEN** full template commands are inspected
- **THEN** CLI smoke tests verify they print and write the deep route template
  files without replacing the compact defaults

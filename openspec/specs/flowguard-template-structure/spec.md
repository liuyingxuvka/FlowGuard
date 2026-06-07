# flowguard-template-structure Specification

## Purpose

Define route-scoped template ownership while preserving the public
`flowguard.templates` compatibility facade.

## Requirements

### Requirement: Route-scoped template ownership
FlowGuard SHALL store route template bodies in route-scoped internal modules
while preserving `flowguard.templates` as the public compatibility facade.

#### Scenario: Existing facade remains compatible
- **WHEN** a caller imports template constants or template writer functions from
  `flowguard.templates`
- **THEN** the same public names remain importable and generate equivalent
  template files

#### Scenario: Template CLI remains compatible
- **WHEN** a caller runs an existing `python -m flowguard *-template` command
- **THEN** the command still emits or writes the expected route template files

### Requirement: Template split has parity evidence
The system SHALL validate template facade parity with public template tests and
CLI smoke coverage after route template bodies move out of the monolithic file.

#### Scenario: Split template text is validated
- **WHEN** route template text is loaded from internal modules
- **THEN** public template tests verify runnable templates, risk-purpose
  headers, private-marker scans, and CLI command dispatch

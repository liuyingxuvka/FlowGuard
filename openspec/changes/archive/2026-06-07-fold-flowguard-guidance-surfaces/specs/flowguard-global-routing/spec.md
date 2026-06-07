## ADDED Requirements

### Requirement: Global routing does not duplicate satellite internals
Global FlowGuard routing SHALL name the selected route and hand off to the
owning satellite or reference without duplicating satellite-specific workflow
internals in multiple prompt surfaces.

#### Scenario: Reusable AGENTS guidance stays compact
- **WHEN** the reusable AGENTS snippet is read
- **THEN** it contains the global routing decision, hard gates, thin default
  path, and compact route table
- **AND** it does not embed long helper inventories or route-specific prompt
  templates

#### Scenario: Route-specific detail is needed
- **WHEN** the selected route needs detailed helper APIs, hazard lists,
  examples, or prompt templates
- **THEN** the guidance points to the owning satellite reference or docs page
  instead of duplicating that detail in the global routing hot path

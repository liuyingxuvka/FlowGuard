## ADDED Requirements

### Requirement: DevelopmentProcessFlow consumes plan-detail lifecycle rows
DevelopmentProcessFlow SHALL accept plan-detail projections as a lifecycle starting point for artifacts, actions, evidence, validation requirements, and freshness rules.

#### Scenario: Plan-detail projection supplies lifecycle registry
- **WHEN** plan-detail rows declare artifacts, ordered steps, produced evidence, required evidence, and validation requirements
- **THEN** the projected DevelopmentProcessPlan uses those rows for ordinary freshness and claim review

#### Scenario: Later action stale evidence remains blocked
- **WHEN** a projected plan changes an artifact after validation evidence was produced
- **THEN** DevelopmentProcessFlow reports the evidence as stale using the projected artifact and evidence ids

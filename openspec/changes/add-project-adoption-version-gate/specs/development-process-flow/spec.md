## ADDED Requirements

### Requirement: Project adoption upgrade participates in process freshness
DevelopmentProcessFlow SHALL treat project FlowGuard adoption and upgrade
records as versioned process artifacts when a staged done, release, archive, or
publish claim depends on current FlowGuard guidance.

#### Scenario: FlowGuard guidance changes after validation
- **WHEN** a claim depends on FlowGuard Skill guidance or project adoption rules
- **AND** the FlowGuard package, managed AGENTS block, or project manifest has
  changed after the validation evidence was produced
- **THEN** DevelopmentProcessFlow reports that the prior evidence must be
  revalidated or the claim must be scoped

#### Scenario: Adoption log alone is insufficient
- **WHEN** an adoption or upgrade log entry exists but the required model/test
  validation evidence is missing or stale
- **THEN** DevelopmentProcessFlow does not treat the log entry as sufficient
  completion evidence

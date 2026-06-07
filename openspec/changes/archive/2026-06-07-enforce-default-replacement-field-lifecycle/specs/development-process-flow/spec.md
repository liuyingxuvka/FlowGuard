## ADDED Requirements

### Requirement: Field lifecycle evidence participates in freshness
DevelopmentProcessFlow SHALL treat field lifecycle meshes, field projections,
replacement decisions, old-field dispositions, model-code-test binding rows,
and bug repair closure rows as versioned artifacts that can stale validation
evidence.

#### Scenario: Field mesh changes after alignment
- **WHEN** a field lifecycle artifact changes after Model-Test Alignment
  evidence was produced
- **THEN** DevelopmentProcessFlow MUST mark the alignment evidence stale and
  recommend rerunning the owner route

#### Scenario: Bug repair field evidence changes
- **WHEN** a field root-cause record, same-class field case, owner code
  contract, old-field disposition, or old-path disposition changes after bug
  repair validation
- **THEN** DevelopmentProcessFlow MUST report bug repair closure stale before
  done or release confidence

## ADDED Requirements

### Requirement: Architecture Reduction classifies old fields
Architecture Reduction SHALL classify old fields, field aliases, compatibility
field adapters, migration field branches, and retired field validation evidence
before contraction or replacement cleanup is claimed ready.

#### Scenario: Old field is a prune candidate
- **WHEN** an old field exists only for a replaced behavior
- **AND** current field lifecycle and model-code-test evidence prove the new
  field covers the behavior
- **THEN** Architecture Reduction MAY classify the old field as a prune
  candidate subject to implementation and validation gates

#### Scenario: Old field has runtime authority
- **WHEN** an archive-only or compatibility field can still affect runtime
  behavior
- **THEN** Architecture Reduction MUST block removal readiness until runtime
  authority is removed, delegated, migrated, or explicitly preserved with
  evidence

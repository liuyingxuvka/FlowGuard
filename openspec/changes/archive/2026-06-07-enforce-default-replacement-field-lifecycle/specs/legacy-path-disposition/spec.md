## ADDED Requirements

### Requirement: Replacement closure includes old-field disposition
Legacy path disposition SHALL support replacement closure that records old
field disposition alongside old path disposition.

#### Scenario: Old field disposition blocks closure
- **WHEN** replacement work proves a new field or new path
- **AND** an old in-scope field remains with missing or unknown disposition
- **THEN** strict replacement closure MUST remain blocked

#### Scenario: Old field is migrated
- **WHEN** an old field is retained only for migration to a new field
- **THEN** disposition evidence MUST name the migration proof, new field id,
  owner code contract, and test evidence before full confidence

## ADDED Requirements

### Requirement: Field and side-effect changes join the revision set
Every added, changed, replaced, removed, externalized, or compensated
behavior-bearing field or side effect SHALL be declared in the owning model
revision set and bound to its base and candidate snapshots.

#### Scenario: Two models share a replaced field
- **WHEN** a revision changes a field written by one model and read by another
- **THEN** both model owners, the field lifecycle row, migration disposition, and affected tests close in the same revision set

#### Scenario: Member passes but field migration is incomplete
- **WHEN** all candidate model checks pass but an old field remains an undeclared successful reader or writer
- **THEN** revision-set activation is blocked

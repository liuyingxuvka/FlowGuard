## ADDED Requirements

### Requirement: Generated field lifecycle inventory
FlowGuard SHALL provide a generated field inventory that lists dataclass fields with module owner, class owner, field name, inferred lifecycle layer, and behavior-bearing hints before field deletion or folding decisions are made.

#### Scenario: Field-bearing module is audited
- **WHEN** the field inventory generator scans FlowGuard modules
- **THEN** the generated report includes field rows grouped by module and lifecycle layer

#### Scenario: Field cleanup is proposed
- **WHEN** a future maintenance task proposes removing fields
- **THEN** the field inventory is current or the task records why field inventory evidence is scoped out


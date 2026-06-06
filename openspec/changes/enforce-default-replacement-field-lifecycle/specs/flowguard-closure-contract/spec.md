## ADDED Requirements

### Requirement: Closure consumes field lifecycle and replacement evidence
FlowGuard Closure Contract SHALL consume current field lifecycle, field
projection, old-field disposition, old-path disposition, model-code-test
alignment, bug repair, freshness, and risk evidence before reporting full done,
release, publish, or production confidence for field or replacement work.

#### Scenario: Field lifecycle evidence is missing
- **WHEN** a broad completion claim depends on field-heavy behavior or feature
  replacement
- **AND** no current field lifecycle evidence is supplied
- **THEN** closure review MUST block or scope the claim

#### Scenario: Unknown disposition blocks full closure
- **WHEN** an in-scope old path or old field has unknown disposition
- **THEN** closure review MUST NOT return full confidence

#### Scenario: Complete field replacement closure passes
- **WHEN** field lifecycle evidence, behavior projections, owner code
  contracts, external-contract tests, old path/field dispositions, process
  freshness, and risk ledger evidence are all current and passing
- **THEN** closure review MAY support full confidence for the field replacement
  claim

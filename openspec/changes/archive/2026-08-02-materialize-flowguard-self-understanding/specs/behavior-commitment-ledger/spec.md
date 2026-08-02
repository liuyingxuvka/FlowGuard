## ADDED Requirements

### Requirement: Understanding and admission behaviors have one primary implementation owner
The behavior ledger SHALL register task-demand derivation, maturation receipt publication and verification, implementation admission, broad-confidence decision, and closure integrity with exactly one current primary implementation owner each.

#### Scenario: Two modules claim primary confidence ownership
- **WHEN** more than one current implementation owner claims the final broad-confidence behavior
- **THEN** the ledger audit fails with duplicate primary ownership

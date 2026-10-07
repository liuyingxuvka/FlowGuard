## ADDED Requirements

### Requirement: Exact resolution basis
Maturation SHALL authenticate resolutions against the original demand basis and bind the exact derived closed demand to its plan, report and canonical receipt. A task-context producer SHALL publish actual closed or blocked maturation evidence independently of native execution.

#### Scenario: A coverage resolution closes an original obligation
- **WHEN** a coverage resolution closes an original obligation
- **THEN** The original basis remains authenticated and the closed demand cannot be substituted or forged.


## MODIFIED Requirements

### Requirement: Test evidence hierarchy exposes child evidence status

FlowGuard SHALL keep child test evidence status visible before a parent test
gate can support routine or release confidence.

#### Scenario: Parent gate requires leaf matrix-cell evidence
- **WHEN** a parent TestMesh declares required leaf matrix-cell ids
- **THEN** each required cell id MUST be owned by a registered child suite or
  script with current passing evidence
- **AND** missing, stale, skipped, running, progress-only, or background
  incomplete leaf-cell evidence MUST block parent confidence

#### Scenario: Leaf matrix-cell suite does not name cells
- **WHEN** a child suite is marked as leaf matrix-cell evidence but does not
  name which cell ids it proves
- **THEN** TestMesh MUST block with a missing leaf-cell ownership finding

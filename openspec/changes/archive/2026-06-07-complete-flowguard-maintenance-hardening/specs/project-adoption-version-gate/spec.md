## ADDED Requirements

### Requirement: Shadow workspace sync helper
FlowGuard SHALL provide a tracked shadow sync helper that can copy complete source sets into a shadow workspace, optionally refresh editable install metadata, and verify import path, package version, schema version, and a named helper in the target workspace.

#### Scenario: Shadow verification succeeds
- **WHEN** the shadow sync helper runs with verification enabled after copying source sets
- **THEN** it reports the target import path, metadata version, schema version, and helper availability

#### Scenario: Shadow verification fails
- **WHEN** the target workspace import path, package version, schema version, or helper availability does not match expectations
- **THEN** the helper exits non-zero and reports the mismatched field


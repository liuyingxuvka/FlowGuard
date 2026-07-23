## ADDED Requirements

### Requirement: Oversized modules split behind one current facade
StructureMesh SHALL allow internal splits of oversized modules only when one
canonical public facade, dependency direction, configuration ownership,
serialization parity, finding-code parity, and affected test evidence are
declared.

#### Scenario: Internal module split preserves public behavior
- **WHEN** implementation moves behind the existing facade and import, CLI, JSON, finding order, and side-effect parity all pass
- **THEN** StructureMesh may close the split without creating a second public route

#### Scenario: Parity is incomplete
- **WHEN** a proposed split has no evidence for one public output or side effect
- **THEN** the existing module remains authoritative and the split stays a registered candidate

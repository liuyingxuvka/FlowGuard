## ADDED Requirements

### Requirement: Lightweight evidence gate structures
FlowGuard SHALL provide lightweight evidence gate/detail structures for broad
evidence models so future route code can group related gate fields without
breaking existing dataclass constructors.

#### Scenario: Risk evidence gates can be grouped
- **WHEN** a risk evidence row needs model, test, family, or analogous-scan gate
  state
- **THEN** that gate state can be represented as a small reusable gate object
  while legacy row fields remain compatible

#### Scenario: Process evidence details can be grouped
- **WHEN** process evidence includes command status, background status, or mesh
  split status
- **THEN** that status can be represented as a focused detail object while
  legacy process evidence fields remain compatible

### Requirement: Compatibility conversion is explicit
The system SHALL keep compatibility conversion helpers explicit so lightweight
objects do not silently replace stronger route-specific proof.

#### Scenario: Lightweight object does not overclaim
- **WHEN** a lightweight evidence object is converted into a legacy plan or row
- **THEN** skipped, stale, progress-only, and missing proof states remain
  visible to the existing review helper

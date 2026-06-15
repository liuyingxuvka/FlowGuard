## ADDED Requirements

### Requirement: Repeated-input closure loops need feedback and blocker tokens
ModelMesh closure transitions SHALL represent retry, wait, and rejection-like
loops with structured repeated-input, progress, repair-feedback, and blocker
tokens so no-delta retry behavior cannot be hidden behind prose.

#### Scenario: Repeated input loop lacks feedback
- **WHEN** a closure transition is loop-like
- **AND** it declares repeated input tokens
- **AND** it has no repair feedback tokens
- **THEN** the closure review SHALL report a repair-feedback finding
- **AND** green closure SHALL be blocked

#### Scenario: Repeated input loop lacks blocker
- **WHEN** a closure transition is loop-like
- **AND** it declares repeated input tokens
- **AND** it has no blocker tokens, progress tokens, or max-iteration bound
- **THEN** the closure review SHALL report a no-delta blocker finding
- **AND** green closure SHALL be blocked

#### Scenario: Rejection retry loop is explicitly guarded
- **WHEN** a loop-like closure transition declares repeated input tokens
- **AND** it emits repair feedback and a blocker or progress token
- **THEN** the closure review SHALL NOT block solely because the loop can retry
  rejected input

## ADDED Requirements

### Requirement: Closure consumes model-angle review evidence
FlowGuard Closure Contract SHALL consume model-angle review evidence when broad
confidence depends on an agent's open-ended model sufficiency review.

#### Scenario: Required model-angle evidence is missing
- **WHEN** closure requires model-angle review evidence
- **AND** no current model-angle report or closure evidence row is supplied
- **THEN** closure MUST block full FlowGuard confidence

#### Scenario: Model-angle evidence is scoped or blocked
- **WHEN** supplied model-angle evidence reports scoped, blocked, stale, or unresolved required angles
- **THEN** closure MUST downgrade or block the broad claim according to that evidence

## ADDED Requirements

### Requirement: Implementation admission requires verified sufficiency and separate permission
DevelopmentProcessFlow SHALL issue `ready` or `ready_scoped` only when the exact task has a current eligible maturation receipt and independently evidenced implementation authorization. `no_code_requested` and `blocked` SHALL remain distinct terminal states.

#### Scenario: Model is sufficient but code was not authorized
- **WHEN** the maturation receipt verifies as closed but the task contains no current implementation authorization
- **THEN** admission returns `no_code_requested` and does not weaken the maturation result

#### Scenario: Code is authorized but model is insufficient
- **WHEN** authorization is current but the maturation receipt is blocked, stale, or incomplete
- **THEN** implementation admission returns `blocked`

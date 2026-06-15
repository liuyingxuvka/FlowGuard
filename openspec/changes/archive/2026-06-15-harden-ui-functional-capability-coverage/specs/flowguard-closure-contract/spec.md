## ADDED Requirements

### Requirement: Final UI claims require functional capability coverage
FlowGuard ClosureContract SHALL require current UI functional capability coverage before final statements claim that a UI is complete, runnable, release-ready, or implemented for in-scope user-visible functions.

#### Scenario: UI closure has capability coverage
- **WHEN** a closure plan requires UI functional capability coverage
- **AND** a current full-confidence capability coverage report is supplied
- **THEN** capability coverage does not block final UI closure confidence

#### Scenario: UI closure lacks capability coverage
- **WHEN** a final UI claim covers user-visible functionality
- **AND** no current capability coverage report is supplied
- **THEN** ClosureContract blocks broad UI release confidence or scopes the claim below full functional completion

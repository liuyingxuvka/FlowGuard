## ADDED Requirements

### Requirement: Transition cells can bind code contracts

Transition coverage cells SHALL support direct code-contract and runtime-node
targets so state transitions can be locked to implementation and tests.

#### Scenario: Transition cell names code owner
- **WHEN** a transition coverage cell declares a code contract id
- **THEN** generated alignment evidence can verify that tests prove the code
  contract implementing the projected transition obligation.

#### Scenario: Transition cell lacks code owner in full confidence claim
- **WHEN** a required transition-derived obligation is reviewed for full
  confidence
- **AND** no code contract owner is bound to that transition obligation
- **THEN** Model-Test Alignment SHALL block or scope the claim.

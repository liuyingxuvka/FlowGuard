## ADDED Requirements

### Requirement: Model-miss counterexamples project into Model-Test Alignment closure
Post-runtime Model-Miss Review SHALL require in-scope known-bad and
counterexample misses to be projected into Model-Test Alignment as
target-aware external regression evidence.

#### Scenario: Counterexample repair closes through owner code
- **WHEN** a model miss is represented by a concrete counterexample trace
- **AND** the repair is claimed broadly
- **THEN** the repaired obligation SHALL have current external
  `counterexample_regression` test evidence bound to the owner code contract
  and the counterexample target id

#### Scenario: Known-bad repair closes through replay
- **WHEN** a model miss or known-bad proof is in scope for the repair
- **AND** the repair is claimed broadly
- **THEN** the repaired obligation SHALL have current external
  `known_bad_replay` test evidence bound to owner code and the known-bad target
  id, or an explicit scoped-out reason outside the broad claim

## ADDED Requirements

### Requirement: Bug repair closure binds model, code, and tests
For an in-scope bug repair, FlowGuard SHALL block broad closure unless the
repaired bug class has a current model obligation, an owner code contract, and
current observed-regression plus same-class test evidence bound to the same
behavior.

#### Scenario: Model-code-test repair chain passes
- **WHEN** a repaired bug class has a model-miss-origin obligation
- **AND** an owner code contract implements that obligation
- **AND** current observed-regression and same-class generalized test evidence
  cover both the model obligation and the owner code contract
- **THEN** Model-Test Alignment may report the repair row as green

#### Scenario: Test does not bind code owner
- **WHEN** a bug repair has model and test evidence
- **AND** the test evidence does not cover the owner code contract that
  implements the repaired obligation
- **THEN** full bug repair closure is blocked or scoped

### Requirement: Bug repair closure records old-path disposition
FlowGuard SHALL require existing compatibility classification and
LegacyPathDisposition evidence before full confidence is restored for an
in-scope bug repair with reachable old paths, fallbacks, aliases, replay paths,
recovery paths, or compatibility adapters.

#### Scenario: Old path is dispositioned
- **WHEN** a repaired bug class had an old or fallback path that remains
  reachable
- **THEN** closure evidence records whether the path was deleted, blocked,
  delegated to the repaired contract, repaired to the same contract, or
  explicitly scoped out

#### Scenario: Old path remains unknown
- **WHEN** an old or fallback path may still execute with unknown disposition
- **THEN** full bug repair closure remains blocked

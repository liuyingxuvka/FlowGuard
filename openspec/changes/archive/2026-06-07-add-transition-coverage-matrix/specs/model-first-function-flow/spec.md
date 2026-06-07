## ADDED Requirements

### Requirement: Model-first coverage claims derive transition obligations
The model-first FlowGuard kernel SHALL require transition coverage projection, or an explicit scoped-out reason, before broad claims that modeled behavior has matching test coverage.

#### Scenario: Broad coverage claim uses transition matrix
- **WHEN** a model-first workflow claims broad model-to-test coverage for state transitions
- **THEN** the workflow derives a transition coverage matrix and passes generated obligations to Model-Test Alignment or routes large evidence to TestMesh

#### Scenario: Transition matrix is scoped out
- **WHEN** a workflow intentionally does not derive a transition coverage matrix
- **THEN** the final claim MUST state the scoped-out reason and MUST NOT claim full transition-to-test coverage

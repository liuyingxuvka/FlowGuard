## ADDED Requirements

### Requirement: Blueprint coverage binds exact test members and dimensions
For each behavior-bearing surface, blueprint alignment SHALL enumerate exact coverage rows containing model obligation, semantic rule, owner code contract, implementation surface, test node, assertion or native-check member, parameter or subtest case identity, covered dimensions, evidence role, oracle, execution owner, and terminal execution disposition.

#### Scenario: Owner test collection is copied to every surface
- **WHEN** a model owner has several behavior surfaces and a test collection does not enumerate which assertions cover which surfaces
- **THEN** alignment SHALL report missing exact coverage rows
- **AND** the collection SHALL NOT automatically cover every surface

#### Scenario: Native checker exists but has no current execution result
- **WHEN** a native checker member and runner fingerprint exist but no current terminal receipt is bound
- **THEN** static checker design SHALL remain visible
- **AND** execution status SHALL be `not_run` rather than `pass`

### Requirement: Test definition and execution evidence remain separate
Model-Test Alignment SHALL distinguish the admitted test source member, the checker or assertion definition, and the current terminal execution receipt. None of these identities SHALL substitute for another.

#### Scenario: Parent suite passed but leaf receipt is absent
- **WHEN** a parent suite reports pass but a required behavior coverage row lacks its exact leaf result or declared bounded delegation
- **THEN** the row SHALL remain incomplete for release confidence


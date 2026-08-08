## ADDED Requirements

### Requirement: Coverage remains inside one exact behavior block
Every blueprint coverage edge SHALL consume a case, checker design, oracle, implementation surface, behavior contract, and coverage-contract owner belonging to the same exact behavior block. Coverage ownership SHALL come only from the exact owner declared by that coverage contract. Shared model ownership, test-node placement, suite membership, source-case lineage, or a passing owner-level test collection SHALL NOT authorize or reassign a coverage edge for a sibling block.

#### Scenario: Owner-level test is copied to every sibling
- **WHEN** one owner-level test or native checker is associated with several behavior blocks without block-local case and checker identities
- **THEN** Model-Test Alignment SHALL keep the affected sibling coverage incomplete
- **AND** it SHALL NOT copy the aggregate result into each behavior block

#### Scenario: Coverage cites a sibling case
- **WHEN** a coverage edge for behavior block A cites a case or checker declared for behavior block B
- **THEN** Model-Test Alignment SHALL reject the edge as a cross-block mismatch
- **AND** neither block SHALL receive coverage from that edge

#### Scenario: Block-local static design has not executed
- **WHEN** a behavior block has an exact case, checker design, oracle, and execution owner but no current terminal receipt
- **THEN** the block-local static design MAY remain complete
- **AND** its execution disposition SHALL remain `not_run`
- **AND** a parent, suite, or owner-level pass SHALL NOT change that disposition

#### Scenario: Planned cases share one model-level origin
- **WHEN** two sibling blocks derive planned cases from the same owner-level source case
- **THEN** each checker and coverage edge SHALL still bind its own exact block-local case identity
- **AND** the shared source lineage SHALL NOT be interpreted as permission to reuse one parameter-case or checker identity across the siblings

#### Scenario: Coverage owner is inferred from a test container
- **WHEN** a coverage edge names one contract owner but a test module, class, suite, parent model, or aggregate command is used to claim another owner
- **THEN** Model-Test Alignment SHALL reject the ownership mismatch
- **AND** only the coverage contract's exact current owner MAY own the edge and its execution evidence

#### Scenario: Parent execution is copied to sibling blocks
- **WHEN** a parent or aggregate checker has a current passing receipt but one or more child behavior coverage contracts lack their own exact terminal evidence
- **THEN** the parent execution SHALL remain evidence only for its declared coverage owner and subject
- **AND** every uncovered child execution SHALL remain `not_run`, incomplete, or blocked as appropriate

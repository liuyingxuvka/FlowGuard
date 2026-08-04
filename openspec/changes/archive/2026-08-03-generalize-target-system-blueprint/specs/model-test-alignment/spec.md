## ADDED Requirements

### Requirement: Blueprint coverage has referential integrity
Every blueprint coverage edge SHALL resolve to a current behavior block, implementation surface, owner-declared concrete case, accepted case-and-dimension checker design, its current test-node or native-check owner, oracle identity, semantic rule, and exactly one covered dimension. The alignment review SHALL reject generated, missing, cross-owner, reused, stale, or mismatched references.

#### Scenario: Assertion belongs to another test node
- **WHEN** a coverage edge cites an oracle member whose owning test node differs from the edge's test node
- **THEN** alignment SHALL report the exact cross-test mismatch
- **AND** the edge SHALL NOT satisfy blueprint coverage

#### Scenario: Oracle does not cover a claimed dimension
- **WHEN** a coverage edge claims a behavior dimension absent from the cited oracle contract
- **THEN** alignment SHALL keep that dimension uncovered

### Requirement: Delegated oracle helpers are explicit
A delegated assertion helper SHALL count as an oracle member only when it is explicitly declared, its source identity is current, its call path terminates at current assertion or native-check members, and cycles or unresolved calls are absent.

#### Scenario: Test calls an unregistered assert-like helper
- **WHEN** a test invokes a helper whose name suggests an assertion but no current declaration and terminal oracle path exist
- **THEN** the helper SHALL remain supporting evidence only

### Requirement: Coverage design and execution are separate objects
The model-test alignment result SHALL preserve a formal static-design edge independently from its execution evidence. An owner-declared and accepted checker design assigned to a current test/native owner MAY be `not_run`; a generated, unaccepted, or ownerless checker SHALL remain a design gap rather than a formal edge.

#### Scenario: Planned test has no implementation member
- **WHEN** a case and expected oracle are proposed but no accepted checker design and current test/native owner exist
- **THEN** alignment SHALL report a planned checker gap
- **AND** it SHALL NOT serialize a passing or complete formal coverage edge

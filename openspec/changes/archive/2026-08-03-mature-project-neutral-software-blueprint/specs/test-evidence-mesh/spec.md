## ADDED Requirements

### Requirement: Project test inventory preserves exact executable evidence identities
TestMesh SHALL consume a project test inventory that distinguishes test source files, executable test nodes, assertion identities and quality, and static freshness. When execution is requested, TestMesh SHALL additionally preserve collection or selection identity, environment and toolchain fingerprints, execution receipts, and execution freshness. Every required test member SHALL have one explicit owner and terminal static disposition; execution status remains separate and may be `not_run`.

#### Scenario: One test file contains several executable tests
- **WHEN** test discovery finds multiple executable nodes in one source file
- **THEN** the inventory assigns each node a stable identity and preserves its source relationship
- **AND** file presence alone does not prove execution of every node

#### Scenario: A test executes without a meaningful assertion
- **WHEN** an executable test node runs successfully but its assertion audit finds no oracle-bearing assertion for the claimed obligation
- **THEN** TestMesh reports the execution separately from assertion quality
- **AND** the node cannot close that obligation's evidence row

#### Scenario: A receipt targets a stale source or collection
- **WHEN** a passing receipt names a different test source, executable-node set, collection identity, toolchain, or subject fingerprint
- **THEN** the receipt is stale for the current project test inventory
- **AND** it is not reused as current evidence

### Requirement: Broad parent results never manufacture missing child coverage
A broad suite result SHALL provide aggregate parent evidence only. It SHALL NOT create child test-node identities, assertion evidence, obligation bindings, or passing dispositions that are absent from the independently derived project test inventory and required child mesh.

#### Scenario: Parent suite passes with an orphan obligation
- **WHEN** the broad parent suite passes while one required obligation has no owned child test node
- **THEN** static model-code-test closure remains blocked for deep blueprint scope
- **AND** the orphan obligation and missing child owner remain explicit

#### Scenario: Ordinary work changes one bounded neighborhood
- **WHEN** a task changes only a fingerprinted affected blueprint neighborhood
- **THEN** TestMesh selects the exact affected test children and their required ancestors
- **AND** it does not require unrelated test partitions merely because a whole-software blueprint exists

#### Scenario: Background execution is still running
- **WHEN** a background test shard has only progress, logs, or a live process
- **THEN** TestMesh reports liveness without a terminal result
- **AND** no blueprint evidence row becomes current until the exact terminal receipt is verified

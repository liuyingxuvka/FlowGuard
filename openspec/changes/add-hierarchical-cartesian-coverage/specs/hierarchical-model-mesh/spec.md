## ADDED Requirements

### Requirement: ModelMesh requires all in-scope coverage receipts
Hierarchical ModelMesh SHALL require every in-scope model in a parent/child
model tree to provide a current model-scoped Cartesian coverage receipt before
broad parent or root confidence can be claimed.

#### Scenario: Missing child coverage receipt blocks parent confidence
- **WHEN** a parent mesh declares an in-scope child model
- **AND** no current coverage receipt exists for that child model
- **THEN** ModelMesh reports a missing coverage receipt finding
- **AND** parent confidence remains blocked or scoped

#### Scenario: All child receipts are current and consumed
- **WHEN** every in-scope child model has a current passing coverage receipt
- **AND** the parent receipt or parent interface plan consumes those child
  receipt ids
- **THEN** ModelMesh may treat the child coverage layer as closed for the
  parent boundary

### Requirement: Child-local green is not parent coverage
Hierarchical ModelMesh SHALL reject broad parent confidence when a child model
coverage receipt is current but the parent model did not consume it.

#### Scenario: Parent omits current child receipt
- **WHEN** a child coverage receipt is passing
- **AND** the parent coverage receipt does not list that child receipt id
- **THEN** ModelMesh reports unconsumed child coverage
- **AND** the parent cannot claim full all-model coverage

### Requirement: Cross-model misses backpropagate into model coverage
Hierarchical ModelMesh SHALL keep cross-model combination misses visible until
the affected child receipts and parent interface receipt are refreshed.

#### Scenario: Cross-model miss changes child and parent boundaries
- **WHEN** a model miss affects a child model axis and a parent consumption axis
- **THEN** ModelMesh requires refreshed child coverage and parent interface
  coverage before closing the parent mesh

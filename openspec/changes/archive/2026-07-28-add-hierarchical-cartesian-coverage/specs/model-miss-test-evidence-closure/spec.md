## ADDED Requirements

### Requirement: Combination misses promote interaction groups
Model-miss closure SHALL promote observed combination-type misses into
ContractExhaustionMesh interaction groups and generated combination case ids
before broad repair confidence can be restored.

#### Scenario: Point fix omits interaction group
- **WHEN** an observed miss depends on more than one model axis or on a child
  axis plus a parent consumption axis
- **AND** the repair adds only the observed regression test
- **THEN** model-miss closure reports missing interaction-group coverage

#### Scenario: Combination miss feeds bug family gate
- **WHEN** a recurring or high-risk miss is promoted to a defect-family gate
- **THEN** the gate names the affected model ids, root-cause dimensions,
  interaction group id, observed combination case id, and generated case ids

### Requirement: Bug families deepen models instead of replacing coverage
Bug-family and same-class closure SHALL provide seeds and family gates for
ContractExhaustionMesh instead of acting as independent canonical coverage.

#### Scenario: Same-class note lacks generated cases
- **WHEN** a bug-family claim names only an abstract same-class note
- **AND** no generated combination case ids or coverage receipt ids exist
- **THEN** closure remains incomplete for the affected model family

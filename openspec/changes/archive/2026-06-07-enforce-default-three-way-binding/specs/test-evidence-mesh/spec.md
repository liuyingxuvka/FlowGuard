## ADDED Requirements

### Requirement: TestMesh leaf evidence preserves three-way targets

TestMesh SHALL preserve model obligation and code contract targets for leaf
test evidence instead of treating child-suite completion as semantic coverage.

#### Scenario: Leaf cell evidence supports a parent gate
- **WHEN** a child test suite owns a transition or matrix cell
- **THEN** the parent confidence still depends on Model-Test Alignment proving
  that the cell binds the model obligation, code contract, and test evidence.

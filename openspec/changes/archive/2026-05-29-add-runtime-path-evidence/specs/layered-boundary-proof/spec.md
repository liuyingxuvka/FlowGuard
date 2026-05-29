## ADDED Requirements

### Requirement: Leaf boundary matrix can require runtime path evidence
Layered boundary proof SHALL allow leaf boundary matrix cells to bind expected
`Input x State -> Set(Output x State)` behavior to runtime node evidence ids.

#### Scenario: Leaf cell has runtime path evidence
- **WHEN** a leaf matrix cell declares required runtime node ids
- **AND** current passing runtime observations cover the cell's input case,
  state case, outputs, state writes, side effects, and error paths
- **THEN** layered boundary proof SHALL accept that runtime path evidence for
  the leaf cell

#### Scenario: Leaf cell lacks runtime path evidence
- **WHEN** a leaf matrix cell requires runtime node evidence
- **AND** a required node id has no current passing observation
- **THEN** layered boundary proof SHALL block parent confidence for that leaf
  cell

#### Scenario: Coarse leaf must split or scope
- **WHEN** a leaf model cannot produce finite runtime path evidence for every
  required input/state cell
- **THEN** layered boundary proof SHALL require a lower-level split or an
  explicit scoped exemption before parent confidence can be claimed

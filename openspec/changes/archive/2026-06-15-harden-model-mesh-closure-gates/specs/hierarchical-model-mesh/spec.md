## ADDED Requirements

### Requirement: Parent mesh green requires handoff closure when child outputs exist
Hierarchical ModelMesh SHALL block broad parent green confidence when a parent
mesh contains child model outputs or reattachment contracts but no closure
model that consumes those handoffs.

#### Scenario: Child output without closure model
- **WHEN** a parent mesh has a child model that declares emitted outputs
- **AND** the parent mesh has no closure model
- **THEN** the mesh review SHALL report a missing closure finding
- **AND** the mesh review SHALL NOT return `mesh_green_can_continue`

#### Scenario: Reattachment contract without closure model
- **WHEN** a parent mesh has a child reattachment contract
- **AND** the parent mesh has no closure model
- **THEN** the mesh review SHALL report a missing closure finding
- **AND** broad parent confidence SHALL remain blocked

#### Scenario: Partition-only mesh remains scoped
- **WHEN** a parent mesh only records partition ownership and has no child
  outputs or reattachment contracts
- **THEN** the mesh review MAY remain a partition confidence review
- **AND** it MUST NOT be described as whole-flow closure evidence

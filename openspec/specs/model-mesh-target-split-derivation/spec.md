# model-mesh-target-split-derivation Specification

## Purpose
TBD - created by archiving change add-mesh-target-split-derivation. Update Purpose after archive.
## Requirements
### Requirement: ModelMesh target split derivation
ModelMesh SHALL require a parent model boundary to include target split
derivation evidence before a parent/child model layout can support green mesh
confidence.

#### Scenario: Complete model target derivation
- **WHEN** a parent model boundary includes a FlowGuard source model id, target
  child model ids, covered partition item ids, and rationale for the split
- **THEN** ModelMesh may continue to ownership, overlap, evidence, and
  large-model review without a target-derivation blocker

#### Scenario: Missing model target derivation
- **WHEN** a parent model boundary contains child model or coverage partitions
  but no target split derivation evidence
- **THEN** ModelMesh reports a target-derivation blocker and does not return a
  green mesh decision

### Requirement: ModelMesh derivation coverage
ModelMesh SHALL reject target split derivations that do not cover the parent
partition items being used for the mesh decision.

#### Scenario: Incomplete model derivation coverage
- **WHEN** a target model split derivation omits one or more parent partition
  item ids from its coverage list
- **THEN** ModelMesh reports incomplete target derivation coverage

### Requirement: ModelMesh derivation source
ModelMesh SHALL require target split derivation evidence to identify the
FlowGuard model or model-of-models used to derive the target child model layout.

#### Scenario: Derivation missing source model
- **WHEN** a target model split derivation does not name a source FlowGuard
  model
- **THEN** ModelMesh reports an invalid target derivation

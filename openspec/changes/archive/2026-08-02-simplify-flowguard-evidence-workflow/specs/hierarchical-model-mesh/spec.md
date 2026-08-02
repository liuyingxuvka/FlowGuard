## ADDED Requirements

### Requirement: ModelMesh activation follows affected topology
ModelMesh SHALL activate for affected related models, parent/child changes, stale child evidence, oversized model partitioning, cross-model refinement, or whole-flow claims. The mere presence of three or more unrelated models in a repository SHALL NOT require mesh execution.

#### Scenario: Repository contains many unrelated models
- **WHEN** a task affects one bounded model with no dependent topology and no stale child evidence
- **THEN** ModelMesh is recorded as not triggered with that reason

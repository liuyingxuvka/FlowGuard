## ADDED Requirements

### Requirement: Existing skills distinguish observed, target, and experiment
The installed FlowGuard entry and affected satellite skills SHALL begin
non-trivial modeled-system work by identifying the observed source revision and
snapshot. They SHALL keep target and experimental snapshots candidate-only
until an evidence-backed observed snapshot is activated.

#### Scenario: AI proposes a model optimization
- **WHEN** an AI creates or changes one or more models before implementation
- **THEN** its output identifies the observed snapshot, candidate snapshot, affected closure, unresolved gaps, and bounded claim without describing the candidate as current

### Requirement: Skills use one revision-set lifecycle
The installed FlowGuard skills SHALL route single- and multi-model replacement
through the same revision-set lifecycle and SHALL NOT introduce another
promotion, rollback, or current-model authority.

#### Scenario: Several skills participate in one change
- **WHEN** ModelMesh, Behavior Commitment Ledger, FieldLifecycleMesh, Model-Test Alignment, TestMesh, and DevelopmentProcessFlow all contribute
- **THEN** each retains its existing owner role while one revision set and one observed-head pointer join their evidence

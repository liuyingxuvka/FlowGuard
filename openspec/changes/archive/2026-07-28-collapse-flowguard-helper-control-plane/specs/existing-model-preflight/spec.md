## ADDED Requirements

### Requirement: ExistingModelPreflight consumes angle and similarity helpers
ExistingModelPreflight SHALL consume model-angle deliberation rows and
model-similarity relations as structured evidence before it decides reuse,
extension, child-model creation, shared-kernel extraction, ArchitectureReduction
handoff, or separate-boundary creation.

#### Scenario: Model angle is required
- **WHEN** the current model may be too narrow for the task
- **THEN** ExistingModelPreflight MUST include angle rows or report a
  model-angle gap
- **AND** the angle helper MUST NOT be selected as a separate public first stop

#### Scenario: Model similarity is required
- **WHEN** the task resembles another model, workflow, sibling test, shared
  kernel, adapter, or business path
- **THEN** ExistingModelPreflight MUST include similarity relation evidence or
  report a similarity-evidence gap
- **AND** the similarity helper MUST NOT be selected as a separate public first
  stop

### Requirement: Preflight output names downstream owner
ExistingModelPreflight SHALL name the downstream public owner route that must
act on consumed helper evidence.

#### Scenario: Duplicate boundary found
- **WHEN** similarity or ownership evidence indicates duplicate responsibility
- **THEN** ExistingModelPreflight MUST route the decision to
  ArchitectureReduction, StructureMesh, ModelMesh, Model-Test Alignment, or
  another public owner route instead of creating a parallel helper route

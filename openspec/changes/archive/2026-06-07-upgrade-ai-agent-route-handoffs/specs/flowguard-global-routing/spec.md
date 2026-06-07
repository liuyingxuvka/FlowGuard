## ADDED Requirements

### Requirement: Global routing preserves existing routes while adding handoff continuation
Global FlowGuard routing SHALL preserve the existing direct satellite route
map and SHALL treat SummaryReport-to-MaintenanceScan-to-specialist output as a
continuation inside the existing route system, not a new parent route.

#### Scenario: Existing route remains owner
- **WHEN** a structured handoff recommends Model-Test Alignment,
  DevelopmentProcessFlow, ModelMesh, TestMesh, StructureMesh, Model
  Maturation, or AgentWorkflowRehearsal
- **THEN** the recommended existing route SHALL remain the owner of validation
  evidence and claim promotion

#### Scenario: Handoff is not a session runner
- **WHEN** the AI hot path describes the handoff sequence
- **THEN** it SHALL NOT introduce a new top-level session runner or require
  every task to pass through a parallel workflow

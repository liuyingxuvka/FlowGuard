## ADDED Requirements

### Requirement: Workflow step contracts can map to runtime nodes
Workflow step contracts SHALL allow completed step metadata to declare runtime
node ids so conformance and runtime path evidence can compare expected step
receipts with observed real-code path nodes.

#### Scenario: Step completion maps to runtime node
- **WHEN** a workflow step contract declares a runtime node id for a completion
  label
- **AND** a replay or runtime observation records the same node id
- **THEN** FlowGuard SHALL be able to match the completed step to the observed
  runtime path node

#### Scenario: Step runtime node is missing
- **WHEN** a workflow step contract requires a runtime node id for a completed
  step
- **AND** no runtime observation records that node id
- **THEN** the runtime path evidence review SHALL report the step-node gap

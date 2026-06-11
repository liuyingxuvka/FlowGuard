## ADDED Requirements

### Requirement: Payload guidance rejects standalone fake package paths
FlowGuard Codex satellite skill guidance SHALL describe synthetic payload cases
as test inputs for real file, artifact, or AI work-package surfaces. It SHALL
NOT teach agents to create or validate standalone fake work-package paths as a
completion target.

#### Scenario: Payload route guidance is read
- **WHEN** an agent reads Model-Test Alignment, TestMesh, DevelopmentProcessFlow,
  PlanDetailing, AgentWorkflowRehearsal, or the model-first kernel guidance
- **THEN** the guidance MUST say payload cases exercise the real payload surface
- **AND** it MUST require current evidence refs, proof artifacts, runtime path
  evidence, or owner-code-contract execution binding before broad confidence

#### Scenario: Misleading fake package wording is absent
- **WHEN** repository or installed FlowGuard skill prompts are inspected
- **THEN** they MUST NOT describe `fake file/work-package packs` as the target
  to validate

## ADDED Requirements

### Requirement: FlowGuard-managed projects use maintenance scan before broad claims
Global FlowGuard routing SHALL present the maintenance scan as the thin default entry for FlowGuard-managed project work where changed artifacts may require model/code/test/structure upkeep.

#### Scenario: Non-trivial project work enters maintenance scan
- **WHEN** an agent works in a project with FlowGuard adoption records
- **AND** the task changes behavior, models, tests, structure, workflow guidance, release assets, or evidence-bearing artifacts
- **THEN** global routing MUST direct the agent to run or construct a maintenance scan before broad completion confidence
- **AND** the scan MUST route any resulting required actions to the existing specialist FlowGuard routes

#### Scenario: Tiny work can skip scan with reason
- **WHEN** the task is a tiny copy edit, formatting-only change, direct command answer, or read-only explanation
- **THEN** global routing MAY skip the maintenance scan with a concrete reason

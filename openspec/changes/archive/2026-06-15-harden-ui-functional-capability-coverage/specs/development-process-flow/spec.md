## ADDED Requirements

### Requirement: Capability coverage artifacts stale UI completion evidence
DevelopmentProcessFlow SHALL treat UI functional capability inventories, output contracts, capability-task mappings, implementation bindings, and capability coverage reports as freshness-sensitive UI lifecycle artifacts.

#### Scenario: Capability inventory changes after UI evidence
- **WHEN** a UI capability inventory, output contract, or implementation binding changes after human-operability or implementation validation evidence was produced
- **THEN** DevelopmentProcessFlow marks the affected UI evidence stale and requires rerunning the relevant UI Flow Structure gates

#### Scenario: UI task complete lacks capability evidence type
- **WHEN** a UI task is marked complete for functional implementation work
- **AND** no current capability coverage evidence kind or scoped-out boundary is recorded
- **THEN** DevelopmentProcessFlow blocks done or release confidence for that task

## MODIFIED Requirements

### Requirement: DevelopmentProcessFlow triggers for staged work with validation
FlowGuard SHALL present DevelopmentProcessFlow as the route for any
non-trivial staged development or modification task where step ordering,
touched artifacts, validation evidence, evidence freshness, peer writes, or
minimum revalidation affects whether the agent can safely continue or claim
done.

#### Scenario: Staged implementation trigger
- **WHEN** an agent is asked to complete a non-trivial task with staged actions
  such as plan, edit, test, fix, and verify
- **THEN** the Codex-facing DevelopmentProcessFlow guidance says to use
  `flowguard-development-process-flow` during planning

#### Scenario: Not reserved for release readiness
- **WHEN** a task is not yet at release, archive, publish, or final readiness
  but has multiple meaningful development stages and validation
- **THEN** the DevelopmentProcessFlow guidance still treats the route as
  applicable

#### Scenario: Trivial work can skip
- **WHEN** the task is a single-step typo, formatting-only edit, or pure
  explanation with no meaningful validation or artifact freshness risk
- **THEN** the guidance permits skipping DevelopmentProcessFlow with a clear
  reason

### Requirement: DevelopmentProcessFlow remains one sibling route
FlowGuard SHALL keep DevelopmentProcessFlow as one sibling route and SHALL NOT
split the Codex skill into separate lightweight and heavyweight modes for this
trigger clarification.

#### Scenario: Single route wording
- **WHEN** the satellite skill and route documentation are read
- **THEN** they describe direct use of `flowguard-development-process-flow`
  rather than introducing separate named modes

#### Scenario: Sibling evidence boundary preserved
- **WHEN** DevelopmentProcessFlow references evidence from ModelMesh, TestMesh,
  StructureMesh, Model-Test Alignment, LongCheck, or Conformance Adoption
- **THEN** the guidance continues to say it may use sibling evidence ids and
  freshness metadata but MUST NOT inspect, replace, or supervise sibling route
  internals

## MODIFIED Requirements

### Requirement: model-first-function-flow routes staged development to DevelopmentProcessFlow
The `model-first-function-flow` Skill SHALL route non-trivial staged
development or modification tasks with validation to
`development_process_flow`, in addition to final done, archive, publish, and
release-readiness evidence checks.

#### Scenario: Kernel route map includes staged development
- **WHEN** the Skill Kernel route map is read
- **THEN** the `development_process_flow` trigger includes non-trivial staged
  development or modification, step ordering, touched artifacts, validation
  evidence, evidence freshness, peer writes, minimum revalidation, and V-style
  process confidence

#### Scenario: Kernel does not wait for final readiness
- **WHEN** the task has multiple meaningful development stages and validation
  but is not yet a release/archive/publish claim
- **THEN** the Skill Kernel guidance still routes the work to
  `development_process_flow`

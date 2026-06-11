## ADDED Requirements

### Requirement: Plans bind payload cases to real surfaces
PlanDetail SHALL require non-trivial plans that import, export, save, load,
generate, or consume files/work packages to name the real payload surface,
synthetic cases, expected proof kind, freshness rule, and final claim boundary.

#### Scenario: Plan includes payload-bearing work
- **WHEN** a plan touches a file, generated artifact, saved project, archive, or
  AI work package
- **THEN** the plan detail MUST identify the real payload surface and the
  evidence refs or proof artifacts expected to prove it
- **AND** it MUST NOT treat synthetic case generation alone as completion
  evidence

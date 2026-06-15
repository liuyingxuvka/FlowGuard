## ADDED Requirements

### Requirement: Plans expose UI and payload validation surfaces
PlanDetail SHALL require non-trivial plans to expose UI action, artifact
payload, AI work-package, manual-review, and final-evidence surfaces when those
boundaries can affect the claim.

#### Scenario: Plan includes import/export work
- **WHEN** a plan touches file import, file export, generated artifacts, or AI
  work packages
- **THEN** the plan detail MUST name payload cases, expected evidence kinds,
  failure/rework branches, freshness rules, and final claim boundaries

#### Scenario: Plan includes running UI completion
- **WHEN** a plan claims implemented or runnable UI behavior
- **THEN** the plan detail MUST name the click-through evidence boundary and
  any manual-check or blindspot branches

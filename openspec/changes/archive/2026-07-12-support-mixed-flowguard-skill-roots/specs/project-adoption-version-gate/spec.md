## ADDED Requirements

### Requirement: Project adoption consumes strict mixed-root suite evidence
Project audit and project upgrade SHALL accept an ownership-backed mixed skill
root when the canonical FlowGuard suite is complete, and SHALL continue to
block when canonical membership or ownership evidence is unresolved.

#### Scenario: Project audit sees a valid mixed root
- **WHEN** a target project contains a passing canonical seventeen-member
  FlowGuard suite with valid distribution ownership evidence
- **AND** unrelated non-FlowGuard skills are co-located in the skill root
- **THEN** project audit does not report
  `suite_inventory_unresolved` for those unrelated skills

#### Scenario: Project upgrade sees a valid mixed root
- **WHEN** explicit project upgrade runs against a valid ownership-backed mixed
  root
- **AND** all other upgrade gates pass
- **THEN** the upgrade may write the current project records
- **AND** it preserves the unrelated skill directories

#### Scenario: Mixed root contains a missing or fake FlowGuard member
- **WHEN** a declared FlowGuard member is missing or an undeclared
  FlowGuard-reserved member is present
- **THEN** project upgrade remains blocked by
  `suite_inventory_unresolved`
- **AND** no project record is written merely because unrelated skills were
  classified separately

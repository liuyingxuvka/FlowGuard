## MODIFIED Requirements

### Requirement: Routine and release lifecycle scopes are distinct
FlowGuard SHALL distinguish routine lifecycle confidence from release
confidence so release-required evidence can be deferred visibly during routine
work but must be current for release claims, including local install and
shadow-workspace verification when the release process touches those artifacts.

#### Scenario: Routine scope defers release evidence
- **WHEN** a routine claim has all routine evidence current and release-required
  evidence pending
- **THEN** DevelopmentProcessFlow may allow routine confidence while reporting
  the release obligation as deferred

#### Scenario: Release scope requires release evidence
- **WHEN** a release claim lacks current release-required evidence
- **THEN** DevelopmentProcessFlow blocks release confidence

#### Scenario: Local release sync evidence is current
- **WHEN** a release claim includes a refreshed editable install and local
  shadow workspace sync
- **THEN** DevelopmentProcessFlow SHALL require final install and shadow import
  evidence for the released version before release confidence is claimed

## ADDED Requirements

### Requirement: UI task rows carry evidence type and status
Plan Detailing Compiler SHALL require UI-related task rows to name completion
evidence type, evidence status, and evidence reference or scoped boundary before
the task can support a done, release, or runnable-UI claim.

#### Scenario: Checked task has no evidence type
- **WHEN** a UI task is marked complete but lacks evidence type and evidence
  status
- **THEN** plan-detail review reports the row as unsupported for UI completion

#### Scenario: Artifact complete is not release complete
- **WHEN** OpenSpec artifacts are complete but UI implementation evidence,
  real-surface inventory, functional-chain evidence, or native/manual signoff
  remains missing
- **THEN** the plan remains artifact-complete only and cannot support release
  confidence

#### Scenario: Evidence type is explicit
- **WHEN** a UI task uses model coverage, static test, runtime click,
  browser DOM/geometry, desktop-shell manual observation, or native-dialog
  blindspot evidence
- **THEN** the task row records that evidence type and whether it is current,
  passing, scoped, stale, planned, or missing

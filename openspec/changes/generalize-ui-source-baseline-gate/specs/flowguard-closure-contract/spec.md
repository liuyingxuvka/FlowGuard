## ADDED Requirements

### Requirement: Final source-based UI claims require source-baseline closure
FlowGuard ClosureContract SHALL require current source-baseline, target mapping, approved difference, and observed-source alignment evidence before final claims say a source-based or mixed UI scope is complete, release-ready, or faithful to its source authority.

#### Scenario: Source-based UI closure lacks source alignment
- **WHEN** a final UI claim covers source-based UI scope
- **AND** no current source-baseline alignment evidence is supplied
- **THEN** ClosureContract blocks broad UI release confidence or scopes the claim below source-based completeness

#### Scenario: Greenfield UI closure skips source-baseline gate
- **WHEN** a final UI claim is greenfield-only
- **THEN** ClosureContract does not require source-baseline alignment
- **AND** it still requires the applicable UI task, implementation, process, and risk evidence

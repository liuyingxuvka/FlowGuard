## ADDED Requirements

### Requirement: Implemented UI action evidence covers reachable controls
UI Flow Structure SHALL require each reachable enabled actionable control and
modeled event in an implemented/runnable UI claim to have real run evidence,
pure-UI classification, or a scoped implementation blindspot.

#### Scenario: Reachable button is unverified
- **WHEN** a running UI exposes an enabled actionable control or modeled event
- **AND** the implementation validation has no browser, desktop, or manual step
  evidence for it
- **AND** it has no pure-UI classification or scoped blindspot
- **THEN** the implementation validation MUST report a blocker

#### Scenario: Native dialog needs manual fallback
- **WHEN** a reachable UI action depends on a native file picker, download,
  clipboard, desktop shell, system permission, or third-party surface that the
  automation cannot inspect
- **THEN** the action MUST have manual step evidence or a scoped blindspot with
  owner, reason, and validation boundary

### Requirement: UI run evidence records step-level freshness
UI implementation validation SHALL keep run method, step event, control,
source state, target state, result, evidence reference, and model or
implementation revision visible.

#### Scenario: Stale UI click-through evidence
- **WHEN** UI run evidence references an older model or implementation revision
- **THEN** the implemented UI claim MUST remain blocked or scoped until the run
  is refreshed

## ADDED Requirements

### Requirement: Payload and UI evidence freshness
DevelopmentProcessFlow SHALL treat UI action maps, payload schemas, import and
export behavior, AI work-package structure, validation prompts, installed
skills, and verifier artifacts as freshness-sensitive process artifacts.

#### Scenario: Payload schema changes after evidence
- **WHEN** payload schema, work-package structure, import/export code, or
  output formatting changes after payload validation evidence is produced
- **THEN** DevelopmentProcessFlow MUST mark that evidence stale and recommend
  rerunning the payload validation requirement

#### Scenario: UI action map changes after click-through evidence
- **WHEN** reachable UI controls, events, state transitions, or handlers change
  after browser, desktop, or manual click-through evidence is produced
- **THEN** DevelopmentProcessFlow MUST mark the click-through evidence stale

### Requirement: Installed prompt and package sync are process evidence
DevelopmentProcessFlow SHALL track repository skill guidance, installed Codex
skills, editable install state, source mirror sync, and package version as
process artifacts for done or release confidence.

#### Scenario: Repository prompt changed but installed prompt was not synced
- **WHEN** repository-managed FlowGuard skill guidance changes
- **AND** installed Codex skill content is not refreshed or verified
- **THEN** DevelopmentProcessFlow MUST report local installed behavior as
  unsynced or scoped

#### Scenario: Editable install points at current source
- **WHEN** local installed package behavior is claimed
- **THEN** evidence MUST show the imported package path, package version, and
  expected helper symbols from the current source

# guard-closure-contract Specification

## Purpose
This capability defines FlowGuard's Guard Closure Contract behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Child Guard closure reports are machine-readable
FlowGuard SHALL require child Guard closure reports to expose owner, artifact kind, closure status, findings, missing inputs, stale evidence, skipped checks, next actions, safe claim, and unsafe claim boundary before using them for broad confidence.

#### Scenario: Partial child report blocks broad confidence
- **WHEN** a child Guard report has `closure_status` equal to `partial`, `blocked`, or `downgraded`
- **THEN** FlowGuard records it as a maintenance obligation instead of treating it as passed evidence

### Requirement: Passed reports cannot hide unresolved evidence
FlowGuard SHALL reject a `passed` child Guard report that still contains hard findings, missing inputs, stale evidence, or skipped checks.

#### Scenario: Passed report contains skipped checks
- **WHEN** a child Guard report says `passed` while `skipped_checks` is not empty
- **THEN** the closure contract checker returns a failing report


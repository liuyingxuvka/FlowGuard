## ADDED Requirements

### Requirement: Model-understanding status command is read-only and composable
The command surface SHALL expose a model-understanding status command that consumes exact artifact references and returns structured understanding sufficiency, FlowGuard implementation admission, user choice, identity mismatches, and not-run gaps. The command SHALL NOT execute validation owners, resume a run, publish evidence, modify files, or change authority.

#### Scenario: Required artifact reference is absent
- **WHEN** the command is invoked without a required current artifact reference
- **THEN** it returns an explicit not-run or unresolved gap and performs no write

#### Scenario: Complete matching artifact set is supplied
- **WHEN** all supplied artifacts have matching current identities and terminal evidence
- **THEN** the command deterministically reports the licensed status with a successful read-only exit

## MODIFIED Requirements

### Requirement: FlowGuard exposes a thin default AI entry path

FlowGuard guidance SHALL present the smallest useful workflow before advanced
routes or helper inventories. The default AI entry path SHALL also tell agents
that old FlowGuard artifacts, models, tests, and guidance should be upgraded or
blocked at the boundary, not preserved as long-lived runtime compatibility.

#### Scenario: Agent starts ordinary risky work

- **GIVEN** a task where order, state, side effects, or evidence freshness may
  matter
- **WHEN** an agent reads the kernel, AGENTS snippet, README, or API surface
  guidance
- **THEN** it sees a compact default path before the advanced route map:
  identify the risky boundary, model `Input x State -> Set(Output x State)`,
  add one invariant or scenario, run the check, inspect counterexamples, and
  escalate only when a named risk requires it

#### Scenario: Tiny or read-only work stays lightweight

- **GIVEN** a task that is a trivial copy edit, formatting-only change, direct
  command answer, or read-only explanation with no behavior/state/process risk
- **WHEN** an agent evaluates FlowGuard applicability
- **THEN** the guidance allows `skip_with_reason` without creating a model or
  loading advanced satellites

#### Scenario: Agent enters older FlowGuard repository

- **GIVEN** a repository has a FlowGuard adoption record older than the
  installed FlowGuard package
- **WHEN** an agent follows the default project-entry guidance
- **THEN** the guidance routes the agent to project upgrade and artifact/model
  upgrade scanning
- **AND** it does not instruct the agent to keep old fields, aliases, or
  wrappers for backward compatibility

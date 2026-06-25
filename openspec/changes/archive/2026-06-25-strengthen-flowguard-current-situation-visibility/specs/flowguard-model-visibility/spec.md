## MODIFIED Requirements

### Requirement: Non-trivial FlowGuard work defaults to user-visible model snapshots
FlowGuard guidance SHALL direct agents to show a short user-facing current
situation explanation before or with a Mermaid model snapshot during
non-trivial FlowGuard work once the route or model shape is stable enough to
explain. The explanation SHALL name what is being checked, why it matters, the
current evidence or gaps, and the next step.

#### Scenario: UI modeling shows the model during work
- **WHEN** FlowGuard is modeling a UI journey, visible controls, state
  transitions, implementation evidence, or claim boundary
- **THEN** the guidance defaults to a user-facing current situation explanation
  and Mermaid snapshot showing the launch/entry states, key branches, evidence
  status, and known gaps

#### Scenario: Model miss review shows the repair path
- **WHEN** a prior FlowGuard pass is contradicted by runtime, test, replay, log,
  manual, or production evidence
- **THEN** the guidance defaults to a user-facing current situation explanation
  and snapshot showing prior claim, observed failure, miss class, model repair,
  generalized bad case, and current validation boundary

#### Scenario: Process or release work shows evidence freshness
- **WHEN** FlowGuard is used for staged development, synchronization, release,
  archive, publish, or validation-freshness confidence
- **THEN** the guidance defaults to a user-facing current situation explanation
  and snapshot showing artifact versions, actions that stale evidence,
  validation ids, revalidation gates, and unsupported claims

#### Scenario: Existing model preflight shows reuse decision
- **WHEN** FlowGuard checks whether existing models, prompt rules, skills, or
  process records already own the requested work
- **THEN** the guidance defaults to a user-facing current situation explanation
  showing the searched boundary, relevant model hits or gaps, reuse decision,
  duplicate-boundary risk, and downstream route

### Requirement: Material model changes update the visible snapshot
FlowGuard guidance SHALL direct agents to update the user-facing current
situation explanation and snapshot when route choice, model scope, branch
coverage, evidence status, or claim boundaries materially change during the
work.

#### Scenario: New branch or gap is discovered
- **WHEN** a counterexample, missing branch, stale evidence, or new route changes
  what FlowGuard is checking
- **THEN** the user-visible current situation explanation and snapshot are
  updated or the final report clearly explains the changed model boundary

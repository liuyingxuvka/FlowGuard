# flowguard-model-visibility Specification

## Purpose
This capability defines FlowGuard's Flowguard Model Visibility behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
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

### Requirement: Trivial work may skip diagrams
FlowGuard guidance SHALL NOT force diagrams for tiny, obvious, single-step,
mechanical, formatting-only, direct-command, or user-suppressed tasks.

#### Scenario: Tiny copy edit remains concise
- **WHEN** the work is a trivial copy edit or one-step direct command with no
  meaningful model interpretation
- **THEN** the agent may skip a diagram with normal concise reporting

### Requirement: Diagrams explain but do not validate
FlowGuard guidance SHALL state that diagrams explain the model and do not count
as validation evidence.

#### Scenario: Validation still comes from executable evidence
- **WHEN** a diagram is shown to the user
- **THEN** the agent still needs executable FlowGuard checks, tests, replay,
  browser/manual evidence, or explicit skipped/not-run boundaries before making
  completion claims

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
### Compact direct-current boundary (2026-09-22)

The compact closeout keeps one FlowGuard skill and exactly three public operations: `read`, `change`, and `release`. A selected subject loads only its concrete protocol and explicitly named accepted model or evidence. Retired commands, profiles, satellite entrypoints, forwarding files, aliases, compatibility readers, migrations, and fallback routes are removed from the current surface; they are not interpreted or selected as a secondary success path.

#### Scenario: Missing or retired selection blocks

- **WHEN** a request has no unique current subject, names a retired entry, or omits a required accepted identity
- **THEN** FlowGuard reports a typed blocker with zero producer and zero write effects; it does not widen the scope or try another route.

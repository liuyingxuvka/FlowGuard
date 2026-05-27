# flowguard-ai-entry-simplification Specification

## Purpose
TBD - created by archiving change simplify-flowguard-ai-entry. Update Purpose after archive.
## Requirements
### Requirement: FlowGuard exposes a thin default AI entry path

FlowGuard guidance SHALL present the smallest useful workflow before advanced
routes or helper inventories.

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

### Requirement: Advanced FlowGuard routes are escalation paths

FlowGuard guidance SHALL keep mature satellite skills discoverable while
framing them as explicit escalation paths, not mandatory default reading for
every task.

#### Scenario: Advanced route is needed

- **GIVEN** a task clearly involving UI topology, test hierarchy, model/test
  alignment, model hierarchy, structure refactor, process/release freshness,
  architecture reduction, existing-model ownership, or model-miss repair
- **WHEN** an agent reaches the escalation section
- **THEN** the matching satellite skill remains named and searchable
- **AND** the route's trigger is described in concise terms

#### Scenario: Advanced route is not needed

- **GIVEN** an ordinary fit-for-risk FlowGuard model is enough
- **WHEN** an agent reads the default entry
- **THEN** helper APIs, proof ledgers, benchmark suites, and deep mesh routes
  are presented as optional escalation, not prerequisites

### Requirement: Public and internal surfaces remain separated

FlowGuard public guidance SHALL distinguish the ordinary product path from
internal maintenance and release-hardening machinery.

#### Scenario: User reads public product docs

- **GIVEN** a user wants to try FlowGuard on a project
- **WHEN** they read public-facing docs
- **THEN** the docs explain that ordinary use starts with the thin default path
- **AND** internal maintenance suites, benchmark/problem corpus runs, and deep
  release evidence are not presented as mandatory first steps

### Requirement: Satellite topology stays current

FlowGuard tests and docs SHALL prevent stale satellite-count wording from
surviving after route topology changes.

#### Scenario: Satellite count changes

- **GIVEN** the repository contains a set of `flowguard-*` satellite skill
  directories
- **WHEN** skill documentation tests run
- **THEN** they compare guidance text against the current repository topology
- **AND** stale fixed-count wording such as an obsolete "seven satellites"
  claim is reported before release confidence is claimed

### Requirement: Sync evidence covers local install, installed skills, shadow workspace, and git version

FlowGuard local release-quality synchronization SHALL verify all user-facing
local surfaces after guidance changes.

#### Scenario: AI entry simplification is finalized

- **GIVEN** docs, skills, tests, and OpenSpec artifacts are updated
- **WHEN** the change is finalized locally
- **THEN** validation includes OpenSpec checks, focused docs/skill tests,
  practical model or regression checks, editable install verification,
  installed skill sync verification, shadow workspace import verification, and
  a scoped local git commit/tag when validation passes
- **AND** unrelated peer-agent changes remain unstaged unless they are part of
  this change

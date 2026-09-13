## ADDED Requirements

### Requirement: Persistent prompt context is measured separately
Prompt review SHALL report the unique catalog, preselection, and admitted-core
source context as a persistent-context metric, with an explicit route budget
when configured. Triggered detail SHALL not be counted as ordinary persistent
context.

#### Scenario: High-cost detail is on demand
- **WHEN** a route has a large detail protocol that is needed only for a named
  contraction, retirement, release, or other explicit trigger
- **THEN** the detail SHALL be reported as triggered expansion
- **AND** the ordinary route SHALL remain within its persistent-context budget

### Requirement: Internal process modes have exact route edges
DevelopmentProcessFlow SHALL expose exact conditional reference edges for its
plan-detailing and agent-workflow internal modes.

#### Scenario: Rough plan needs detailing
- **WHEN** a rough or underspecified plan requires structured rows
- **THEN** the plan-detailing protocol SHALL be the named on-demand owner

#### Scenario: Multi-skill operation needs rehearsal
- **WHEN** a multi-skill, tool, plugin, or external-side-effect operation needs
  workflow rehearsal
- **THEN** the agent-workflow protocol SHALL be the named on-demand owner

### Requirement: Current self DNA can be exchanged
FlowGuard SHALL be able to materialize one current self portable-blueprint
bundle from the same current source/model/code/test evidence used by its
canonical self blueprint.

#### Scenario: Self bundle is exported
- **WHEN** the current self blueprint is canonically export-ready
- **THEN** one content-addressed portable bundle SHALL be written atomically
- **AND** the bundle SHALL preserve static, portable-integrity, and execution
  status as separate fields

#### Scenario: Self bundle is checked in isolation
- **WHEN** the exported self bundle is copied to an empty directory
- **THEN** the portable verifier SHALL validate it without loading source,
  providers, tests, fallback readers, or reconstruction logic

### Requirement: Aggregate test success does not forge leaf passes
Model-test alignment SHALL keep aggregate execution success separate from
leaf-level execution evidence.

#### Scenario: Leaf evidence is absent
- **WHEN** an aggregate owner passes but an individual behavior block has no
  current terminal execution receipt
- **THEN** the behavior block SHALL remain `not_run` or typed-gap
  **AND** the aggregate pass SHALL not be copied into that leaf

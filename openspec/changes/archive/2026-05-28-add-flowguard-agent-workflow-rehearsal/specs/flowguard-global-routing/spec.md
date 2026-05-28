## ADDED Requirements

### Requirement: Multi-skill workflow rehearsal routes directly
The global Codex FlowGuard guidance SHALL route non-trivial tasks that may
require multiple installed skills, uncertain skill selection, cross-skill
ordering, external side effects, staged validation, or non-trivial completion
evidence to `flowguard-agent-workflow-rehearsal` before execution.

#### Scenario: Complex multi-skill task rehearses first
- **WHEN** a task may involve several installed Codex skills, plugins, tools,
  or staged validation paths
- **THEN** the global guidance selects `flowguard-agent-workflow-rehearsal`
  before execution begins

#### Scenario: Fresh snapshot is part of routing
- **WHEN** `flowguard-agent-workflow-rehearsal` is selected
- **THEN** the guidance requires a fresh current-machine skill snapshot for
  that invocation
- **AND** it forbids treating cached skill lists as current evidence

#### Scenario: Tiny tasks can skip rehearsal
- **WHEN** the task is a trivial read-only answer, formatting-only edit, direct
  command answer, or obvious low-risk single-skill task
- **THEN** the guidance may skip `flowguard-agent-workflow-rehearsal` with a
  concrete reason

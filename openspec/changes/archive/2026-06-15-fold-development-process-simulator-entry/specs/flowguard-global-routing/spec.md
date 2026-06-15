## MODIFIED Requirements

### Requirement: Global routing prefers direct FlowGuard satellite skills
The global Codex FlowGuard guidance SHALL first check whether a direct
FlowGuard satellite skill clearly matches the task and SHALL prefer that direct
skill over `model-first-function-flow` when the match is clear. For
development-process simulation work, the clear direct skill SHALL be the
single front-door `flowguard-development-process-flow`, with internal modes for
plan detailing, agent workflow rehearsal, and execution freshness.

#### Scenario: Staged development routes directly
- **WHEN** a task is non-trivial staged development or modification with
  validation, such as plan, edit, test, fix, and verify
- **THEN** the global guidance routes to `flowguard-development-process-flow`
  instead of treating `model-first-function-flow` alone as sufficient
- **AND** the simulator selects `execution_freshness` when artifact versions,
  evidence freshness, install sync, release, archive, publish, or local git
  confidence matters

#### Scenario: Rough plan routes through development simulator
- **WHEN** a task asks to discuss, refine, or expand a rough non-trivial plan
- **THEN** the global guidance routes to `flowguard-development-process-flow`
  as the front-door simulator
- **AND** the simulator selects `plan_detailing` as the internal mode instead
  of auto-selecting `flowguard-plan-detailing-compiler` as a peer first entry

#### Scenario: Multi-skill workflow routes through development simulator
- **WHEN** a task may require multiple installed skills, plugins, tools,
  external side effects, staged validation paths, or cross-skill evidence
- **THEN** the global guidance routes to `flowguard-development-process-flow`
  as the front-door simulator
- **AND** the simulator selects `agent_workflow` as the internal mode instead
  of auto-selecting `flowguard-agent-workflow-rehearsal` as a peer first entry

#### Scenario: UI interaction routes directly
- **WHEN** UI controls, screens, menus, navigation, overlays, visible states,
  journey coverage, UI text hierarchy, or implementation click-through
  evidence are the main risk
- **THEN** the global guidance routes to `flowguard-ui-flow-structure`

#### Scenario: Model-test evidence routes directly
- **WHEN** model obligations, tests, code contracts, scenarios, invariants,
  hazards, or evidence coverage need direct comparison
- **THEN** the global guidance routes to `flowguard-model-test-alignment`

#### Scenario: Ambiguous routing uses kernel
- **WHEN** no direct satellite route clearly matches, several routes apply, or
  a core behavior/state model is needed before narrowing
- **THEN** the global guidance routes to `model-first-function-flow`

### Requirement: Multi-skill workflow rehearsal routes through the simulator
The global Codex FlowGuard guidance SHALL route non-trivial tasks that may
require multiple installed skills, uncertain skill selection, cross-skill
ordering, external side effects, staged validation, or non-trivial completion
evidence to `flowguard-development-process-flow` first, which SHALL select the
`agent_workflow` internal mode before execution.

#### Scenario: Complex multi-skill task rehearses first
- **WHEN** a task may involve several installed Codex skills, plugins, tools,
  or staged validation paths
- **THEN** the global guidance selects `flowguard-development-process-flow`
  before execution begins
- **AND** the simulator selects `agent_workflow` and delegates to
  AgentWorkflowRehearsal evidence

#### Scenario: Fresh snapshot is part of routing
- **WHEN** `agent_workflow` mode is selected
- **THEN** the guidance requires a fresh current-machine skill snapshot for
  that invocation
- **AND** it forbids treating cached skill lists as current evidence

#### Scenario: Tiny tasks can skip rehearsal
- **WHEN** the task is a trivial read-only answer, formatting-only edit, direct
  command answer, or obvious low-risk single-skill task
- **THEN** the guidance may skip `agent_workflow` mode with a concrete reason

### Requirement: Global routing recognizes rough-plan expansion
FlowGuard global routing SHALL route non-trivial rough-plan expansion, plan
completion, and "make this plan detailed" requests to
`flowguard-development-process-flow` first, which SHALL select the
`plan_detailing` internal mode and delegate detailed row validation to the
PlanDetailing compiler.

#### Scenario: Rough plan routes to simulator plan mode
- **WHEN** a user asks to turn a vague idea or short plan into a detailed
  FlowGuard process plan
- **THEN** global routing selects `flowguard-development-process-flow`
- **AND** the simulator selects `plan_detailing` and requires structured rows
  before downstream FlowGuard routes

#### Scenario: Route still avoids trivial work
- **WHEN** the task is a tiny copy edit, direct command answer, or
  formatting-only change
- **THEN** global routing may skip plan detailing with a reason

### Requirement: Global routing uses a compact canonical decision table
Global FlowGuard guidance SHALL present one compact routing decision table for
ordinary AI use and SHALL avoid repeating long helper inventories in the hot
path. The table SHALL present plan detailing, agent workflow rehearsal, and
development process freshness as modes under the single
`flowguard-development-process-flow` front door rather than as three competing
first-entry rows.

#### Scenario: Agent reads reusable AGENTS guidance
- **WHEN** an agent reads `docs/agents_snippet.md`
- **THEN** it first sees task-size triage, the FlowGuard routing decision,
  minimum valuable path, hard gates, and a compact route table before any
  reference protocol detail
- **AND** the route table shows development-process simulation as one entry
  with `plan_detailing`, `agent_workflow`, and `execution_freshness` modes

#### Scenario: Detailed route content is needed
- **WHEN** the selected route needs detailed protocol rules, helper API
  inventories, examples, or evidence ledgers
- **THEN** the guidance points to the matching skill reference or docs page
  instead of duplicating the full content in the AGENTS hot path

## MODIFIED Requirements

### Requirement: Plan detailing is exposed as a delegated development-process mode
FlowGuard SHALL include `flowguard-plan-detailing-compiler` as a discoverable
Codex skill for explicit requests and simulator delegation, while the ordinary
automatic rough-plan hot path SHALL enter `flowguard-development-process-flow`
first and select `plan_detailing` mode.

#### Scenario: Satellite remains discoverable
- **WHEN** the FlowGuard Codex skill topology is read
- **THEN** plan detailing appears as a delegated/internal development-process
  mode with a direct skill name available for explicit user requests

#### Scenario: Automatic route uses front door
- **WHEN** a non-trivial task generically asks to discuss, refine, or expand a
  plan
- **THEN** installed guidance selects `flowguard-development-process-flow`
  first
- **AND** it records `plan_detailing` as the selected internal mode

#### Scenario: Installed skill sync covers plan detailing
- **WHEN** the repository skill is updated
- **THEN** installed Codex skill synchronization checks include the
  plan-detailing delegated skill

### Requirement: Agent workflow rehearsal is exposed as a delegated development-process mode
The repository SHALL provide `flowguard-agent-workflow-rehearsal` as a
discoverable FlowGuard skill for explicit requests and simulator delegation,
while the ordinary automatic multi-skill workflow hot path SHALL enter
`flowguard-development-process-flow` first and select `agent_workflow` mode.

#### Scenario: Rehearsal satellite is listed as delegated
- **WHEN** a Codex agent reads the FlowGuard skill topology or reusable AGENTS
  guidance
- **THEN** `flowguard-agent-workflow-rehearsal` appears as a delegated/internal
  development-process mode rather than as a competing ordinary first entry

#### Scenario: Rehearsal mode preserves hard gates
- **WHEN** `agent_workflow` mode is selected through the simulator
- **THEN** the delegated rehearsal still requires the real FlowGuard package
  for FlowGuard claims
- **AND** it requires a fresh current-machine skill inventory before rehearsal

### Requirement: Satellite skills remain discoverable route shells
FlowGuard SHALL preserve direct satellite skills as concise route shells with
standalone hard gates, trigger/skip criteria, minimum workflow, snapshot
guidance, non-goals, and reference handoff. Delegated development-process
satellites SHALL additionally state that automatic generic routing should enter
`flowguard-development-process-flow` first.

#### Scenario: Satellite skill count is not reduced by structure cleanup
- **WHEN** implementation surfaces are simplified
- **THEN** existing satellite skill names remain discoverable and their
  `SKILL.md` files remain within prompt budgets

#### Scenario: Hard gates remain visible
- **WHEN** a satellite skill is read without deep reference files
- **THEN** real-package verification, project adoption records, fake-framework
  rejection, and route-specific evidence honesty remain visible

#### Scenario: Delegated satellites name their front door
- **WHEN** the PlanDetailing or AgentWorkflowRehearsal `SKILL.md` is read
- **THEN** it says generic automatic routing should enter
  `flowguard-development-process-flow` and use the corresponding internal mode

### Requirement: Global prompt guidance describes the new topology
The reusable AGENTS snippet SHALL describe the FlowGuard architecture as one
kernel, direct specialist satellites, and one development-process simulator
front door that owns three internal modes: `plan_detailing`,
`agent_workflow`, and `execution_freshness`.

#### Scenario: Repository copies AGENTS guidance
- **WHEN** another repository copies `docs/agents_snippet.md`
- **THEN** it learns that generic plan discussion, multi-skill workflow, and
  staged execution enter `flowguard-development-process-flow` first
- **AND** it learns that PlanDetailing and AgentWorkflowRehearsal remain
  delegated helpers for explicit or simulator-selected use

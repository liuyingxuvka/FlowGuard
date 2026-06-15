# flowguard-codex-skill-satellites Specification

## Purpose
This capability defines FlowGuard's Flowguard Codex Skill Satellites behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Kernel remains the canonical FlowGuard entrypoint
The repository SHALL keep `model-first-function-flow` as the canonical
FlowGuard Skill Kernel for applicability decisions, hard gates, flow lenses,
ambiguous route selection, package import verification, and adoption evidence.

#### Scenario: Ambiguous request starts at the kernel
- **WHEN** a Codex task involves FlowGuard risks but does not clearly name one
  standalone satellite skill
- **THEN** the `model-first-function-flow` Skill remains the correct entrypoint
  and selects the matching route or routes

### Requirement: Seven route-specific satellite skills are directly discoverable
The repository SHALL provide seven standalone Codex skills:
`flowguard-model-test-alignment`, `flowguard-development-process-flow`,
`flowguard-model-miss-review`, `flowguard-code-structure-recommendation`,
`flowguard-model-mesh`, `flowguard-test-mesh`, and
`flowguard-structure-mesh`.

#### Scenario: Clear route request invokes a satellite
- **WHEN** a user directly asks for a mature route such as Model-Test
  Alignment, DevelopmentProcessFlow, ModelMesh, TestMesh, or StructureMesh
- **THEN** Codex can invoke the matching standalone FlowGuard skill without
  treating package helper APIs as skills

### Requirement: Satellite skills preserve FlowGuard hard gates
Each satellite skill SHALL preserve FlowGuard's hard gates: use the real
`flowguard` package, represent modeled blocks as `Input x State ->
Set(Output x State)` where modeling is needed, keep skipped evidence visible,
avoid fake mini-frameworks, avoid weakening invariants, and route ambiguous
cross-cutting work back to the kernel.

#### Scenario: Satellite skill runs in another repository
- **WHEN** a standalone satellite skill is used in another repository
- **THEN** it tells Codex to verify the real FlowGuard package before claiming
  FlowGuard adoption or route confidence

### Requirement: Satellite skills remain discoverable route shells

FlowGuard SHALL preserve direct satellite skills as concise route shells with
standalone hard gates, trigger/skip criteria, minimum workflow, snapshot
guidance, non-goals, and reference handoff.

#### Scenario: Satellite skill count is not reduced by structure cleanup

- **WHEN** implementation surfaces are simplified
- **THEN** existing satellite skill names remain discoverable and their
  `SKILL.md` files remain within prompt budgets

#### Scenario: Hard gates remain visible

- **WHEN** a satellite skill is read without deep reference files
- **THEN** real-package verification, project adoption records, fake-framework
  rejection, and route-specific evidence honesty remain visible

### Requirement: Global prompt guidance describes the new topology
The reusable AGENTS snippet SHALL describe the FlowGuard architecture as one
kernel plus seven directly invokable satellite skills, while keeping
`conformance_adoption`, `long_check_observability`, and `framework_upgrade` as
kernel-routed support protocols.

#### Scenario: Repository copies AGENTS guidance
- **WHEN** another repository copies `docs/agents_snippet.md`
- **THEN** it learns which FlowGuard skills are direct Codex skills and which
  protocols remain routed through the kernel

### Requirement: Installed skills are synchronized before release
The release process SHALL sync the repository skill directories to the local
Codex installed skills directory and verify the installed skill set before
publishing a GitHub Release.

#### Scenario: Release validation checks installed behavior
- **WHEN** a new FlowGuard release is prepared
- **THEN** repository skills, installed Codex skills, package version,
  shadow workspace import, git tag, and GitHub Release version are checked for
  alignment

### Requirement: Satellite skills preserve target-project adoption
Every directly invokable FlowGuard satellite Skill SHALL preserve the target
project AGENTS/version adoption check so direct satellite use cannot bypass the
kernel's project adoption rule.

#### Scenario: Satellite runs in target project
- **WHEN** a standalone FlowGuard satellite Skill is used for real target
  project work
- **THEN** it tells the agent to ensure the project has a FlowGuard AGENTS
  managed block and project version record, or to record why that update was
  not performed

### Requirement: Agent workflow rehearsal satellite is discoverable as a delegated mode owner
The repository SHALL provide `flowguard-agent-workflow-rehearsal` as a
FlowGuard skill that Codex can invoke when explicitly requested or delegated by
the development-process simulator `agent_workflow` mode.

#### Scenario: Rehearsal satellite is listed with delegated role
- **WHEN** a Codex agent reads the FlowGuard skill topology or reusable AGENTS
  guidance
- **THEN** `flowguard-agent-workflow-rehearsal` appears as the delegated
  `agent_workflow` owner
- **AND** generic multi-skill workflow routing enters
  `flowguard-development-process-flow` first

#### Scenario: Rehearsal satellite preserves hard gates
- **WHEN** the satellite is used in another repository or machine
- **THEN** it requires the real FlowGuard package for FlowGuard claims
- **AND** it requires a fresh current-machine skill inventory before rehearsal

### Requirement: Installed skill synchronization includes rehearsal satellite
The release and local synchronization process SHALL include
`flowguard-agent-workflow-rehearsal` in repository and installed Codex skill
surface checks.

#### Scenario: Installed skill is synchronized
- **WHEN** the change is validated for local use
- **THEN** the installed Codex skills directory contains the new rehearsal
  satellite
- **AND** repository skill docs tests verify the satellite topology

#### Scenario: Installed prompt behavior is not claimed from repository-only changes
- **WHEN** the repository copy of the skill has changed
- **THEN** the change is not reported as active installed behavior until the
  installed skill surface is synchronized or explicitly reported as unsynced

### Requirement: Installed skill route alignment
Installed FlowGuard Codex skill route maps SHALL stay aligned with the package route graph, including route ids, triggers, minimal workflow, hard gates, evidence boundaries, and downstream handoffs.

#### Scenario: Package route graph adds a group
- **WHEN** the package route graph adds or changes a route group
- **THEN** installed skill guidance SHALL be updated or the mismatch SHALL be recorded as a scoped maintenance obligation

### Requirement: Codex exposes a topology hazard satellite skill

FlowGuard SHALL expose `flowguard-model-topology-hazard-review` as a direct
Codex satellite skill while keeping the model-first kernel as the router for
ambiguous or cross-route work.

#### Scenario: Skill route is present and prompt-grounded

- **WHEN** the Codex skill directories are inspected
- **THEN** `flowguard-model-topology-hazard-review` MUST have a concise
  `SKILL.md`, OpenAI agent metadata, a protocol reference, and a lazy-loaded
  prompt template
- **AND** the kernel route map MUST route model-shape future-use hazards to the
  new satellite skill.

### Requirement: Satellite reference protocols own detailed route guidance
Each directly invokable FlowGuard satellite SHALL own its detailed protocol in
the satellite `references/` directory when that route has a standalone skill.

#### Scenario: Kernel reference duplicates are folded
- **WHEN** the kernel reference directory includes a protocol whose detailed
  route is owned by a standalone satellite
- **THEN** the kernel copy is either absent or a compact handoff stub
- **AND** the satellite reference remains reachable and substantive

#### Scenario: Standalone satellite remains usable
- **WHEN** a satellite skill is installed or copied independently
- **THEN** its `SKILL.md` and satellite reference provide the route trigger,
  hard gates, workflow checklist, validation boundary, and non-goals without
  requiring the kernel's duplicate copy

### Requirement: Plan detailing is exposed as a delegated mode owner
FlowGuard SHALL include `flowguard-plan-detailing-compiler` as the delegated
`plan_detailing` owner that remains directly invokable when explicitly named.

#### Scenario: Delegated skill is discoverable
- **WHEN** the FlowGuard Codex skill topology is read
- **THEN** plan detailing appears as the `plan_detailing` owner
- **AND** generic rough-plan routing enters `flowguard-development-process-flow`
  first

#### Scenario: Installed skill sync covers plan detailing
- **WHEN** the repository skill is updated
- **THEN** installed Codex skill synchronization checks include the plan-detailing satellite

### Requirement: Satellite skills use concise route shells
Each directly invokable FlowGuard satellite skill SHALL keep its `SKILL.md`
first-read surface to a concise route shell while preserving standalone hard
gates and a clear reference handoff.

#### Scenario: Satellite route shell is inspected
- **WHEN** a repository-managed satellite `SKILL.md` is read by an agent
- **THEN** it contains the skill name, route trigger, skip/return guidance, hard
  gates, a minimum workflow, validation/claim boundary notes, non-goals, and a
  route-specific reference path without embedding the full protocol inline

#### Scenario: Standalone use keeps hard gates
- **WHEN** a satellite skill is copied or installed outside the FlowGuard repo
- **THEN** it still tells the agent to use the real FlowGuard package, preserve
  AGENTS/version adoption checks for real project use, keep skipped evidence
  visible, and avoid fake mini-frameworks

### Requirement: Installed satellite sync is content-aware
Installed FlowGuard satellite skill synchronization SHALL verify repository and
installed skill content rather than only checking that a directory exists.

#### Scenario: Existing installed skill is refreshed
- **WHEN** a repository-managed satellite skill already exists in the local
  installed Codex skills directory
- **THEN** synchronization refreshes changed content or reports an explicit
  mismatch before local installed behavior is claimed

### Requirement: Installed UI skills require human-operability routing
FlowGuard Codex skill satellites SHALL route UI completion, usability, and
human-operable claims through user task coverage and human-operability evidence
rather than treating visible inventory or functional chains as sufficient.

#### Scenario: Skill prompt omits task coverage
- **WHEN** the UI Flow skill is used for a complete UI claim
- **THEN** its guidance must require user task coverage, task-to-feature,
  task-to-UI, affordance, action grammar, dialog/window, keyboard/focus, and
  walkthrough evidence before human-operable confidence

### Requirement: Installed UI skills use generic source-baseline routing
FlowGuard Codex skill satellites SHALL keep installed UI and process skill guidance generic for source-based UI work.

#### Scenario: UI skill names generic work mode
- **WHEN** the installed UI Flow Structure skill is read
- **THEN** it routes by greenfield, source-based, and mixed work mode and names source-baseline mapping, approved differences, generic source interactions, and observed-source alignment

#### Scenario: Installed skill hard-codes one source technology
- **WHEN** installed FlowGuard UI or development process skill guidance hard-codes one source technology as a generic gate
- **THEN** the installed skill sync is incomplete

### Requirement: FlowGuard skills expose writing-quality process gates
FlowGuard Codex skill guidance SHALL mention writing-quality ledgers as process
evidence when prompt, skill, or document workflows depend on academic or
source-backed writing quality.

#### Scenario: DevelopmentProcessFlow skill is read
- **WHEN** an agent uses DevelopmentProcessFlow for thesis, report, paper, or
  source-backed writing upgrades
- **THEN** the skill guidance MUST name literature progression, method depth,
  figure/table argument treatment, AI-style density, and citation/footnote
  verification as possible freshness-sensitive artifacts

### Requirement: Plan detailing is a delegated simulator mode owner
FlowGuard Codex skill guidance SHALL present `flowguard-plan-detailing-compiler`
as the delegated `plan_detailing` owner for non-trivial plan discussions and
rough AI outlines after the DevelopmentProcessFlow simulator front door records
the mode.

#### Scenario: Plan detailing appears as delegated owner
- **WHEN** a Codex agent reads FlowGuard skill topology or reusable AGENTS guidance
- **THEN** `flowguard-plan-detailing-compiler` appears as the delegated
  `plan_detailing` owner under `flowguard-development-process-flow`

#### Scenario: Plan discussion records mode before delegation
- **WHEN** the task is a non-trivial plan discussion before implementation
- **THEN** Codex skill guidance selects DevelopmentProcessFlow first and records
  `plan_detailing` before any delegated PlanDetailing pass

### Requirement: Installed skills include updated plan-detailing guidance
Installed FlowGuard Codex skill synchronization SHALL refresh the local installed `flowguard-plan-detailing-compiler`, `flowguard-agent-workflow-rehearsal`, and `flowguard-development-process-flow` guidance when repository routing changes.

#### Scenario: Installed guidance is synchronized
- **WHEN** repository skill guidance is updated for plan discussion handoff
- **THEN** local installed skill copies are synchronized or an explicit unsynced boundary is reported before local Codex behavior is claimed

### Requirement: Installed UI skill guidance teaches real-surface first gate
FlowGuard Codex skill satellite guidance SHALL state that existing/runnable UI
work starts from observed real UI inventory, maps every visible item to a model
owner or blindspot, validates enabled controls through real functional chains,
and uses final done-claim review before broad completion wording.

#### Scenario: Repository and installed skills align
- **WHEN** the repository UI Flow, Model Miss, DevelopmentProcessFlow,
  AgentWorkflowRehearsal, or Closure guidance changes
- **THEN** installed Codex skill copies must be synchronized or final
  confidence must stay scoped

#### Scenario: Compact template cannot prove completion
- **WHEN** a public compact template is used for UI route exploration
- **THEN** the guidance says compact output is not runnable/complete UI
  evidence unless observed inventory, functional-chain, and implementation
  validation gates are also current

### Requirement: Satellite skill guidance teaches validation gates
FlowGuard Codex satellite skills SHALL surface the new UI and artifact payload
validation evidence gates in their concise route shells or reference protocols.

#### Scenario: UI satellite is read
- **WHEN** an agent reads `flowguard-ui-flow-structure`
- **THEN** the guidance MUST say runnable UI completion requires reachable
  actionable controls/events to have run evidence, pure-UI classification, or
  scoped blindspots

#### Scenario: Alignment and TestMesh satellites are read
- **WHEN** an agent reads Model-Test Alignment or TestMesh guidance
- **THEN** the guidance MUST route artifact payload contracts to Model-Test
  Alignment and large payload evidence matrices to TestMesh

### Requirement: Installed skill sync covers validation gate changes
Installed FlowGuard skill synchronization SHALL verify that local installed
skills include validation gate guidance before active installed behavior is
claimed.

#### Scenario: Installed skill is stale
- **WHEN** repository skill content includes validation gate guidance
- **AND** the installed skill copy does not
- **THEN** release or local sync confidence MUST remain scoped until the
  installed skill is refreshed or the mismatch is reported


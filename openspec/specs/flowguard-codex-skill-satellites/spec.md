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

### Requirement: Agent workflow rehearsal satellite is directly discoverable
The repository SHALL provide `flowguard-agent-workflow-rehearsal` as a
standalone FlowGuard satellite skill that Codex can invoke directly.

#### Scenario: Rehearsal satellite is listed with peers
- **WHEN** a Codex agent reads the FlowGuard skill topology or reusable AGENTS
  guidance
- **THEN** `flowguard-agent-workflow-rehearsal` appears as a peer FlowGuard
  satellite beside the existing route-specific satellites

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

### Requirement: Plan detailing is exposed as a direct Codex satellite
FlowGuard SHALL include `flowguard-plan-detailing-compiler` as a directly invokable Codex satellite skill.

#### Scenario: Satellite is discoverable
- **WHEN** the FlowGuard Codex skill topology is read
- **THEN** plan detailing appears beside the existing direct satellites

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

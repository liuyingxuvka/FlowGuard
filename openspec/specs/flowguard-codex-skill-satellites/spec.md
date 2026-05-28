# flowguard-codex-skill-satellites Specification

## Purpose
TBD - created by archiving change split-flowguard-codex-skills. Update Purpose after archive.
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

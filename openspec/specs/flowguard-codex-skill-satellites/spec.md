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

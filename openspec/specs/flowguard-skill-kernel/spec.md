# flowguard-skill-kernel Specification

## Purpose
This capability defines FlowGuard's Flowguard Skill Kernel behavior and the evidence required to use it safely in AI-agent maintenance workflows.
## Requirements
### Requirement: Skill Kernel remains compact and route-oriented
The `model-first-function-flow` Skill SHALL keep its main `SKILL.md` focused on
triggering, hard gates, route selection, workflow skeleton, and resource
mapping.

#### Scenario: Oversized work receives a soft split hint
- **WHEN** a model, test, script, module, or command is becoming large, slow, or
  hard to follow
- **THEN** the Skill suggests considering whether a parent/child split would
  improve maintainability or verification
- **AND** the Skill does not require fixed runtime thresholds or mandatory
  splitting

#### Scenario: External planning artifacts remain optional
- **WHEN** a compatible planning or specification artifact exists
- **THEN** the Skill may inspect it as optional context
- **AND** FlowGuard remains usable without any external planner

### Requirement: Sub-protocol ownership is explicit
FlowGuard SHALL distinguish agent sub-protocols from package helper APIs.

#### Scenario: API helper is not a sub-skill
- **WHEN** the route map lists `RiskIntent`, templates, property factories, or
  mesh review functions
- **THEN** it identifies them as helper APIs rather than standalone agent
  skills

### Requirement: Hard gates are not delegated away
The Skill Kernel SHALL preserve non-negotiable rules even when detailed
procedures move into references.

#### Scenario: Real package gate remains visible
- **WHEN** FlowGuard applies to repository work
- **THEN** the kernel still requires verifying the real package import and
  forbids fake mini-framework substitutes

#### Scenario: Skipped checks stay visible
- **WHEN** a model, replay, test, release, or adoption check is skipped
- **THEN** the kernel requires a reason and prevents treating the skipped check
  as a pass

### Requirement: Known-bad modularization hazards are modeled
FlowGuard SHALL include executable evidence for Skill Kernel modularization.

#### Scenario: Missing route fails
- **WHEN** a modular Skill removes a required ModelMesh, TestMesh,
  StructureMesh, model-miss, long-check, conformance/adoption, or framework
  upgrade route
- **THEN** the rollout model reports a violation

#### Scenario: Heavy checks over-trigger
- **WHEN** the kernel requires heavy framework checks for ordinary narrow
  project work
- **THEN** the rollout model reports a violation

#### Scenario: Helper APIs become fake sub-skills
- **WHEN** package helper APIs are classified as independently triggerable
  sub-skills
- **THEN** the rollout model reports a violation

### Requirement: Kernel requires target-project adoption rule
The FlowGuard Skill Kernel SHALL tell agents that real FlowGuard use in another
repository must check whether the target project carries a FlowGuard
`AGENTS.md` adoption block.

#### Scenario: Target project lacks FlowGuard AGENTS block
- **WHEN** the kernel is used for non-trivial FlowGuard work in another
  repository
- **AND** the target project lacks a FlowGuard managed `AGENTS.md` block
- **THEN** the kernel instructs the agent to add or update the block from the
  canonical FlowGuard snippet unless the user requested read-only work

#### Scenario: Read-only work does not force writes
- **WHEN** the user explicitly requests read-only analysis
- **THEN** the kernel may report the missing AGENTS block as a gap without
  writing project files

### Requirement: Kernel references use compact handoff stubs for satellite-owned protocols
The FlowGuard Skill Kernel SHALL avoid carrying full duplicate copies of
satellite-owned reference protocols.

#### Scenario: Duplicate protocol copy is detected
- **WHEN** a kernel reference file is byte-for-byte identical to a satellite
  reference file
- **THEN** skill documentation tests fail or require the kernel copy to become
  a compact handoff stub

#### Scenario: Handoff stub remains useful
- **WHEN** an agent opens a kernel-side handoff stub
- **THEN** it states that the satellite owns the detailed protocol
- **AND** it names the satellite skill and detailed reference file to load next

### Requirement: Skill kernel keeps template library compact
The FlowGuard skill kernel SHALL expose risk-template reuse as a compact
pre/post model gate without moving the full template-library protocol into the
first-read skill body.

#### Scenario: Kernel first read stays compact
- **WHEN** the model-first skill kernel is read
- **THEN** it states the minimum valuable model gate and template search/harvest rule without embedding long public template catalogs

#### Scenario: Detailed protocol remains referenced
- **WHEN** an agent needs implementation detail for template library behavior
- **THEN** the kernel points to route docs, helpers, or CLI commands rather than expanding every field inline

### Requirement: Skill hot path enforces harvest closure
The FlowGuard skill kernel SHALL state that template harvest closure is required
after any new or materially deepened model while keeping detailed template
catalogs out of the hot path.

#### Scenario: Agent reads model-first hot path
- **WHEN** an agent reads the model-first kernel or reusable AGENTS snippet
- **THEN** the minimum workflow includes harvest closure as written, merged, duplicate-linked, or not-harvestable with an accepted reason
- **AND** it does not embed long public or local template catalogs

#### Scenario: Satellite route bypass is prevented
- **WHEN** a directly routed satellite skill creates or deepens a model
- **THEN** its first-read guidance also requires template harvest closure before broad completion claims


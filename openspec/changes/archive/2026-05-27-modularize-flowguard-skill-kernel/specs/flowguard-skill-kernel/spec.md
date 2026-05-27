## ADDED Requirements

### Requirement: Skill Kernel remains compact and route-oriented
The `model-first-function-flow` Skill SHALL keep its main `SKILL.md` focused on
triggering, hard gates, route selection, workflow skeleton, and resource
mapping.

#### Scenario: Kernel routes to sub-protocol
- **WHEN** a task involves slow validation, structure decomposition, multiple
  models, model misses, or framework upgrade claims
- **THEN** the Skill points to the matching sub-protocol reference instead of
  inlining the full procedure in the kernel

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

## MODIFIED Requirements

### Requirement: Development process simulator is the AI-facing front door
FlowGuard SHALL expose one AI-facing development-process simulator entry for rough plan discussion, multi-skill/tool workflow rehearsal when risk-admitted, staged execution, validation freshness, install/shadow/git sync, and release/archive/publish claims.

#### Scenario: Rough plan enters front door
- **WHEN** a non-trivial user request asks to discuss, refine, or make a plan detailed before implementation
- **THEN** the AI-facing entry SHALL be `flowguard-development-process-flow`
- **AND** the simulator SHALL select `plan_detailing` as an internal mode

#### Scenario: Multi-skill workflow enters front door
- **WHEN** a non-trivial user request requires risk-admitted capability sequencing such as an explicit rehearsal request, shared writes, a write that can invalidate post-validation evidence, an agent/route workflow change, or multiple independent owners with irreversible side effects
- **THEN** the AI-facing entry SHALL be `flowguard-development-process-flow`
- **AND** the simulator SHALL select `agent_workflow` as an internal mode

#### Scenario: Low-risk capability surface skips rehearsal
- **WHEN** a task is simple read-only work, has one owner and one tool, and only needs targeted checks
- **AND** the request has no explicit rehearsal or risk-admission fact
- **THEN** the simulator SHALL leave `agent_workflow` `not_triggered`
- **AND** it SHALL not create a workflow inventory, rehearsal plan, or receipt

#### Scenario: Capability labels alone do not admit rehearsal
- **WHEN** a request merely names multiple skills, tools, plugins, an external-effect label, or a cross-owner handoff
- **AND** it has no explicit rehearsal, shared-write, post-validation-invalidating-write, route-change, or multi-owner irreversible side-effect fact
- **THEN** the simulator SHALL keep `agent_workflow` unselected
- **AND** the owning DevelopmentProcessFlow route and author-side native checks SHALL remain authoritative

#### Scenario: Ordinary cross-owner handoff enters freshness only
- **WHEN** a staged task hands work from one owner to another and has no shared write, post-validation-invalidating write, route change, multiple-owner irreversible side effect, or explicit rehearsal request
- **THEN** the simulator SHALL select `execution_freshness` for the staged work
- **AND** it SHALL leave `agent_workflow` `not_triggered` without creating a rehearsal plan or receipt

#### Scenario: Cross-owner handoff includes an independent risk trigger
- **WHEN** a staged task hands work between owners and also has a shared write, post-validation-invalidating write, route change, multiple-owner irreversible side effect, or explicit rehearsal request
- **THEN** the simulator SHALL select `agent_workflow` for that risk reason
- **AND** the relevant execution-freshness mode SHALL remain separately governed

#### Scenario: Execution freshness enters front door
- **WHEN** a non-trivial user request includes implementation, validation, install sync, shadow workspace sync, local git evidence, release, archive, or publish confidence
- **THEN** the AI-facing entry SHALL be `flowguard-development-process-flow`
- **AND** the simulator SHALL select `execution_freshness` as an internal mode

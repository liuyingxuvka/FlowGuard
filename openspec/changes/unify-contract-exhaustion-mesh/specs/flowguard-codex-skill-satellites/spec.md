## ADDED Requirements

### Requirement: Contract-exhaustion route has a thin satellite skill
FlowGuard MUST expose a `flowguard-contract-exhaustion-mesh` satellite skill
that routes finite bad-case generation through ContractExhaustionMesh while
preserving existing proof-route ownership.

#### Scenario: Agent routes same-class generation to thin skill
- **WHEN** an agent needs to generate same-class or finite boundary bad cases
- **THEN** the skill directs the agent to use ExistingModelPreflight and
  ContractExhaustionMesh before handing off to proof routes

#### Scenario: Skill refuses fallback case generation
- **WHEN** an agent tries to use hand-written same-class cases as canonical
  coverage
- **THEN** the skill instructs the agent to produce canonical case ids or report
  a scoped/model-gap result

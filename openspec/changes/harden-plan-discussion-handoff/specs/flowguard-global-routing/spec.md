## ADDED Requirements

### Requirement: Global routing sends rough plan discussions to PlanDetailing
Global FlowGuard routing SHALL send non-trivial plan discussions,方案 discussions, acceptance-standard discussions, execution-step discussions, and AI-generated outlines to `flowguard-plan-detailing-compiler` before implementation or final confidence routes.

#### Scenario: Plan discussion selects plan detailing
- **WHEN** a non-trivial user request asks to discuss, design, refine, or agree on a plan before execution
- **THEN** global routing selects `flowguard-plan-detailing-compiler` as the first direct FlowGuard satellite route

#### Scenario: Structured lifecycle review can use development process directly
- **WHEN** the user already provides structured lifecycle rows, artifact versions, validation evidence, and freshness rules
- **THEN** global routing may select `flowguard-development-process-flow` directly for lifecycle freshness review

### Requirement: Global routing composes plan-detailing, rehearsal, and development process
Global FlowGuard routing SHALL compose PlanDetailing, AgentWorkflowRehearsal, and DevelopmentProcessFlow by ownership rather than forcing every task through a universal parent route.

#### Scenario: Multi-skill plan composes routes
- **WHEN** a plan discussion produces structured PlanDetail rows and the work involves multiple skills, tools, agents, or side effects
- **THEN** global routing hands the PlanDetail projection to AgentWorkflowRehearsal before execution

#### Scenario: Execution freshness composes routes
- **WHEN** the same plan enters implementation, validation, done, release, archive, or publish review
- **THEN** global routing hands the PlanDetail projection to DevelopmentProcessFlow for lifecycle freshness and claim support

### Requirement: Global routing blocks prose-only broad claims
Global FlowGuard routing SHALL prevent broad done, release, publish, archive, or production-confidence claims from relying only on prose plans when the task was non-trivial.

#### Scenario: Prose plan cannot support full completion
- **WHEN** a non-trivial plan discussion has no PlanDetail rows, workflow rehearsal handoff, or current lifecycle evidence
- **THEN** global routing keeps the final claim scoped or blocked until the missing structured evidence is created

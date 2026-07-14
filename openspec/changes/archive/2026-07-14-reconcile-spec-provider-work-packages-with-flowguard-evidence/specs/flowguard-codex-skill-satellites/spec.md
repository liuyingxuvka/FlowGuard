## ADDED Requirements

### Requirement: Native skills route spec reconciliation through existing owners
FlowGuard's maintained skills SHALL direct spec work-package planning and verification through DevelopmentProcessFlow, PlanDetailing, ExistingModelPreflight, and TestMesh native routes with SkillGuard as contract supervisor only.

#### Scenario: Agent plans a multi-spec workflow
- **WHEN** an agent uses OpenSpec or Spec Kit with FlowGuard in one non-trivial change
- **THEN** skill guidance SHALL require provider authority, bidirectional mapping, begin/post freshness, terminal receipts, and explicit reuse boundaries without creating a second spec workflow

#### Scenario: Product UI guidance is rendered
- **WHEN** the task concerns internal spec-tool orchestration
- **THEN** the skill guidance SHALL NOT project work-package fields into product UI content or visibility rules

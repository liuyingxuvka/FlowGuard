## ADDED Requirements

### Requirement: Five maintained prompts use provider-neutral WorkContext guidance
The maintained `flowguard`, `flowguard-behavior-commitment-ledger`, `flowguard-existing-model-preflight`, `flowguard-development-process-flow`, and `flowguard-test-mesh` prompt surfaces SHALL use the same provider-neutral WorkContext vocabulary and generic artifact roles. They SHALL route WorkContext through the existing Behavior Commitment Ledger, ExistingModelPreflight, DevelopmentProcessFlow, PlanDetailing, and TestMesh owners without creating a provider-specific satellite, parallel workflow, or OpenSpec-default path.

#### Scenario: Any supported provider supplies work artifacts
- **WHEN** OpenSpec, declared files, a Spec Kit profile, a Superpowers profile, or another registered provider supplies requirements, plans, designs, tasks, or status artifacts
- **THEN** the five maintained prompt surfaces SHALL describe those artifacts through the same WorkContext roles and SHALL preserve the provider's native artifact and lifecycle authority

#### Scenario: No provider is selected
- **WHEN** a FlowGuard task has no external work-context provider
- **THEN** the existing FlowGuard routes SHALL remain usable as a standalone workflow without inventing provider artifacts or selecting OpenSpec by default

#### Scenario: A prompt treats provider completion as test evidence
- **WHEN** any maintained prompt proposes that provider status, task checkboxes, or artifact completion proves model or test execution
- **THEN** its native semantic checks and SkillGuard-supervised maintenance SHALL reject that guidance

#### Scenario: Internal work context reaches product UI guidance
- **WHEN** the task concerns provider orchestration, artifact discovery, or internal status
- **THEN** the maintained prompts SHALL keep that information internal and SHALL NOT project it into product UI content or visibility rules

### Requirement: Provider integrations remain outside FlowGuard skill authority
FlowGuard's maintained prompts SHALL describe adapter boundaries and generic roles but SHALL NOT take maintenance, execution, installation, or lifecycle ownership of official OpenSpec, Spec Kit, Superpowers, or other third-party provider skills. SkillGuard supervision SHALL apply only to the five declared FlowGuard prompt surfaces and their existing maintenance unit.

#### Scenario: A third-party provider skill changes
- **WHEN** an official or third-party provider skill changes its commands, artifacts, or lifecycle
- **THEN** FlowGuard SHALL preserve that skill as an external native owner and SHALL update only its own adapter or prompt contract when the generic WorkContext boundary is affected

#### Scenario: FlowGuard prompt maintenance is performed
- **WHEN** one of the five declared FlowGuard prompt surfaces is changed
- **THEN** the existing SkillGuard maintenance unit SHALL supervise the FlowGuard-owned change without enrolling, copying, or validating the provider skill itself

## REMOVED Requirements

### Requirement: Native skills route spec reconciliation through existing owners
**Reason**: The requirement encoded provider-specific Spec Work Package sessions, receipts, freshness, and reconciliation as the common route. The replacement WorkContext is provider-neutral, read-only, and has no provider execution or receipt authority.

**Migration**: Use the five maintained provider-neutral prompt surfaces and their existing FlowGuard owners. Preserve provider-native lifecycles externally and admit actual validator evidence to TestMesh only through a separately declared native execution owner.

#### Scenario: A maintained prompt encounters external work artifacts
- **WHEN** a maintained FlowGuard prompt discovers requirements, designs, plans, tasks, or status from any provider
- **THEN** it SHALL use read-only WorkContext guidance and SHALL NOT start a Spec Work Package session, receipt lifecycle, or provider execution route

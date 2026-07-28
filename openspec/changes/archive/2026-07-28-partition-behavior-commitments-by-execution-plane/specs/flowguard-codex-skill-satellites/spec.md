## ADDED Requirements

### Requirement: Existing skills teach behavior-plane ownership
The existing BCL, Existing Model Preflight, Model Miss, DevelopmentProcessFlow, AgentWorkflowRehearsal, PlanDetailing, and model-first skill guidance SHALL describe the three behavior planes and their route-native ownership boundaries without adding a new skill route.

#### Scenario: BCL skill creates a commitment
- **WHEN** the BCL skill adds, changes, removes/replaces, gap-backfills, or checks a model-miss commitment
- **THEN** it SHALL classify behavior plane and actor kind before broad confidence
- **AND** SHALL require typed cross-plane relations

#### Scenario: Preflight skill retrieves related product context
- **WHEN** an AI-operation task relates to a product commitment
- **THEN** the preflight skill SHALL keep the AI commitment primary and label the product commitment as related context

#### Scenario: Model Miss asks whose promise failed
- **WHEN** a concrete post-green failure is reviewed
- **THEN** the Model Miss skill SHALL identify the affected plane before backfeed

### Requirement: Process and agent skills do not absorb sibling planes
DevelopmentProcessFlow SHALL remain the development lifecycle owner, and AgentWorkflowRehearsal SHALL remain the AI-operation plan/evidence owner; neither SHALL treat related product behavior as its own implementation instructions.

#### Scenario: Product behavior model is consulted by agent workflow
- **WHEN** an agent operation invokes or validates a product commitment
- **THEN** AgentWorkflowRehearsal SHALL treat the product model as target context
- **AND** its own ordered steps SHALL come from the agent-operation owner model

### Requirement: Skill source, generated contract, and installed copy stay synchronized
Affected skill changes SHALL update canonical `SKILL.md`, directly required references, `agents/openai.yaml`, and `.skillguard/contract-source.json`, then regenerate derived contracts and verify shadow/formal installed parity.

#### Scenario: Generated contract is hand-edited
- **WHEN** a derived compiled contract differs without a matching contract-source change
- **THEN** SkillGuard validation SHALL fail the skill target

#### Scenario: Installed copy is stale
- **WHEN** canonical and compiled skill checks pass but the installed skill differs
- **THEN** project closure SHALL remain blocked until installer check/parity passes

### Requirement: Guidance remains advisory outside existing hard gates
Skill guidance SHALL make registered same-plane models visible without imposing a new universal requirement that every trivial action execute a model.

#### Scenario: Existing release gate applies
- **WHEN** a task reaches an existing irreversible/release/full-claim gate
- **THEN** route-native evidence requirements SHALL still apply
- **AND** this change SHALL NOT weaken them

#### Scenario: Ordinary task has no registered hit
- **WHEN** a non-trivial lookup returns no same-plane commitment and no concrete miss exists
- **THEN** Codex MAY continue through existing routing with an explicit no-hit boundary rather than fabricating a commitment

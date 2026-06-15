## ADDED Requirements

### Requirement: Multi-agent UI workflows use generic source evidence roles
AgentWorkflowRehearsal SHALL describe UI evidence roles generically as source-baseline inventory, user task flow, target difference review, implementation validation, and integration evidence roles.

#### Scenario: Source-based UI has role evidence
- **WHEN** a multi-agent workflow includes source-based UI scope
- **THEN** rehearsal requires a source-baseline evidence role, a target-difference review role, and an implementation validation role before full runnable UI confidence

#### Scenario: Generic role names avoid source-specific hard gates
- **WHEN** AgentWorkflowRehearsal guidance names UI evidence roles
- **THEN** it does not hard-code one source technology as the generic role name

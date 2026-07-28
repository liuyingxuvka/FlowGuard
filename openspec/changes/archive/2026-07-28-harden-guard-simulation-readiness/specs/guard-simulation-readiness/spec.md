## ADDED Requirements

### Requirement: Kernel Skill Must Preserve Route-Specific Diagram Semantics

FlowGuard SHALL instruct agents to choose diagram forms that preserve the active guard model instead of flattening every route into a generic flowchart.

#### Scenario: Installed kernel skill is inspected

- **WHEN** downstream tests read the installed `model-first-function-flow` skill
- **THEN** the text includes a FlowGuard diagram intent gate
- **AND** it includes route-specific warnings for LogicGuard use.

### Requirement: Skill Contracts Must Preserve Native FlowGuard Ownership

FlowGuard skill contracts SHALL say that duplicate SkillGuard-owned execution paths are invalid while preserving native FlowGuard check ownership.

#### Scenario: Route checker validates contracts

- **WHEN** SkillGuard route checks inspect FlowGuard skill contracts
- **THEN** the contracts pass anti-bypass checks
- **AND** native FlowGuard model checks remain the authority for behavior claims.

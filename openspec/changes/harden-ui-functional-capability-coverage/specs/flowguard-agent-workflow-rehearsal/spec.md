## ADDED Requirements

### Requirement: Multi-agent UI work includes capability coverage role
AgentWorkflowRehearsal SHALL account a UI functional capability inventory and coverage role before full runnable UI confidence when multiple agents collaborate on UI work.

#### Scenario: Multi-agent UI implementation has capability checker
- **WHEN** a multi-agent workflow claims an implemented UI is complete for user-visible functions
- **THEN** the rehearsal evidence includes a role responsible for capability inventory/coverage in addition to visible surface, source-baseline when applicable, user task flow, implementation validation, and integration evidence roles

#### Scenario: Capability role is missing
- **WHEN** UI agents divide design and code work but no role owns required capability inventory, output contracts, and capability-to-evidence binding
- **THEN** AgentWorkflowRehearsal keeps full runnable UI confidence blocked or scoped

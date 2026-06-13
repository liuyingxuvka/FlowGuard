## ADDED Requirements

### Requirement: UI plans name capability coverage evidence
PlanDetailing SHALL require non-trivial UI plans to name functional capability inventory, capability-task mapping, output contracts, implementation bindings, and evidence kinds before execution-ready or done-ready UI claims.

#### Scenario: UI plan names required capabilities
- **WHEN** a UI plan claims user-visible functionality will be implemented or completed
- **THEN** plan detail rows include capability inventory evidence, expected output contracts, implementation binding evidence, and validation or scoped-out boundaries

#### Scenario: UI plan only names controls
- **WHEN** a UI plan lists screens or buttons but omits the required functional capability inventory
- **THEN** the plan is incomplete for broad UI implementation or release claims

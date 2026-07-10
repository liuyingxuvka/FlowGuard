## ADDED Requirements

### Requirement: Canonical Route Ownership Projection
The global route registry SHALL be authoritative for stable route id, route role, entry policy, canonical owner skill, and typed next actions. Kernel route indexes, skill metadata, and generated route documentation MUST match that registry.

#### Scenario: Kernel route map names a different owner
- **WHEN** the kernel route projection disagrees with the registry's canonical owner
- **THEN** route-parity validation fails and identifies both owner values

#### Scenario: Prompt route id is stale
- **WHEN** a skill prompt declares a route id absent from the registry
- **THEN** route-parity validation fails before SkillGuard certification

### Requirement: Internal Ownership For Cross-Cutting Helpers
Primary Path Authority SHALL be an internal route owned by Behavior Commitment Ledger. Risk Evidence Ledger, FlowGuard self-maintenance, and Risk Template Library SHALL be kernel-owned internal routes unless a future specification promotes one to an independently invocable public skill. PlanDetailing and AgentWorkflow SHALL remain delegated modes owned by DevelopmentProcessFlow.

#### Scenario: Primary Path Authority is routed
- **WHEN** a path-sensitive commitment requires Primary Path Authority evidence
- **THEN** the handoff resolves to the BCL-owned internal PPA route and not to DevelopmentProcessFlow as a substitute public owner

#### Scenario: Kernel risk route is selected
- **WHEN** the kernel selects Risk Evidence Ledger for final claim gating
- **THEN** the target resolves as a kernel-owned internal route and does not require a nonexistent public skill

### Requirement: Default Replacement Of Legacy Handoffs
After migration, bare-string handoffs and legacy alias targets MUST NOT remain as an alternate successful routing path. Legacy input MAY produce a typed migration diagnostic but SHALL NOT be executed successfully.

#### Scenario: Legacy bare string is supplied
- **WHEN** a caller supplies an untyped historical next-action string
- **THEN** the system returns a migration error naming the required typed target and does not follow the legacy path

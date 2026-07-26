## ADDED Requirements

### Requirement: Managed adoption guidance uses the provider-neutral work-context rule
Generated and upgraded project guidance SHALL describe external requirements, plans, designs, tasks, and status through provider-neutral WorkContext and generic artifact roles. It SHALL NOT identify OpenSpec or any other provider as the sole or default provider, and it SHALL preserve standalone FlowGuard operation when no provider is selected. The retired provider-specific SpecContext rule SHALL be replaced directly without a compatibility alias, dual managed rule, or fallback execution path.

#### Scenario: A project uses a non-OpenSpec provider
- **WHEN** a project declares Spec Kit, Superpowers, a declared-file profile, or another registered provider
- **THEN** project audit SHALL accept the same current WorkContext contract without requiring OpenSpec artifacts or commands

#### Scenario: A project uses no external provider
- **WHEN** no WorkContext provider is configured for a project
- **THEN** the version gate SHALL keep normal FlowGuard adoption valid and SHALL NOT synthesize an implicit provider

#### Scenario: Retired provider-specific guidance remains
- **WHEN** managed project guidance still contains the retired SpecContext execution, receipt, or OpenSpec-default rule after upgrade
- **THEN** project audit SHALL report semantic drift and SHALL NOT treat the adoption projection as current

### Requirement: Managed adoption guidance exposes complete coverage gates
Current managed guidance SHALL state that broad behavior coverage depends on an independently derived expected inventory, exact `modeled`, `delegated`, or `scoped` disposition for every expected item, and current native UI and field inventory projections where those surfaces are in scope. The project audit SHALL compare the managed semantic rule and declared record identity but SHALL NOT execute a WorkContext provider or convert provider status into validation evidence.

#### Scenario: Adoption guidance omits the independent inventory gate
- **WHEN** a project's managed guidance permits broad coverage from caller-selected ledger rows alone
- **THEN** project audit SHALL report the coverage rule as stale or incomplete

#### Scenario: Provider status is present during project audit
- **WHEN** a provider reports a completed proposal, plan, design, or task list
- **THEN** project audit SHALL treat the status as contextual metadata only and SHALL NOT mark FlowGuard checks, models, tests, or evidence as passed

### Requirement: Coverage inventory identities participate in project freshness
When a project declares behavior, UI, field, or external work-context inventories, its adoption record SHALL preserve their current authority identities or declared discovery locations. A changed or missing required inventory identity SHALL be reported as a visible freshness or completeness issue rather than being ignored or repaired through a provider fallback.

#### Scenario: A declared UI inventory revision changes
- **WHEN** the current UI inventory fingerprint differs from the identity bound by the last broad coverage result
- **THEN** the project audit SHALL report the affected coverage evidence as stale without executing UI validation on behalf of its native owner

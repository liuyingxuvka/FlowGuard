## ADDED Requirements

### Requirement: Blueprint qualification and empirical reconstruction have separate lifecycle owners
DevelopmentProcessFlow SHALL track implementation inventory, binding, resource, projection, and static-closure freshness separately from empirical reconstruction evidence. It SHALL NOT automatically run an isolated reconstruction for ordinary changes, static checks, export, installation, or release unless the exact release requirement explicitly demands empirical reconstruction.

#### Scenario: Ordinary implementation changes one blueprint shard
- **WHEN** a changed file invalidates one inventory or binding shard
- **THEN** the process revalidates the affected owner closure without launching a whole repository reconstruction

#### Scenario: User explicitly requests reconstruction qualification
- **WHEN** the task explicitly requires empirical reconstruction and current static closure is complete
- **THEN** the process may schedule one separately owned isolated reconstruction and keeps not-run, pass, fail, or blocked visible

### Requirement: Final blueprint release freezes all consumed identities before the unique full gate
Before a release claims current software-blueprint closure, the process SHALL freeze source, observed model authority, implementation inventory, binding report, resource manifest, portable projection, skill projection, toolchain, and validation-plan identities. The unique final full gate SHALL run only after that freeze.

#### Scenario: Peer writes after the freeze
- **WHEN** a peer changes a consumed artifact after the final plan is frozen
- **THEN** affected evidence becomes stale and release publication remains blocked without rolling back the peer change

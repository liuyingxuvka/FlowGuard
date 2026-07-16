## ADDED Requirements

### Requirement: Simulator exposes an internal strategy-selection mode
The development process simulator SHALL select `strategy_selection` for non-trivial work with multiple viable sequences, material repeated-work risk, diagnostic campaign/batching decisions, or an explicit optimization claim, and SHALL keep DPF as the front door.

#### Scenario: Multiple viable repair sequences
- **WHEN** a staged plan can validly fail fast, collect diagnostics, or use safe parallel shards
- **THEN** the simulator selects `strategy_selection` and requires its review evidence before any enforced final claim

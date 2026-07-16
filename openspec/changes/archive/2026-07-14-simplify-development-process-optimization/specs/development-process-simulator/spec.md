## MODIFIED Requirements

### Requirement: Simulator exposes an internal strategy-selection mode
The development process simulator SHALL retain the internal mode id `strategy_selection` and DPF front door, but SHALL select it only when `process_optimization_reasons` includes an explicit optimization request, multiple outcome-equivalent viable routes, material repeated-work risk, or a diagnostic-boundary choice. The request SHALL carry one reason-id collection and one optimization-evidence-id collection instead of separate strategy booleans. Ordinary staged validation or a single obvious route SHALL NOT activate the mode.

#### Scenario: Multiple viable repair sequences
- **WHEN** a staged plan has two outcome-equivalent viable sequences with materially different repeated-work risk
- **THEN** the simulator selects `strategy_selection` and requires current process-optimization evidence before an enforced final claim

#### Scenario: Ordinary implementation has one sequence
- **WHEN** a staged implementation has one clear sequence and no optimization reason
- **THEN** the simulator may select other lifecycle modes but does not select `strategy_selection`

#### Scenario: Material evidence changes an active decision
- **WHEN** an active optimizer's input evidence changes
- **THEN** the simulator preserves the mode identity while DPF requires refreshed decision evidence rather than selecting a separate adaptive mode

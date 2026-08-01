## ADDED Requirements

### Requirement: Broad risk confidence requires current model maturation
Risk Evidence Ledger SHALL expose a typed `model_maturation` gate and SHALL require a current closed-for-task maturation result with the exact task, candidate, coverage, and input identity for every broad risk row that depends on model sufficiency.

#### Scenario: Missing or stale maturation blocks broad confidence
- **WHEN** a required model-maturation gate is missing, stale, blocked, scoped, progress-only, or bound to another identity
- **THEN** the ledger MUST block or scope broad confidence and report the specific maturation gap

#### Scenario: Exact closed maturation supports the row
- **WHEN** a required model-maturation gate references the current matching closed-for-task result with no open gaps
- **THEN** the gate MAY support the risk row without replacing any specialist evidence gate

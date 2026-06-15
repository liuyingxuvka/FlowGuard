## ADDED Requirements

### Requirement: Risk evidence ledger consumes business path evidence
Risk evidence ledger closure SHALL allow final confidence rows to depend on
current business-path topology and runtime evidence when path duplication,
conflict, old-path disposition, or wrong-path runtime proof can affect the
claim.

#### Scenario: Missing business path hazard review limits confidence
- **WHEN** a final claim depends on a path-sensitive workflow and business-path topology review is missing, stale, or blocked
- **THEN** the risk evidence ledger records the gap and limits or blocks broad confidence

#### Scenario: Current business path evidence supports closure
- **WHEN** topology hazard review and runtime path evidence both bind to the expected business path
- **THEN** the risk evidence ledger can use those current evidence rows to support final closure

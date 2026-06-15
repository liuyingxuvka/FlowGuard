## ADDED Requirements

### Requirement: Human-operability risks require explicit evidence gates
RiskEvidenceLedger SHALL support a human-operability gate for UI risks where
confusing affordance, missing task coverage, ambiguous action grammar, missing
dialog return, missing keyboard/focus behavior, or failed walkthrough evidence
can invalidate a broad UI claim.

#### Scenario: Required risk has no operability proof
- **WHEN** a required UI risk depends on human-operability
- **AND** no current task coverage, affordance, action grammar, dialog,
  keyboard, or walkthrough proof is linked
- **THEN** the risk ledger blocks broad UI done/release confidence

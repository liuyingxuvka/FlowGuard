## ADDED Requirements

### Requirement: Final risk evidence consumes UI and payload gates
RiskEvidenceLedger SHALL require current proof or route-gate evidence for UI
action and artifact payload risks before full confidence.

#### Scenario: UI risk lacks click-through proof
- **WHEN** a final risk row depends on implemented UI behavior
- **AND** no current UI implementation validation proof or scoped blindspot is
  attached
- **THEN** the ledger MUST block or scope full confidence

#### Scenario: Payload risk lacks payload proof
- **WHEN** a final risk row depends on file import/export, generated artifact,
  or AI work-package behavior
- **AND** no current artifact payload validation proof or scoped blindspot is
  attached
- **THEN** the ledger MUST block or scope full confidence

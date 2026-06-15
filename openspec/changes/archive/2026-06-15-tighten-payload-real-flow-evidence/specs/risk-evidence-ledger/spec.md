## ADDED Requirements

### Requirement: Final payload risk consumes real-flow proof
RiskEvidenceLedger SHALL require final broad confidence claims involving file,
artifact, or AI work-package behavior to consume current real-flow payload
proof or an explicit scoped blindspot.

#### Scenario: Payload risk has only synthetic case rows
- **WHEN** a final risk row depends on payload-bearing behavior
- **AND** the available evidence only declares synthetic payload cases without
  proof that the real payload surface executed
- **THEN** final confidence MUST remain blocked or scoped

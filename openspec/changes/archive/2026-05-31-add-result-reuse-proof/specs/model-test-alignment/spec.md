## ADDED Requirements

### Requirement: Model-Test Alignment rejects invalid reused test evidence
Model-Test Alignment SHALL reject reused test evidence before it counts toward
model obligation or code contract coverage unless the evidence has a current
test-result reuse ticket and a current proof artifact.

#### Scenario: Reused evidence covers obligation
- **WHEN** a `TestEvidence` row is marked as reused
- **AND** its reuse ticket and proof artifact are current
- **AND** the proof artifact covers the same obligation ids as the evidence row
- **THEN** Model-Test Alignment SHALL allow the evidence to participate in
  obligation coverage

#### Scenario: Reused evidence lacks ticket
- **WHEN** a `TestEvidence` row is marked as reused but has no reuse ticket
- **THEN** Model-Test Alignment SHALL report a missing test-reuse ticket finding
- **AND** the row SHALL NOT silently support a green alignment claim

#### Scenario: Reused evidence has stale proof artifact
- **WHEN** reused `TestEvidence` references a stale, non-passing, progress-only,
  or fingerprint-missing proof artifact
- **THEN** Model-Test Alignment SHALL report the proof artifact gap before green
  alignment can be claimed

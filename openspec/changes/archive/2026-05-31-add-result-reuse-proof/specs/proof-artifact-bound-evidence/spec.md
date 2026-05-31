## ADDED Requirements

### Requirement: Proof artifacts bind reused test result files
Proof artifact evidence SHALL serve as the concrete result artifact reference
for reused test evidence.

#### Scenario: Reused result has matching artifact fingerprint
- **WHEN** reused test evidence references a proof artifact with a result path
  and artifact fingerprints
- **AND** the test-result reuse ticket says the result fingerprint still matches
- **THEN** strict evidence consumers SHALL treat the proof artifact as the
  concrete reused result file

#### Scenario: Reused result has no artifact fingerprint
- **WHEN** reused test evidence has no proof artifact fingerprint
- **THEN** strict evidence consumers SHALL report the reused result as
  unsupported by concrete proof

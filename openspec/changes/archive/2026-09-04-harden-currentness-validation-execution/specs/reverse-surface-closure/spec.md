## ADDED Requirements

### Requirement: Authored reverse semantics are functional inputs
The canonical authored reverse semantic map SHALL be a fingerprinted functional
input to its owner authority. Discovery snapshots, reports, receipts, and
progress artifacts SHALL remain output-only. A map in authored-pending-audit
state SHALL NOT support a broad reverse-closure claim.

#### Scenario: Semantic assignment changes without route-set change
- **WHEN** an owner assignment, obligation, or test reference changes in the
  authored map
- **THEN** the owner input fingerprint SHALL change and the old receipt SHALL be
  stale

#### Scenario: Pending semantic map is consumed
- **WHEN** the map has not received its independent semantic acceptance receipt
- **THEN** broad reverse closure SHALL remain blocked

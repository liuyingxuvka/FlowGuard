## ADDED Requirements

### Requirement: UI done claims are reviewed before full confidence
FlowGuard Closure Contract SHALL review final UI done claims for missing manual
signoff, native-dialog blindspots, planned evidence, unmapped observed visible
items, missing functional chains, missing implementation validation, and stale
process evidence before allowing full done, release, publish, or production
confidence.

#### Scenario: Final UI claim is fully supported
- **WHEN** every in-scope UI last-mile evidence row is current, passing, mapped,
  and consumed by process and risk evidence
- **THEN** Closure Contract may allow the full UI done or release claim

#### Scenario: Final UI claim has native blindspot
- **WHEN** a native dialog or manual-only branch remains unobserved or only
  planned
- **THEN** Closure Contract downgrades the final wording to scoped confidence
  such as base implementation complete but release not complete

#### Scenario: Final UI claim has unmapped visible item
- **WHEN** an observed visible UI item remains unmapped to a model owner or
  scoped blindspot
- **THEN** Closure Contract blocks full UI completion confidence

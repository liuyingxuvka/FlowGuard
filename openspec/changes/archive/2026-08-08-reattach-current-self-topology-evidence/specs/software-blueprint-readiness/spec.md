## ADDED Requirements

### Requirement: Self-blueprint readiness preserves topology and evidence reattachment gaps
Whole-self-blueprint readiness SHALL consume the exact current structural-parent projection, cross-boundary relations, feedback-component progress reports, child terminal receipts, full parent aggregation receipt, and model-test helper/coverage report. Static-blueprint readiness SHALL remain blocked when any required relation, progress contract, independent receipt, helper leaf, coverage owner, or execution disposition is incomplete, stale, foreign, self-generated, or `not_run`.

#### Scenario: Full parent is green while a child is not reattached
- **WHEN** the full model parent reports success but one current child lacks its exact terminal receipt or the parent does not consume that receipt
- **THEN** readiness SHALL expose the child reattachment gap and remain blocked
- **AND** parent green SHALL NOT advance the truthful ordered prefix past the missing child evidence

#### Scenario: Structural hierarchy passes while feedback progress is missing
- **WHEN** every node has one structural parent but a reachable feedback component lacks a current independently evidenced progress contract
- **THEN** structural topology MAY remain complete while feedback and static-blueprint readiness remain blocked
- **AND** cross-boundary connectivity SHALL NOT be reclassified as structure to hide the gap

#### Scenario: Qualification creates the evidence it consumes
- **WHEN** the self-blueprint build or readiness route generates or registers a passing receipt used by the same qualification
- **THEN** readiness SHALL report an independent-evidence gap
- **AND** deterministic generation or matching content fingerprints SHALL NOT make the receipt current evidence

#### Scenario: Planned helper coverage has not executed
- **WHEN** recursive helper resolution and coverage ownership are statically complete but one exact leaf execution receipt is absent
- **THEN** static checker design MAY remain complete
- **AND** execution SHALL remain `not_run` and whole executed-evidence readiness SHALL not pass

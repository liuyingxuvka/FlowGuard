## ADDED Requirements

### Requirement: Preflight selects a bounded owner closure before materialization
Existing Model Preflight SHALL perform canonical plane-first commitment lookup
and exact observed-instance selection before reading or serializing detailed
model ownership. In ordinary light and full modes, an omitted changed-path hint
MUST NOT expand to every observed model.

#### Scenario: Ordinary task has no changed paths
- **WHEN** a non-trivial task supplies a task summary but no changed paths
- **THEN** preflight SHALL select a bounded same-plane primary owner set and
  typed affected closure rather than materializing the complete observed
  inventory

#### Scenario: Light mode is requested
- **WHEN** the caller requests light preflight
- **THEN** the result SHALL contain selected ids, purposes, fingerprints,
  boundaries, duplicate risk, and downstream route without deep class,
  function, field, or source-body expansion

#### Scenario: Full mode is requested
- **WHEN** the caller requests full preflight before proposal or implementation
- **THEN** detailed ownership SHALL be materialized only for the selected owner
  closure and any explicit unresolved ambiguity SHALL remain blocking

#### Scenario: Broad inventory is required
- **WHEN** ledger mode is `bootstrap_ledger` or `coverage_gap_backfill`, or the
  caller explicitly requests an authority inventory audit
- **THEN** preflight MAY inspect the complete declared inventory and SHALL label
  that breadth in its evidence

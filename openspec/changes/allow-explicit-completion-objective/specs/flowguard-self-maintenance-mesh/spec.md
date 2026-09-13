## ADDED Requirements

### Requirement: Self-maintenance binds finite cycles to explicit objectives

FlowGuard self-maintenance SHALL bind each finite completion cycle to the
derived identity of its reviewed objective and required terminal obligations.
The existing same-objective reuse, one-initial-attempt limit, one typed repair
limit, and terminal no-reopen rules SHALL remain unchanged. A new objective
MAY start only through the explicit objective resolver and SHALL never be
manufactured from mutable execution metadata.

#### Scenario: Current objective is reused

- **WHEN** a terminal parent is current and a second invocation names the same
  objective and frozen inputs
- **THEN** self-maintenance returns the same parent with zero producer
  invocations and creates no new run directory

#### Scenario: Current objective is exhausted

- **WHEN** the same objective has consumed its initial and repair attempts
- **THEN** self-maintenance remains blocked even if the caller changes output,
  receipt-store, source-delta, or owner-disposition identifiers

#### Scenario: New objective is admitted

- **WHEN** a distinct reviewed objective resolves to a different stable
  fingerprint and all ordinary readiness gates pass
- **THEN** self-maintenance admits a new finite cycle while preserving the old
  objective's immutable evidence

## ADDED Requirements

### Requirement: Bounded system composition is one portable-verification API cohort
The public API registry SHALL expose current system schema/artifact/report types and the canonical `check_system_composition` entrypoint inside portable verification discovery. Internal graph-construction, state-expansion, and trace-projection helpers MUST remain private.

#### Scenario: Public system symbol is exported
- **WHEN** a supported bounded system-composition name is present in the package facade
- **THEN** it is registered, documented, importable, and covered by exact API parity tests

#### Scenario: Internal compiler helper exists
- **WHEN** a helper only constructs joint states or rewrites portable traces
- **THEN** it is absent from public route-starter and package API cohorts


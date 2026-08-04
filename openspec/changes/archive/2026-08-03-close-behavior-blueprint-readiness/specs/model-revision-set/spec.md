## ADDED Requirements

### Requirement: Non-trivial revision sets close current intent lineage
An accepted non-trivial ModelRevisionSet SHALL include the current intent inventory fingerprint and a terminal disposition for every admitted intent contribution, or one explicit evidence-bound rationale that no declared external intent exists for the revision.

#### Scenario: Empty intent inventory passes by vacuity
- **WHEN** a non-trivial revision has no contributions or dispositions and no current no-intent rationale
- **THEN** acceptance SHALL be blocked without changing observed authority


## ADDED Requirements

### Requirement: Affected authority is relationship-complete
For an upgraded behavior surface, the authoritative model system SHALL identify its model owner, source owner, test or check owner, runtime entry when applicable, and explicit gaps; an inventory row alone SHALL NOT prove this relationship coverage.

#### Scenario: Model exists without a validating owner edge
- **WHEN** an affected model is inventoried but no current test/check owner or declared gap is attached
- **THEN** the authority audit reports incomplete affected coverage

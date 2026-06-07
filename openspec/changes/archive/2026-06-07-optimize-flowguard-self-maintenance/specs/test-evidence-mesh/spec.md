## ADDED Requirements

### Requirement: Self-maintenance validation mesh
Test Evidence Mesh SHALL represent slow, large, release-only, stale, skipped, or background self-maintenance validations as parent/child evidence with freshness and result artifacts.

#### Scenario: Full regression times out
- **WHEN** full regression does not complete within the practical run window
- **THEN** Test Evidence Mesh SHALL record the timeout as a scoped gap and preserve focused child evidence instead of claiming parent pass

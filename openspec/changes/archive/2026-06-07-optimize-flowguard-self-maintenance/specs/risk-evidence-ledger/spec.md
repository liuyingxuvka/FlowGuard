## ADDED Requirements

### Requirement: Self-maintenance final claim boundary
Risk Evidence Ledger SHALL surface self-maintenance gaps, stale evidence, unsupported route claims, install sync gaps, shadow workspace gaps, and local git limitations before final broad confidence.

#### Scenario: Install sync not verified
- **WHEN** source changes are complete but editable install, import path, metadata version, feature availability, or shadow workspace sync is not verified
- **THEN** the ledger SHALL block or scope the final release/install confidence claim

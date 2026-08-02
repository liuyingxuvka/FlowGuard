## ADDED Requirements

### Requirement: Each demanded owner has one canonical resolution
The system SHALL accept exactly one canonical owner resolution for each demanded owner. Task-coverage display and maturation evaluation SHALL be projections of that same resolution identity and fingerprint rather than separately entered claims.

#### Scenario: Same owner is submitted twice with different evidence
- **WHEN** two resolutions for one demanded owner have different identities, dispositions, or evidence fingerprints
- **THEN** maturation is blocked with a duplicate-or-conflicting-resolution diagnostic

#### Scenario: Display and maturation consume the same resolution
- **WHEN** a demanded owner has one current terminal resolution
- **THEN** both the task-coverage row and maturation contribution report the same resolution identity and fingerprint

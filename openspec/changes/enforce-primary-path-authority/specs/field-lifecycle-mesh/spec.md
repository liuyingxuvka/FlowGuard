## ADDED Requirements

### Requirement: Field lifecycle rejects hidden fallback fields
FieldLifecycleMesh SHALL classify old, renamed, alias, compatibility, backup,
and migration fields that can replace a primary field after failure.

#### Scenario: Old field fallback blocks
- **WHEN** a new primary field is missing or invalid and code reads an old
  field to return success for the same business intent
- **THEN** FieldLifecycleMesh SHALL report a hidden fallback field gap

#### Scenario: Migration field has closing disposition
- **WHEN** a migration-only field remains
- **THEN** FieldLifecycleMesh SHALL require owner, readers, writers,
  projection, lifecycle, evidence, and closing disposition

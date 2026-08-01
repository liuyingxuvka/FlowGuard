## ADDED Requirements

### Requirement: Triggered field coverage contributes to maturation
FieldLifecycleMesh SHALL project the current in-scope field inventory, behavior projections, reader/writer ownership, replacement dispositions, and unresolved field gaps into task-local maturation when field work is triggered.

#### Scenario: Stale field inventory cannot satisfy maturation
- **WHEN** a field contribution is stale or lacks an exact owner/disposition for an in-scope field
- **THEN** maturation MUST preserve a stale or missing-obligation signal and MUST NOT count the field as covered

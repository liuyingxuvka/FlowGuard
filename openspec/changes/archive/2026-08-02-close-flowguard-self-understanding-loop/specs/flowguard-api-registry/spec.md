## ADDED Requirements

### Requirement: Understanding status extends the existing kernel API group
The public understanding-status types and functions SHALL be registered under the existing model-first kernel owner. They SHALL NOT create a new public route or skill, and registry, import, serialization, and CLI projections SHALL remain in parity.

#### Scenario: Status API is added to another route
- **WHEN** the public status surface appears under a new or unrelated route owner
- **THEN** registry validation fails with an ownership mismatch

#### Scenario: CLI field lacks API serialization parity
- **WHEN** a status field is exposed through the CLI but omitted from the public serialized API result
- **THEN** parity validation fails

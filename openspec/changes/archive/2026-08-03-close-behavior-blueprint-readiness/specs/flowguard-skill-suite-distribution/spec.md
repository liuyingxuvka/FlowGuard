## ADDED Requirements

### Requirement: Blueprint release freezes behavior and reduction evidence
Before installation or source publication for a blueprint-qualified FlowGuard release, the distribution owner SHALL consume the frozen behavior-block qualification and self-reduction evidence identities in addition to the existing source, skill, model, test, OpenSpec, and parity owners. Empirical reconstruction SHALL remain excluded unless separately requested.

#### Scenario: Installed projection is current but behavior qualification is stale
- **WHEN** clean consumer installation parity passes but the behavior-block qualification fingerprint does not match the release tree
- **THEN** installation status MAY remain current for that projection
- **AND** GitHub release publication SHALL remain blocked


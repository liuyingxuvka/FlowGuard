## ADDED Requirements

### Requirement: Separate inventory authorities
FlowGuard SHALL expose one maintainer-source inventory and one consumer-distribution inventory with distinct schemas, identities, hashes, and claim boundaries.

#### Scenario: Author source is validated
- **WHEN** the maintainer-source inventory runs against the canonical FlowGuard repository
- **THEN** it MAY require author-owned SkillGuard control files while proving only author-maintenance completeness

#### Scenario: Consumer distribution is validated
- **WHEN** the consumer-distribution inventory runs against a staged or installed release
- **THEN** it SHALL require the 15 target-owned consumer members and SHALL reject every author-control path

### Requirement: Shared stable membership without shared path policy
Both inventories MUST derive the same one-kernel and fourteen-satellite identities from one canonical member authority while keeping their required and prohibited path policies separate.

#### Scenario: Private member list drifts
- **WHEN** an installer or validator contains an unapproved second literal suite member list
- **THEN** inventory validation SHALL fail and identify the duplicate owner

#### Scenario: Author-only path is requested in consumer inventory
- **WHEN** a consumer validator is configured to require `.skillguard` or another author-control path
- **THEN** schema validation SHALL reject the inventory definition

### Requirement: Exact consumer reference closure
The consumer inventory SHALL prove that every distributed prompt reference, import, script, asset, and native data dependency resolves inside target-owned consumer paths.

#### Scenario: Referenced runtime remains author-only
- **WHEN** a target-owned entrypoint references content that exists only beneath `.skillguard`
- **THEN** consumer construction SHALL block before activation and name the unresolved dependency

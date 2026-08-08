## ADDED Requirements

### Requirement: Author projection synchronization has one current owner
FlowGuard author projection synchronization SHALL use the current atomic installer-owned author-sync operation as its sole maintained owner. Tests and documentation for a retired whole-workspace shadow synchronization script SHALL be removed rather than preserved through an import shim, compatibility command, or duplicate synchronization path.

#### Scenario: Retired shadow script tests remain
- **WHEN** tests still import or patch the retired whole-workspace shadow synchronization module
- **THEN** those tests SHALL be retired or replaced by tests of the current atomic author-sync owner before final validation

#### Scenario: Author shadow starts empty
- **WHEN** a new isolated author-shadow target has no accepted FlowGuard author projection
- **THEN** the current installation projection SHALL establish the bounded target and the atomic author-sync operation SHALL then prove exact author parity

#### Scenario: Consumer projection remains clean
- **WHEN** author-source validation and synchronization complete
- **THEN** the installed consumer projection SHALL exclude SkillGuard contracts, receipts, author registries, maintenance evidence, and whole-workspace synchronization machinery

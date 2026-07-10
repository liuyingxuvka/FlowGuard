## ADDED Requirements

### Requirement: Canonical Skill Suite Inventory
The system SHALL maintain one versioned canonical inventory that identifies the FlowGuard kernel and every public satellite skill, including stable skill id, route role, expected entry files, and control-root expectation. Inventory skill ids MUST be unique and the current inventory MUST contain exactly one kernel and sixteen satellites.

#### Scenario: Current suite is fully declared
- **WHEN** the canonical inventory is loaded from the current repository
- **THEN** it identifies seventeen unique members with exactly one kernel and sixteen satellites

#### Scenario: Duplicate member is declared
- **WHEN** two inventory records use the same skill id
- **THEN** validation fails with a duplicate-member diagnostic and no suite-complete claim

### Requirement: Bidirectional Membership Reconciliation
The suite validator SHALL discover every directory containing `SKILL.md` under the configured FlowGuard skill root and SHALL compare the discovered set with the canonical inventory in both directions. A missing, extra, or renamed member MUST fail validation.

#### Scenario: Undeclared skill directory exists
- **WHEN** a new `SKILL.md` directory exists but is absent from the canonical inventory
- **THEN** validation fails with an extra-discovered-member diagnostic naming that directory

#### Scenario: Declared directory is absent
- **WHEN** an inventory member has no corresponding `SKILL.md` directory
- **THEN** validation fails with a missing-declared-member diagnostic naming that member

### Requirement: Missing Controls Are Visible Failures
Suite discovery MUST begin from `SKILL.md` membership rather than existing `.skillguard` directories or check scripts. If a member lacks an expected control root or required entry file, the member SHALL remain in the result and SHALL fail the relevant readiness gate.

#### Scenario: Behavior ledger control root is absent
- **WHEN** the Behavior Commitment Ledger has `SKILL.md` but no expected `.skillguard` control root
- **THEN** the suite report includes that skill and returns a missing-control-root failure instead of omitting it

### Requirement: Canonical Inventory Projections
Legacy suite marker and readiness commands SHALL consume the canonical inventory result and MUST NOT maintain independent member lists. Machine output SHALL include the inventory schema version and a deterministic inventory hash.

#### Scenario: Legacy verifier is run
- **WHEN** the suite marker compatibility script executes
- **THEN** its member set and pass/fail decision are obtained from the canonical inventory validator

#### Scenario: Private hard-coded list drifts
- **WHEN** a repository check finds a second unapproved literal suite member list
- **THEN** validation fails and identifies the duplicate inventory owner

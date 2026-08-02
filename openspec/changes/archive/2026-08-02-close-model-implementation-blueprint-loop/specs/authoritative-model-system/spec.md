## ADDED Requirements

### Requirement: Blueprint closure uses an independently discovered implementation universe
The authoritative model system SHALL consume a fingerprinted implementation and reconstruction-resource inventory derived independently from declared models, code contracts, and tests before it licenses a whole-software blueprint claim. Every admitted inventory item SHALL have one explicit disposition, and unresolved files, parse failures, hidden state or effect writers, duplicate primary owners, and omitted reconstruction resources SHALL block static blueprint completion.

#### Scenario: Undeclared helper exists in production source
- **WHEN** independent discovery finds a behavior-bearing helper that is absent from the declared model and contract bindings
- **THEN** static blueprint closure is incomplete and identifies the helper

#### Scenario: Every admitted item has a current disposition
- **WHEN** the current inventory, bindings, resources, and owner fingerprints cover every item inside the declared boundary
- **THEN** the system may report static blueprint complete within that boundary

### Requirement: Static blueprint and empirical reconstruction are separate claims
The authoritative model system SHALL report static blueprint closure independently from empirical reconstruction evidence. Static completion with no reconstruction run SHALL NOT be described as independently reconstructed or empirically verified.

#### Scenario: Static closure passes without a reconstruction receipt
- **WHEN** every static obligation is current and empirical reconstruction has not run
- **THEN** the result reports static complete and reconstruction not-run

#### Scenario: Reconstruction receipt targets another blueprint
- **WHEN** an empirical receipt carries a blueprint fingerprint different from the current manifest
- **THEN** empirical reconstruction is stale or blocked without changing the static result

### Requirement: Blueprint projection remains derived from the sole observed authority
Any portable software-blueprint projection SHALL bind the exact current observed model-system snapshot and existing owner fingerprints. It SHALL NOT create another observed head, copy owner semantics into a competing authority, or remain current after a consumed owner changes.

#### Scenario: Observed snapshot changes after export
- **WHEN** the observed model-system snapshot changes after a blueprint projection is produced
- **THEN** the projection becomes stale until deterministically regenerated

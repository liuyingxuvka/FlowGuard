## ADDED Requirements

### Requirement: Behavior sources are external promises, not implementation self-description
Behavior Commitment Ledger SHALL register normative requirements, public
contracts, user-visible workflow declarations, and other sources that state an
external behavior promise. Production modules, helper modules, executable
self-model files, tests, generated inventories, and validation receipts SHALL
retain their exact relationship to the commitment through the software
blueprint, implementation inventory, Model-Test Alignment, or TestMesh and
SHALL NOT act as the BCL source authority for that promise.

#### Scenario: Implementation currently describes its own commitment
- **WHEN** a BCL source row points to a production, helper, executable-model, or test file as the source of an external promise
- **THEN** the commitment remains blocked from broad external-promise confidence until an exact current normative or public-contract source is bound
- **AND** the code or test file remains traceable only through its native blueprint or evidence owner

#### Scenario: Normative source and implementation binding coexist
- **WHEN** a commitment cites a current OpenSpec requirement or public workflow contract and the software blueprint separately binds its implementation and tests
- **THEN** BCL owns the intended external promise while the blueprint and test owners own realization evidence without duplicate authority

#### Scenario: Generated evidence is offered as intent
- **WHEN** a generated inventory, result, receipt, or current file fingerprint is the only proposed source for a commitment
- **THEN** BCL rejects it as normative authority even if the artifact is mechanically fresh

### Requirement: Behavior source freshness is derived from current project files
Behavior Commitment Ledger SHALL derive physical source freshness from the
current project root instead of trusting a stored status. The existing ledger
owner SHALL resolve direct, anchored, semicolon-composite, and bounded-glob
source references into one sorted unique project-relative file inventory,
fingerprint every file with the canonical source-byte policy, derive each
surface content identity and the complete inventory identity deterministically,
and keep authored semantic fingerprints separate from mechanical source
identity.

#### Scenario: Checked-in source inventory is current
- **WHEN** every expected source reference resolves safely to its exact current file set and every stored surface and inventory fingerprint equals the deterministic live derivation
- **THEN** the live source-inventory review SHALL accept the physical source identity as current
- **AND** the ordinary review SHALL perform no write

#### Scenario: One source file changes after ledger publication
- **WHEN** any resolved source file content changes while the stored ledger row remains unchanged
- **THEN** the live review SHALL report the exact stale surface and block broad behavior confidence
- **AND** a handwritten `freshness_state=current` SHALL NOT override the mismatch

#### Scenario: Composite or glob membership changes
- **WHEN** a semicolon-composite or bounded-glob reference gains, loses, duplicates, or resolves a different project file
- **THEN** the surface content identity and top inventory identity SHALL change
- **AND** the previous inventory revision SHALL be stale

#### Scenario: Source reference is missing or unsafe
- **WHEN** a source reference is absolute, escapes the project root, reaches an unsafe link, resolves no files, or includes a missing file or invalid anchor
- **THEN** the live review SHALL fail visibly without guessing a replacement path or silently narrowing the inventory

#### Scenario: Explicit refresh is requested
- **WHEN** a caller explicitly asks the existing BCL owner to refresh an otherwise valid ledger
- **THEN** the owner SHALL return one immutable ledger value whose source rows, discovery evidence, top fingerprint, and inventory revision all come from the same derivation
- **AND** commitment decisions and authored semantic fingerprints SHALL remain unchanged

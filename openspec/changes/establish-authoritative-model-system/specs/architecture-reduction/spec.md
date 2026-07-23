## ADDED Requirements

### Requirement: Reduction consumes observed-system ownership
Architecture Reduction SHALL derive duplicate authority, obsolete route,
compatibility discovery, shared-kernel, and orphan candidates from the
validated observed model-system snapshot and its owner evidence.

#### Scenario: Two helpers are syntactically identical but semantically owned by different contracts
- **WHEN** duplicate code lacks observable-contract equivalence or a shared-kernel relation with parity evidence
- **THEN** Architecture Reduction keeps the candidate blocked

#### Scenario: Compatibility discovery duplicates the current manifest authority
- **WHEN** all supported runners are explicitly registered and undeclared runners fail visibly
- **THEN** the obsolete compatibility discovery path MAY be removed with manifest and runner parity evidence

## MODIFIED Requirements

### Requirement: Canonical Skill Suite Inventory
The system SHALL consume one package-owned, versioned canonical consumer
authority that identifies the FlowGuard kernel and every public satellite,
including stable skill id, route role, expected entry files, control-root
expectation, and content identity. Skill ids MUST be unique. The current
inventory MUST derive its exact member set from that authority and MUST NOT
encode the same set in another literal source.

#### Scenario: Current suite is fully declared
- **WHEN** canonical inventory is loaded from the current package authority
- **THEN** it identifies exactly one kernel and every current public satellite
- **AND** the current repository contains fifteen unique members

#### Scenario: Duplicate member is declared
- **WHEN** two authority records use the same skill id
- **THEN** validation fails with a duplicate-member diagnostic and no
  suite-complete claim

### Requirement: Bidirectional Membership Reconciliation
The suite validator SHALL compare the exact authority-declared member and file
sets with every FlowGuard-reserved skill directory and file in both directions.
A missing, extra, renamed, shadowed, or content-drifted member or file MUST fail
validation. Unrelated co-located skills remain outside the FlowGuard claim.

#### Scenario: Undeclared reserved skill directory exists
- **WHEN** a FlowGuard-reserved `SKILL.md` directory exists but is absent from
  the package authority
- **THEN** validation fails with an extra-discovered-member diagnostic

#### Scenario: Declared directory is absent
- **WHEN** an authority member has no corresponding `SKILL.md` directory
- **THEN** validation fails with a missing-declared-member diagnostic

#### Scenario: Self-consistent stale projection is supplied
- **WHEN** a stale installed or shadow projection contains internally matching
  files and its own stale member list
- **THEN** comparison against package authority fails instead of accepting the
  stale projection as self-authorizing

### Requirement: Canonical Inventory Projections
Repository, package, formal, shadow, and installed suite checks SHALL consume
the package-owned consumer authority and MUST NOT maintain independent member
lists. Machine output SHALL include authority schema, authority hash, member
set, exact file projection, projection role, and deterministic tree identity.

#### Scenario: A verifier is run
- **WHEN** any current suite or installation verifier executes
- **THEN** its member and file set is obtained from the package-owned authority

#### Scenario: Private hard-coded list drifts
- **WHEN** a repository check finds a second unapproved literal suite list
- **THEN** validation fails and identifies the duplicate inventory owner

## ADDED Requirements

### Requirement: Retired public entries have zero residual authority
Internal helpers for plan detailing and agent workflow rehearsal SHALL remain
owned by DevelopmentProcessFlow and SHALL NOT exist as installed public skill
ids, direct public routes, aliases, wrappers, fallbacks, consumer members, or
independent success implementations.

#### Scenario: Retired helper exists as an installed skill
- **WHEN** an installed or shadow root contains a public
  `flowguard-plan-detailing-compiler` or
  `flowguard-agent-workflow-rehearsal` skill
- **THEN** suite validation fails with retired-public-authority evidence

#### Scenario: Internal helper remains available through its owner
- **WHEN** DevelopmentProcessFlow invokes plan-detailing or agent-workflow
  internal mode
- **THEN** the helper executes only under that public owner's current route and
  does not become an independent public success path

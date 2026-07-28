## MODIFIED Requirements

### Requirement: Canonical Skill Suite Inventory
The system SHALL consume one package-owned, versioned canonical consumer
authority that identifies the FlowGuard kernel and every public satellite,
including stable skill id, route role, expected target-owned entry files, and
content identity. Skill ids MUST be unique. The current public member and file
sets MUST be derived from that authority and MUST NOT be repeated as another
literal list. Author-side maintenance inventory MAY retain its distinct
private path policy but MUST NOT become a consumer-runtime authority.

#### Scenario: Current suite is fully declared
- **WHEN** canonical inventory is loaded from the current package authority
- **THEN** it identifies fifteen unique members with exactly one `flowguard`
  kernel and fourteen public satellites

#### Scenario: Duplicate member is declared
- **WHEN** two authority records use the same skill id
- **THEN** validation fails with a duplicate-member diagnostic and no
  suite-complete claim

### Requirement: Bidirectional Membership Reconciliation
The suite validator SHALL compare the exact package-authority member and file
sets with every FlowGuard-reserved skill directory and file in both
directions. A missing, extra, renamed, shadowed, or content-drifted member or
file MUST fail validation. Unrelated co-located skills remain outside the
FlowGuard claim boundary.

#### Scenario: Undeclared skill directory exists
- **WHEN** a FlowGuard-reserved `SKILL.md` directory exists but is absent from
  the package authority
- **THEN** validation fails with an extra-discovered-member diagnostic naming
  that directory

#### Scenario: Declared directory is absent
- **WHEN** an authority member has no corresponding `SKILL.md` directory
- **THEN** validation fails with a missing-declared-member diagnostic naming
  that member

### Requirement: Missing Controls Are Visible Failures
Suite reconciliation MUST begin from the complete package-authority member and
file inventory. A missing target-owned consumer file SHALL remain visible and
fail consumer readiness. Author-side validation MAY require private controls
only in its separate maintenance projection; a consumer projection SHALL
reject every author-control path rather than treating it as required runtime
content.

#### Scenario: Behavior ledger control root is absent
- **WHEN** the author-maintenance projection requires a Behavior Commitment
  Ledger control root and that root is absent
- **THEN** the author report includes that skill and returns an exact
  missing-maintainer-control failure without changing consumer membership

#### Scenario: Consumer projection contains an author control
- **WHEN** a staged or installed consumer member contains `.skillguard` or
  another author-only control
- **THEN** consumer readiness fails with the exact prohibited path

### Requirement: Canonical Inventory Projections
Repository, package, formal, shadow, installed, project-audit, and
project-upgrade consumer checks SHALL consume the package-owned authority and
MUST NOT maintain independent member lists. Machine output SHALL include the
authority schema, authority hash, member set, exact file projection,
projection role, and deterministic tree identity. Author-maintenance evidence
retains a separate claim boundary and MUST NOT be read as a consumer fallback.

#### Scenario: Legacy verifier is run
- **WHEN** a retained suite marker or currentness verifier executes
- **THEN** its consumer member and file set and pass/fail decision are obtained
  from the package-owned authority

#### Scenario: Private hard-coded list drifts
- **WHEN** a repository check finds a second unapproved literal suite list
- **THEN** validation fails and identifies the duplicate inventory owner

## ADDED Requirements

### Requirement: Packaged consumer-suite authority has exact parity
Each FlowGuard package release SHALL contain one deterministic target-owned
consumer-suite authority declaring the current 15 member ids and exact clean
consumer file fingerprints. Maintainer validation, installation, and
installed-currentness checks SHALL require this authority to match both the
generated author-source projection and the global consumer projection by raw
content.

#### Scenario: Authority is compiled from current author source
- **WHEN** the maintainer compiles the consumer-suite authority
- **THEN** it derives exactly one kernel and fourteen satellites from the
  current author inventory
- **AND** it records the generated clean consumer files without author paths,
  `.skillguard`, contracts, receipts, or router state

#### Scenario: Package is installed non-editably
- **WHEN** FlowGuard is installed as a normal package without its repository
  checkout
- **THEN** the consumer-suite authority remains readable from package data
- **AND** no author suite map is required at runtime

#### Scenario: Source changes without authority regeneration
- **WHEN** a maintained consumer skill file changes and the packaged authority
  is not regenerated
- **THEN** author-side installation and currentness validation fail before
  activation or release

#### Scenario: Installed projection is exact
- **WHEN** every global consumer member and file matches the packaged authority
  and the installer ownership manifest names the same identity
- **THEN** installed consumer validation passes with one deterministic
  inventory hash

### Requirement: Retired public entries have zero residual authority
Internal plan-detailing and agent-workflow rehearsal helpers SHALL remain
owned by `flowguard-development-process-flow`. They SHALL NOT exist as
installed public skill ids, direct public routes, aliases, wrappers, fallbacks,
consumer members, or independent success implementations. The
`model-first-function-flow` implementation route remains internal to the
public `flowguard` kernel and SHALL NOT be installed as a separate skill.

#### Scenario: Retired helper exists as an installed skill
- **WHEN** an installed or shadow root contains a retired plan-detailing,
  agent-workflow-rehearsal, simulator, or model-first public skill entry
- **THEN** suite validation fails with retired-public-authority evidence

#### Scenario: Internal helper remains available through its owner
- **WHEN** DevelopmentProcessFlow invokes plan-detailing or agent-workflow
  internal mode
- **THEN** the helper executes only under that public owner's current route and
  does not become an independent public success path
